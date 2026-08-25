from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.config import SESSION_SECRET
from app.api.auth import auth_router


app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False
)


app.include_router(auth_router)