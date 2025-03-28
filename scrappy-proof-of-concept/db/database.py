# db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from models.models import Base
from config import DATABASE_URL  # Use centralized configuration
from contextlib import contextmanager

# Create the engine using DATABASE_URL from config.py
engine = create_engine(DATABASE_URL, echo=False)

# Create a configured Session class with expire_on_commit set to False
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    """
    Initialize the DB, ensuring that all tables (including versioning tables) are created.
    """
    configure_mappers()
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Automatically commits if no exceptions occur, rolls back on errors,
    and ensures the session is closed.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
