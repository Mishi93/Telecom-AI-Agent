from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env directly here, rather than relying on core.py to have
# loaded it first. main.py imports this module before agent.core, so if
# only core.py called load_dotenv(), DATABASE_URL would be read from the
# environment BEFORE the .env file's values were ever loaded.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# Absolute path, driven by an env var, instead of a relative "./telecom.db".
# A relative path resolves against whatever the process's working directory
# happens to be at runtime - which differs between how Railway invokes
# uvicorn vs. how a script gets run via `railway ssh`, causing the app and
# your data-generation scripts to silently read/write two different files.
#
# Local dev: falls back to ./telecom.db (unchanged behavior).
# Production (Railway): set DATABASE_URL to an absolute path on your
# mounted Volume, e.g. sqlite:////data/telecom.db (note: FOUR slashes -
# three for the sqlite:// scheme + one for the absolute path).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./telecom.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Crucial for multi-threading
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Add this helper dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # Forces the database connection to close after EVERY request