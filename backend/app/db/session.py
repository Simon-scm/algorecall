from collections.abc import Generator
from sqlalchemy.orm import Session, sessionmaker
from .engine import engine

SessionLocal = sessionmaker(engine)

def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
