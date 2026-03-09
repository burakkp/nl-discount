import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sqlalchemy import text
from core.database.session import engine
from core.database.models import Base

def init_db():
    print("Creating database tables...")
    try:
        # First ensure the PostGIS extension exists because we use Geography columns
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
    except Exception as e:
        print(f"Note: Could not create postgis extension (might already exist or lack permissions): {e}")

    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()

