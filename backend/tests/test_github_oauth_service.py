import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from support import FakeSession, github_oauth_service


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
