import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch


os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_AUTHORIZE_URL", "https://github.test/login/oauth/authorize")
os.environ.setdefault("GITHUB_CALLBACK_URI", "http://testserver/auth/github/callback")
os.environ.setdefault("GITHUB_ACCESS_TOKEN_URL", "https://github.test/login/oauth/access_token")
os.environ.setdefault("GITHUB_USER_URL", "https://github.test/user")
os.environ.setdefault("FRONTEND_URL_AFTER_LOGIN", "http://frontend.test/app")


from fastapi.testclient import TestClient

from app.api import auth
from app.db.session import get_db_session
from app.main import app
from app.services import github_api_service, github_oauth_service, github_repository_service


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.rolled_back = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def rollback(self):
        self.rolled_back = True


class AppTestCase(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_db_session] = lambda: FakeSession()
        self.client = TestClient(app, follow_redirects=False)

    def tearDown(self):
        app.dependency_overrides.clear()

    def start_login_and_get_state(self):
        captured = {}

        def fake_authorization_url(state: str, scope: str) -> str:
            captured["state"] = state
            captured["scope"] = scope
            return f"https://github.test/oauth?state={state}&scope={scope}"

        with patch.object(
            github_oauth_service,
            "build_authorization_url",
            side_effect=fake_authorization_url,
        ):
            response = self.client.get("/auth/login/github")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(captured["scope"], "repo read:user")
        self.assertIn(captured["state"], response.headers["location"])
        return captured["state"]

    def login_test_user(self, app_user):
        state = self.start_login_and_get_state()
        github_tokens = github_oauth_service.GithubTokens(
            access_token="access-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token="refresh-token",
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scope="repo read:user",
        )
        github_user = github_oauth_service.GithubUser(
            id=app_user.github_id,
            login=app_user.github_login,
            email=app_user.github_email,
        )

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
        ):
            response = self.client.get(
                f"/auth/github/callback?code=test-code&state={state}"
            )

        self.assertEqual(response.status_code, 302)


class AuthEndpointTests(AppTestCase):
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


class GithubOAuthServiceTests(unittest.TestCase):
    def test_transform_response_into_github_tokens(self):
        before = datetime.now(UTC)

        tokens = github_oauth_service.transform_response_into_github_tokens(
            {
                "access_token": "access-token",
                "expires_in": 3600,
                "refresh_token": "refresh-token",
                "refresh_token_expires_in": 7200,
                "scope": "read:user",
            }
        )

        self.assertEqual(tokens.access_token, "access-token")
        self.assertEqual(tokens.refresh_token, "refresh-token")
        self.assertEqual(tokens.scope, "read:user")
        self.assertGreaterEqual(tokens.access_token_expires_at, before + timedelta(seconds=3599))
        self.assertGreaterEqual(tokens.refresh_token_expires_at, before + timedelta(seconds=7199))
        self.assertIsNotNone(tokens.access_token_expires_at.tzinfo)
        self.assertIsNotNone(tokens.refresh_token_expires_at.tzinfo)

    def test_save_tokens_creates_or_updates_credentials_by_user_id(self):
        tokens = github_oauth_service.GithubTokens(
            access_token="new-access-token",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
            refresh_token="new-refresh-token",
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scope="read:user",
        )
        db_session = FakeSession()

        with patch.object(github_oauth_service, "get_credentials_by_user_id", return_value=None):
            github_oauth_service.save_tokens(db_session, tokens, user_id=42)

        self.assertEqual(len(db_session.added), 1)
        created_credentials = db_session.added[0]
        self.assertEqual(created_credentials.user_id, 42)
        self.assertEqual(created_credentials.access_token, "new-access-token")
        self.assertTrue(db_session.committed)
        self.assertEqual(db_session.refreshed, [created_credentials])

        existing_credentials = SimpleNamespace(user_id=42)
        db_session = FakeSession()

        with patch.object(
            github_oauth_service,
            "get_credentials_by_user_id",
            return_value=existing_credentials,
        ):
            github_oauth_service.save_tokens(db_session, tokens, user_id=42)

        self.assertEqual(db_session.added, [])
        self.assertEqual(existing_credentials.access_token, "new-access-token")
        self.assertEqual(existing_credentials.refresh_token, "new-refresh-token")
        self.assertTrue(db_session.committed)
        self.assertEqual(db_session.refreshed, [existing_credentials])

    def test_get_new_access_token_raises_reconnect_when_refresh_token_expired(self):
        expired_credentials = SimpleNamespace(
            access_token="old-access-token",
            access_token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
            refresh_token="old-refresh-token",
            refresh_token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        with patch.object(
            github_oauth_service,
            "get_credentials_by_user_id",
            return_value=expired_credentials,
        ):
            with self.assertRaises(github_oauth_service.GithubReconnectRequiredError):
                asyncio.run(github_oauth_service.get_new_access_token(FakeSession(), 42))


class GithubRepositoryInitEndpointTests(AppTestCase):
    def test_initialize_repository_requires_login(self):
        response = self.client.post("/github/repository/init")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Not authenticated")

    def test_initialize_repository_uses_valid_token_and_returns_repository(self):
        app_user = SimpleNamespace(
            id=42,
            github_id=123,
            github_login="octocat",
            github_email="octocat@example.com",
        )
        repository = SimpleNamespace(
            id=7,
            github_repository_id=987,
            name="algorecall",
        )
        self.login_test_user(app_user)

        with (
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
            patch.object(
                github_oauth_service,
                "get_new_access_token",
                new=AsyncMock(return_value="valid-access-token"),
            ) as get_new_access_token,
            patch.object(
                github_repository_service,
                "initialize_repository_for_user",
                new=AsyncMock(return_value=repository),
            ) as initialize_repository,
        ):
            response = self.client.post("/github/repository/init")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": 7,
                "github_repository_id": 987,
                "name": "algorecall",
            },
        )
        get_new_access_token.assert_awaited_once_with(ANY, 42)
        initialize_repository.assert_awaited_once_with(
            db_session=ANY,
            user_id=42,
            access_token="valid-access-token",
        )

    def test_initialize_repository_returns_reconnect_required(self):
        app_user = SimpleNamespace(
            id=42,
            github_id=123,
            github_login="octocat",
            github_email=None,
        )
        self.login_test_user(app_user)

        with (
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
            patch.object(
                github_oauth_service,
                "get_new_access_token",
                new=AsyncMock(
                    side_effect=github_oauth_service.GithubReconnectRequiredError()
                ),
            ),
            patch.object(
                github_repository_service,
                "initialize_repository_for_user",
                new=AsyncMock(),
            ) as initialize_repository,
        ):
            response = self.client.post("/github/repository/init")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "github_reconnect_required",
                "login_url": "/auth/login/github?force=true",
            },
        )
        initialize_repository.assert_not_awaited()


class GithubRepositoryServiceTests(unittest.TestCase):
    def test_repository_service_returns_existing_repository_without_github_call(self):
        existing_repository = SimpleNamespace(
            id=7,
            user_id=42,
            github_repository_id=987,
            name="algorecall",
        )

        with (
            patch.object(
                github_repository_service,
                "get_repository_by_user_id",
                return_value=existing_repository,
            ),
            patch.object(
                github_api_service,
                "create_repository",
                new=AsyncMock(),
            ) as create_repository,
        ):
            repository = asyncio.run(
                github_repository_service.initialize_repository_for_user(
                    db_session=FakeSession(),
                    user_id=42,
                    access_token="valid-access-token",
                )
            )

        self.assertIs(repository, existing_repository)
        create_repository.assert_not_awaited()

    def test_repository_service_creates_and_saves_new_repository(self):
        db_session = FakeSession()
        github_repository = github_api_service.GithubRepositoryData(
            github_repository_id=987,
            name="algorecall",
        )

        with (
            patch.object(
                github_repository_service,
                "get_repository_by_user_id",
                return_value=None,
            ),
            patch.object(
                github_api_service,
                "create_repository",
                new=AsyncMock(return_value=github_repository),
            ) as create_repository,
        ):
            repository = asyncio.run(
                github_repository_service.initialize_repository_for_user(
                    db_session=db_session,
                    user_id=42,
                    access_token="valid-access-token",
                )
            )

        create_repository.assert_awaited_once_with(
            access_token="valid-access-token",
            name="algorecall",
            private=True,
            description=(
                "Coding problem recall and solution archive managed by algorecall"
            ),
        )
        self.assertIs(repository, db_session.added[0])
        self.assertEqual(repository.user_id, 42)
        self.assertEqual(repository.github_repository_id, 987)
        self.assertEqual(repository.name, "algorecall")
        self.assertTrue(db_session.committed)
        self.assertEqual(db_session.refreshed, [repository])


if __name__ == "__main__":
    unittest.main()
