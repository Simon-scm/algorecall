from sqlalchemy.orm import sessionmaker
from .engine import engine

SessionLocal = sessionmaker(engine)

def get_session():
    with SessionLocal() as session:
        yield session
