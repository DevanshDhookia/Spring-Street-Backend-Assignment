from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# pool_pre_ping revalidates idle connections before handing them to a caller
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — one session per request, always closed on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
