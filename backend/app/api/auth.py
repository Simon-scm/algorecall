import secrets
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from app.services import user_service, github_oauth_service
from app.db.session import get_db_session
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.config import FRONTEND_URL_AFTER_LOGIN



auth_router = APIRouter(prefix="/auth")

# TODO:
# - log out
# - new oauth required (routing) when access_token fails (expired)

# should be contacted by frontend when clicking on login 
@auth_router.get("/login/github")
def handle_github_login(request: Request, db_session: Session=Depends(get_db_session)) -> RedirectResponse:
    # check if user/browser has active session cookie while user clicks on login
    # this way user does not have to make github oauth every time he clicks on login
    user_id = request.session.get("user_id")

    if user_id is not None:
        user = user_service.get_user_by_id(db_session, user_id)
        if user is not None:
            return RedirectResponse(
                url=FRONTEND_URL_AFTER_LOGIN
            )
        request.session.clear()

    # if no session is active or session_user_id is not in db -> start auth flow
    # state randomly generated for every login, safed to session and send to github api. 
    # Github sends back the state so I can verify that the callback request is legit
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    github_auth_url = github_oauth_service.build_authorization_url(state=state, scope="read:user")

    return RedirectResponse(
        url=github_auth_url,
        status_code=302,
    )



@auth_router.get("/github/callback")
async def handle_github_callback(request: Request, code: str, state: str, db_session: Session=Depends(get_db_session)):
    if state != request.session.pop("oauth_state", None):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Get access token and user data from github
    try:
        github_access_token = await github_oauth_service.exchange_code_for_access_token(code)
        github_user = await github_oauth_service.get_authenticated_user(github_access_token)
    except github_oauth_service.GithubOAuthError as exc:
        raise HTTPException(status_code=400, detail="GitHub authentication failed") from exc

    # Get app user from db - if user does not exists, create a new one
    try:
        user = user_service.get_user_by_github_id(db_session, github_user.id)
        if not user:
            user = user_service.create_user(db_session, github_user.id, github_user.login, github_user.email)      
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="User already exists") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    # safe user_id as signed artifact in browser session to use for later authentication    
    request.session["user_id"] = user.id

    # redirect browser to home screen of frontend 
    return RedirectResponse(
        url=FRONTEND_URL_AFTER_LOGIN, # TODO: Change to fronted closed (in app) route when in prod
        status_code=302
    )


# later requested be frontend to render user data on home screen
@auth_router.get("/me")
def get_current_user(request: Request, db_session: Session=Depends(get_db_session)):
    session_user_id = request.session.get("user_id")
    if session_user_id is None:
        raise HTTPException(status_code=401, detail="Not athenticated")

    try:
        user = user_service.get_user_by_id(db_session, session_user_id)
    except SQLAlchemyError as exc:
        # TODO: redirect to frontend login page
        raise HTTPException(status_code=500, detail="Database error while retrieving user") from exc

    if user is None:
        # TODO: redirect to frontend login page
        request.session.clear()
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.id,
        "github_id": user.github_id,
        "github_login": user.github_login,
        "github_email": user.github_email,
    }
    


    
