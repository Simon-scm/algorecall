from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.config import SESSION_SECRET
from app.api.auth import auth_router
from app.api.github import github_router


app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False
)


app.include_router(auth_router)
app.include_router(github_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )