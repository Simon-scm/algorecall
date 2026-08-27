from app.db.models import AppUser
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError



def create_user(session: Session, github_id:str, github_login: str, github_email: str=None) -> AppUser:
    user = AppUser(
        github_id=github_id,
        github_login=github_login,
        github_email=github_email
    )

    try:
        session.add(user)
        session.commit()
        session.refresh(user)

        return user
    
    except IntegrityError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise

def get_user_by_id(session: Session, user_id: str) -> AppUser | None:
    return session.get(AppUser, user_id)
    


def get_user_by_github_id(session: Session, github_id) -> AppUser | None:
    stmt = select(AppUser).where(AppUser.github_id == github_id)
    user = session.execute(stmt).scalar_one_or_none()
    return user