from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services import github_api_service, github_oauth_service
from app.services import github_repository_service, user_service


github_router = APIRouter(prefix="/github")


@github_router.post("/repository/init")
async def initialize_github_repository(
    request: Request,
    db_session: Session = Depends(get_db_session),
):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user = user_service.get_user_by_id(db_session, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="User not found")

    try:
        access_token = await github_oauth_service.get_new_access_token(
            db_session,
            user_id,
        )
        repository = await github_repository_service.initialize_repository_for_user(
            db_session=db_session,
            user_id=user_id,
            access_token=access_token,
        )
    except github_oauth_service.GithubReconnectRequiredError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "github_reconnect_required",
                "login_url": "/auth/login/github?force=true",
            },
        ) from exc
    except github_oauth_service.GithubOAuthError as exc:
        raise HTTPException(status_code=502, detail="GitHub authentication error") from exc
    except github_api_service.GithubApiError as exc:
        raise HTTPException(status_code=502, detail="GitHub API error") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    return {
        "id": repository.id,
        "github_repository_id": repository.github_repository_id,
        "name": repository.name,
    }
