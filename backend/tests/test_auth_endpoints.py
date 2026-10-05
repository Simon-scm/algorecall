import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from support import AppTestCase, auth, github_oauth_service


class AuthEndpointTests(AppTestCase, unittest.TestCase):
    def test_github_login_redirect_sets_oauth_state(self):
        self.start_login_and_get_state()

    def test_github_login_force_starts_oauth_for_existing_session(self):
        app_user = SimpleNamespace(
            id=42,
            github_id=123,
            github_login="octocat",
            github_email=None,
        )
        self.login_test_user(app_user)
        captured = {}

        def fake_authorization_url(state: str, scope: str) -> str:
            captured["state"] = state
            captured["scope"] = scope
            return f"https://github.test/oauth?state={state}&scope={scope}"

        with (
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
            patch.object(
                github_oauth_service,
                "build_authorization_url",
                side_effect=fake_authorization_url,
            ),
        ):
            response = self.client.get("/auth/login/github?force=true")

        self.assertEqual(response.status_code, 302)
        self.assertIn("https://github.test/oauth", response.headers["location"])
        self.assertIn(captured["state"], response.headers["location"])

    def test_callback_creates_session_and_me_resolves_user(self):
        state = self.start_login_and_get_state()
        github_tokens = github_oauth_service.GithubTokens(
            access_token="access-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token="refresh-token",
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scope="read:user",
        )
        github_user = github_oauth_service.GithubUser(
            id=123,
            login="octocat",
            email="octocat@example.com",
        )
        app_user = SimpleNamespace(
            id=42,
            github_id=123,
            github_login="octocat",
            github_email="octocat@example.com",
        )

        with (
            patch.object(
                github_oauth_service,
                "exchange_code_for_access_tokens",
                new=AsyncMock(return_value=github_tokens),
            ) as exchange_code,
            patch.object(
                github_oauth_service,
                "get_authenticated_user",
                new=AsyncMock(return_value=github_user),
            ) as get_github_user,
            patch.object(auth.user_service, "get_user_by_github_id", return_value=None),
            patch.object(auth.user_service, "create_user", return_value=app_user) as create_user,
            patch.object(github_oauth_service, "save_tokens_for_user") as save_tokens,
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
        ):
            callback_response = self.client.get(
                f"/auth/github/callback?code=test-code&state={state}"
            )
            me_response = self.client.get("/auth/me")

        self.assertEqual(callback_response.status_code, 302)
        self.assertEqual(callback_response.headers["location"], "http://frontend.test/app")
        exchange_code.assert_awaited_once_with("test-code")
        get_github_user.assert_awaited_once_with("access-token")
        create_user.assert_called_once()
        save_tokens.assert_called_once_with(ANY, 42, github_tokens)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(
            me_response.json(),
            {
                "id": 42,
                "github_id": 123,
                "github_login": "octocat",
                "github_email": "octocat@example.com",
            },
        )

    def test_callback_rejects_invalid_oauth_state(self):
        self.start_login_and_get_state()

        with patch.object(
            github_oauth_service,
            "exchange_code_for_access_tokens",
            new=AsyncMock(),
        ) as exchange_code:
            response = self.client.get(
                "/auth/github/callback?code=test-code&state=wrong-state"
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid OAuth state")
        exchange_code.assert_not_awaited()

    def test_logout_clears_session(self):
        state = self.start_login_and_get_state()
        github_tokens = github_oauth_service.GithubTokens(
            access_token="access-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token="refresh-token",
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scope="read:user",
        )
        github_user = github_oauth_service.GithubUser(id=123, login="octocat", email=None)
        app_user = SimpleNamespace(id=42, github_id=123, github_login="octocat", github_email=None)

        with (
            patch.object(
                github_oauth_service,
                "exchange_code_for_access_tokens",
                new=AsyncMock(return_value=github_tokens),
            ),
            patch.object(
                github_oauth_service,
                "get_authenticated_user",
                new=AsyncMock(return_value=github_user),
            ),
            patch.object(auth.user_service, "get_user_by_github_id", return_value=app_user),
            patch.object(github_oauth_service, "save_tokens_for_user"),
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
        ):
            self.client.get(f"/auth/github/callback?code=test-code&state={state}")
            logged_in_response = self.client.get("/auth/me")
            logout_response = self.client.post("/auth/logout")
            logged_out_response = self.client.get("/auth/me")

        self.assertEqual(logged_in_response.status_code, 200)
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json(), {"message": "Logged out"})
        self.assertEqual(logged_out_response.status_code, 401)
