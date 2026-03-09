"""
core/database/session.py
SQLAlchemy engine + SessionLocal factory.
Import SessionLocal wherever you need a DB session.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file.\n"
        "Example: postgresql://user:password@localhost:5432/nederland_discounts"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # Detects stale connections before use
    pool_size=5,          # Connections kept open
    max_overflow=10       # Burst capacity above pool_size
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)
