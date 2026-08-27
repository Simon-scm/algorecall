from app.db.models import AppUser
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError



def create_user(db_session: Session, github_id:str, github_login: str, github_email: str=None) -> AppUser:
    user = AppUser(
        github_id=github_id,
        github_login=github_login,
        github_email=github_email
    )

    try:
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        return user
    
    except IntegrityError:
        db_session.rollback()
        raise
    except SQLAlchemyError:
        db_session.rollback()
        raise



def get_user_by_id(db_session: Session, user_id: str) -> AppUser | None:
    return db_session.get(AppUser, user_id)

    

def get_user_by_github_id(db_session: Session, github_id) -> AppUser | None:
    stmt = select(AppUser).where(AppUser.github_id == github_id)
    user = db_session.execute(stmt).scalar_one_or_none()
    return user


