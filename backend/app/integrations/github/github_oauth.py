from app.config import GITHUB_CLIENT_ID, GITHUB_CALLBACK_URI, GITHUB_AUTHORIZE_URL, GITHUB_ACCESS_TOKEN_URL, GITHUB_CLIENT_SECRET, GITHUB_USER_URL
from urllib.parse import urlencode
from dataclasses import dataclass
import httpx

@dataclass
class GitHubUser:
    id: int
    login: str
    email: str | None

class GitHubOAuthError(Exception):
    pass


def build_authorization_url(state: str, scope: str) -> str:
    params = {
        "redirect_uri": GITHUB_CALLBACK_URI,
        "client_id":  GITHUB_CLIENT_ID,
        "scope": scope,
        "state": state
    }
    
    github_auth_url = f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    return github_auth_url


async def exchange_code_for_token(code: str) -> str:
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_CALLBACK_URI #just so github can check on their end to varify against first redirect_uri when requesting the code
    }

    headers = {"Accept": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=GITHUB_ACCESS_TOKEN_URL,
                data=data,
                headers=headers
            )
            response.raise_for_status()

    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise GitHubOAuthError("Failed to retrieve GitHub access token") from exc

    response_data = response.json()
    access_token = response_data.get("access_token")

    if access_token is None:
        raise GitHubOAuthError(
            response_data.get("error_description", "GitHub did not return an access token")
        )

    return access_token


async def get_authenticated_user(github_access_token: str) -> GitHubUser:
    headers={
        "Authorization": f"Bearer {github_access_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=GITHUB_USER_URL,
                headers=headers
            )

            response.raise_for_status()
          
    except httpx.HTTPError as exc:
        raise GitHubOAuthError("Failed to retrieve GitHub user data") from exc

    response_data = response.json()
    github_id = response_data.get("id")
    github_login = response_data.get("login")
    
    if github_id is None or github_login is None:
            raise GitHubOAuthError(
                response_data.get("error_description", "GitHub did not return a user")
            )

    return GitHubUser(
        id=response_data.get("id"),
        login=response_data.get("login"),
        email=response_data.get("email") # Better set None when mail is ""??
    )