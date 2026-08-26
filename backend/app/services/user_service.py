from app.db.models import AppUser
from sqlalchemy.orm import Session

def get_user_by_github_id(session: Session, github_id) -> AppUser | None:
    pass

def create_user(session: Session, github_id:str, github_login: str, github_email: str=None) -> AppUser:
    pass


