from app.db.models import GithubRepository
from app.services import github_api_service
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


DEFAULT_REPOSITORY_NAME = "algorecall-repo"
DEFAULT_REPOSITORY_DESCRIPTION = (
    "Coding problem recall and solution archive managed by algorecall"
)


def get_repository_by_user_id(
    db_session: Session,
    user_id: int,
) -> GithubRepository | None:
    stmt = select(GithubRepository).where(GithubRepository.user_id == user_id)
    repository = db_session.execute(stmt).scalar_one_or_none()
    return repository


async def initialize_repository_for_user(
    db_session: Session,
    user_id: int,
    access_token: str,
) -> GithubRepository:
    existing_repository = get_repository_by_user_id(db_session, user_id)
    if existing_repository is not None:
        return existing_repository

    github_repository = await github_api_service.create_repository(
        access_token=access_token,
        name=DEFAULT_REPOSITORY_NAME,
        private=True,
        description=DEFAULT_REPOSITORY_DESCRIPTION,
    )

    repository = GithubRepository(
        user_id=user_id,
        github_repository_id=github_repository.github_repository_id,
        name=github_repository.name,
    )

    try:
        db_session.add(repository)
        db_session.commit()
        db_session.refresh(repository)
        return repository
    except IntegrityError:
        db_session.rollback()
        raise
    except SQLAlchemyError:
        db_session.rollback()
        raise
