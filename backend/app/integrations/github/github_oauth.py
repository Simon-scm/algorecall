from app.config import GITHUB_REDIRECT_URI, GITHUB_CLIENT_ID, GITHUB_AUTHORIZE_URL
from urllib.parse import urlencode



class GitHubOAuthClient:

    def __init__(self):
        self.github_redirect_uri = GITHUB_REDIRECT_URI
        self.github_client_id = GITHUB_CLIENT_ID

    def build_authorization_url(self, state: str, scope: str) -> str:
        params = {
            "redirect_uri": self.github_redirect_uri,
            "client_id":  self.github_client_id,
            "scope": scope,
            "state": state
        }
        
        github_auth_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

        return github_auth_url
