import secrets
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from app.integrations.github import github_oauth
from app.services import user_service
from app.db.session import get_session
from sqlalchemy.orm import Session



auth_router = APIRouter(prefix="/auth")


@auth_router.get("/login/github")
def handle_github_login(request: Request) -> RedirectResponse:
    # state randomly generated for every login, safed to session and send to github api. 
    # Github sends back the state so I can verify that the callback request is legit
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    github_auth_url = github_oauth.build_authorization_url(state=state, scope="read:user")

    return RedirectResponse(
        url=github_auth_url,
        status_code=302,
    )


@auth_router.get("/github/callback")
async def handle_github_callback(request: Request, code: str, state: str, session: Session=Depends(get_session)):
    if state != request.session.pop("oauth_state", None):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    
    try:
        github_access_token = await github_oauth.exchange_code_for_token(code)
        github_user = await github_oauth.get_authenticated_user(github_access_token)
    except github_oauth.GitHubOAuthError:
        raise HTTPException(status_code=400, detail="GitHub authentication failed")
    
    user = user_service.get_user_by_github_id(session, github_user.id)
    if not user:
        user = user_service.create_user(session, github_user.id, github_user.login, github_user.email)

    request.session["user_id"] = user.id

    

    
