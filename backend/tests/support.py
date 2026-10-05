import os

from fastapi.testclient import TestClient


os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GITHUB_AUTHORIZE_URL", "https://github.test/login/oauth/authorize")
os.environ.setdefault("GITHUB_CALLBACK_URI", "http://testserver/auth/github/callback")
os.environ.setdefault("GITHUB_ACCESS_TOKEN_URL", "https://github.test/login/oauth/access_token")
os.environ.setdefault("GITHUB_USER_URL", "https://github.test/user")
os.environ.setdefault("FRONTEND_URL_AFTER_LOGIN", "http://frontend.test/app")


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


class AppTestCase:
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

        from unittest.mock import patch

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
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, patch

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
