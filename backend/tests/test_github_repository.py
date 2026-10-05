import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from support import (
    AppTestCase,
    FakeSession,
    auth,
    github_api_service,
    github_oauth_service,
    github_repository_service,
)


class GithubRepositoryInitEndpointTests(AppTestCase, unittest.TestCase):
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
            name="algorecall-repo",
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
                "name": "algorecall-repo",
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

    def test_initialize_repository_refreshes_and_retries_after_github_auth_failure(self):
        app_user = SimpleNamespace(
            id=42,
            github_id=123,
            github_login="octocat",
            github_email=None,
        )
        repository = SimpleNamespace(
            id=7,
            github_repository_id=987,
            name="algorecall-repo",
        )
        self.login_test_user(app_user)

        with (
            patch.object(auth.user_service, "get_user_by_id", return_value=app_user),
            patch.object(
                github_oauth_service,
                "get_new_access_token",
                new=AsyncMock(return_value="stale-access-token"),
            ),
            patch.object(
                github_oauth_service,
                "refresh_access_token_for_user",
                new=AsyncMock(return_value="refreshed-access-token"),
            ) as refresh_access_token,
            patch.object(
                github_repository_service,
                "initialize_repository_for_user",
                new=AsyncMock(
                    side_effect=[
                        github_api_service.GithubApiAuthenticationError(),
                        repository,
                    ]
                ),
            ) as initialize_repository,
        ):
            response = self.client.post("/github/repository/init")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": 7,
                "github_repository_id": 987,
                "name": "algorecall-repo",
            },
        )
        refresh_access_token.assert_awaited_once_with(ANY, 42)
        self.assertEqual(initialize_repository.await_count, 2)
        self.assertEqual(
            initialize_repository.await_args_list[0].kwargs["access_token"],
            "stale-access-token",
        )
        self.assertEqual(
            initialize_repository.await_args_list[1].kwargs["access_token"],
            "refreshed-access-token",
        )

    def test_initialize_repository_returns_reconnect_when_retry_refresh_fails(self):
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
                new=AsyncMock(return_value="stale-access-token"),
            ),
            patch.object(
                github_oauth_service,
                "refresh_access_token_for_user",
                new=AsyncMock(
                    side_effect=github_oauth_service.GithubReconnectRequiredError()
                ),
            ),
            patch.object(
                github_repository_service,
                "initialize_repository_for_user",
                new=AsyncMock(
                    side_effect=github_api_service.GithubApiAuthenticationError()
                ),
            ),
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

    def test_initialize_repository_returns_reconnect_when_retry_auth_fails(self):
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
                new=AsyncMock(return_value="stale-access-token"),
            ),
            patch.object(
                github_oauth_service,
                "refresh_access_token_for_user",
                new=AsyncMock(return_value="refreshed-access-token"),
            ),
            patch.object(
                github_repository_service,
                "initialize_repository_for_user",
                new=AsyncMock(
                    side_effect=[
                        github_api_service.GithubApiAuthenticationError(),
                        github_api_service.GithubApiAuthenticationError(),
                    ]
                ),
            ),
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


class GithubRepositoryServiceTests(unittest.TestCase):
    def test_repository_service_returns_existing_repository_without_github_call(self):
        existing_repository = SimpleNamespace(
            id=7,
            user_id=42,
            github_repository_id=987,
            name="algorecall-repo",
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
            name="algorecall-repo",
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
            name="algorecall-repo",
            private=True,
            description=(
                "Coding problem recall and solution archive managed by algorecall"
            ),
        )
        self.assertIs(repository, db_session.added[0])
        self.assertEqual(repository.user_id, 42)
        self.assertEqual(repository.github_repository_id, 987)
        self.assertEqual(repository.name, "algorecall-repo")
        self.assertTrue(db_session.committed)
        self.assertEqual(db_session.refreshed, [repository])
