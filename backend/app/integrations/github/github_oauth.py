from app.config import GITHUB_REDIRECT_URI, GITHUB_CLIENT_ID, GITHUB_AUTHORIZE_URL
from urllib.parse import urlencode
from dataclasses import dataclass

@dataclass
class GitHubUser:
    id: int
    login: str
    email: str | None

def build_authorization_url(state: str, scope: str) -> str:
    params = {
        "redirect_uri": GITHUB_REDIRECT_URI,
        "client_id":  GITHUB_CLIENT_ID,
        "scope": scope,
        "state": state
    }
    
    github_auth_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    return github_auth_url


async def exchange_code_for_token(code: str) -> str:
    pass



async def get_authenticated_user(github_access_token: str) -> GitHubUser:
    pass