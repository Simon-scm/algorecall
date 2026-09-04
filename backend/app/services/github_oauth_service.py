from app.config import GITHUB_CLIENT_ID, GITHUB_CALLBACK_URI, GITHUB_AUTHORIZE_URL, GITHUB_ACCESS_TOKEN_URL, GITHUB_CLIENT_SECRET, GITHUB_USER_URL
from urllib.parse import urlencode
from dataclasses import dataclass
import httpx
from app.db.models import GithubCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
import datetime



@dataclass
class GithubUser:
    id: int
    login: str
    email: str | None

@dataclass
class GithubTokens:
    access_token: str
    access_token_expires_at: datetime.datetime
    refresh_token: str
    refresh_token_expires_at: datetime.datetime
    scope: str | None



class GithubOAuthError(Exception):
    pass

class GithubReconnectRequiredError(Exception):
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



async def exchange_code_for_access_tokens(code: str) -> GithubTokens:
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
        raise GithubOAuthError("Failed to retrieve GitHub access token") from exc

    response_data = response.json()
    tokens = transform_response_into_github_tokens(response_data)

    return tokens



async def get_authenticated_user(github_access_token: str) -> GithubUser:
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
        raise GithubOAuthError("Failed to retrieve GitHub user data") from exc

    response_data = response.json()
    github_id = response_data.get("id")
    github_login = response_data.get("login")
    
    if github_id is None or github_login is None:
            raise GithubOAuthError(
                response_data.get("error_description", "GitHub did not return a user")
            )

    return GithubUser(
        id=response_data.get("id"),
        login=response_data.get("login"),
        email=response_data.get("email") # Better set None when mail is ""??
    )





def get_credentials_by_id(db_session: Session, user_id: int) -> GithubCredentials | None:
    stmt = select(GithubCredentials).where(GithubCredentials.user_id == user_id)
    credentials = db_session.execute(stmt).scalar_one_or_none()
    return credentials



# TODO: Exception Handling!
async def get_new_access_token(db_session: Session, user_id: int) -> str :
    # retrieve access token and expiring time from db
    github_creds = get_credentials_by_id(db_session, user_id)

    if github_creds is None:
        raise GithubOAuthError("GitHub credentials not found for user")

    if github_creds.access_token_expires_at > datetime.datetime.now(datetime.UTC):
            return github_creds.access_token

    # Error should by acknowledged by the endpoint in which the Github API operation was initiated
    # Enpoint should return json stating that a reconnect is required
    if github_creds.refresh_token_expires_at <= datetime.datetime.now(datetime.UTC):
        raise GithubReconnectRequiredError("GitHub refresh token expired")

    # if access token is expired get new one with refresh token 
    new_tokens = await refresh_tokens(github_creds.refresh_token)

    save_tokens(db_session, new_tokens, user_id)

    return new_tokens.access_token



# func to refresh token - only to be called from inside this service
async def refresh_tokens(refresh_token) -> GithubTokens:
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token

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
            raise GithubOAuthError("Failed to refresh GitHub access token") from exc
    
    response_data = response.json()
    tokens = transform_response_into_github_tokens(response_data)

    return tokens
    



# func to force refresh of access token manually
async def refresh_access_token_for_user(db_session: Session, user_id: int) -> str:
    # get refresh token from db
    github_creds = get_credentials_by_id(db_session, user_id)

    if github_creds is None:
        raise GithubOAuthError("GitHub credentials not found for user")

    # use refresh token to get new access token (and other tokens)
    new_tokens = await refresh_tokens(github_creds.refresh_token)
    
    save_tokens(db_session, new_tokens, user_id)

    return new_tokens.access_token



def save_tokens_for_user(db_session: Session, user_id: int, tokens: GithubTokens) -> None:
    save_tokens(db_session, tokens, user_id)



# TODO: encrypted tokens before saving in db when in prod 
def save_tokens(db_session: Session, tokens: GithubTokens, user_id: int) -> None:
    github_creds = get_credentials_by_id(db_session, user_id)

    if github_creds is None:
        github_creds = GithubCredentials(user_id=user_id)
        db_session.add(github_creds)

    github_creds.access_token = tokens.access_token
    github_creds.access_token_expires_at = tokens.access_token_expires_at
    github_creds.refresh_token = tokens.refresh_token
    github_creds.refresh_token_expires_at = tokens.refresh_token_expires_at
    github_creds.scope = tokens.scope

    try:
        db_session.commit()
        db_session.refresh(github_creds)

    except IntegrityError:
        db_session.rollback()
        raise
    except SQLAlchemyError:
        db_session.rollback()
        raise



def transform_response_into_github_tokens(response_data: dict) -> GithubTokens:
    access_token = response_data.get("access_token")
    refresh_token = response_data.get("refresh_token")
    access_token_expires_in = response_data.get("expires_in")
    refresh_token_expires_in = response_data.get("refresh_token_expires_in")

    if access_token is None:
        raise GithubOAuthError(
            response_data.get("error_description", "GitHub did not return an access token")
        )

    if refresh_token is None:
        raise GithubOAuthError(
            response_data.get("error_description", "GitHub did not return a refresh token")
        )

    if access_token_expires_in is None or refresh_token_expires_in is None:
        raise GithubOAuthError(
            response_data.get("error_description", "GitHub did not return token expiry data")
        )

    now = datetime.datetime.now(datetime.UTC)

    return GithubTokens(
        access_token=access_token,
        access_token_expires_at=now + datetime.timedelta(seconds=access_token_expires_in),
        refresh_token=refresh_token,
        refresh_token_expires_at=now + datetime.timedelta(seconds=refresh_token_expires_in),
        scope=response_data.get("scope"),
    )
