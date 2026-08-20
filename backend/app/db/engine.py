from sqlalchemy import create_engine

LOCAL_DEV_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/app"

engine = create_engine(LOCAL_DEV_DATABASE_URL, echo=True)