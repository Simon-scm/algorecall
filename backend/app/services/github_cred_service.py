from app.db.models import GithubCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import datetime
from dataclasses import dataclass

@dataclass
class GithubTokens:
    access_token: str
    access_token_expires_at: datetime.datetime
    refresh_token: str
    refresh_token_expires_at: datetime.datetime



def get_user_by_id(user_id: str) -> GithubCredentials:
    pass



# TODO: Exception Handling!
async def get_valid_access_token(db_session: Session, user_id: str) -> str :
    # retrieve access token and expiring time from db
    github_creds = db_session.get(GithubCredentials, user_id)

    if github_creds.access_token > datetime.datetime.now():
            return github_creds.access_token

    # if access token is expired get new one with refresh token 
    new_tokens = await refresh_access_token(github_creds.refresh_token)

    save_tokens(new_tokens)

    return new_tokens.access_token



# func to refresh token - only to be called from inside this service
async def refresh_access_token(refresh_token) -> GithubTokens:
     pass


# func to force refresh of access token manually
async def refresh_access_token_for_user(db_session: Session, user_id: str) -> str:

    # get refresh token from db
    github_creds = db_session.get(GithubCredentials, user_id)
    # use refresh token to get new access token (and other tokens)
    new_tokens = await refresh_access_token(github_creds.refresh_token)
    
    save_tokens(new_tokens)

    return new_tokens.access_token



def save_tokens(db_session: Session, tokens: dict) -> None:

    github_creds = GithubCredentials(
        access_toke = tokens.access_token,
        access_token_expires_at = tokens.access_token_expires_at,
        refresh_token = tokens.refresh_token,
        refresh_token_expires_at = tokens.refresh_token_expires_at
    )

    try:
        db_session.add(github_creds)
        db_session.commit()
        db_session.refresh()

    except IntegrityError:
        db_session.rollback()
        raise
    except SQLAlchemyError:
        db_session.rollback()
        raise