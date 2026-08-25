import secrets
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.integrations.github.github_oauth import GitHubOAuthClient




auth_router = APIRouter(prefix="/auth")

github_auth_client = GitHubOAuthClient()

@auth_router.get("/login/github")
def handle_github_login(request: Request):
    # state randomly generated for every login, safed to session and send to github api. Github sends back the state so I can verify that the callback request is legit
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    github_auth_url = github_auth_client.build_authorization_url(state=state, scope="read:user")

    return RedirectResponse(
        url=github_auth_url,
        status_code=302,
    )



@auth_router.get("/github/callback")
async def handle_github_callback(request: Request, code: str, state: str):
    if state != request.session.get("oauth_state"):
        raise HTTPException()



    
