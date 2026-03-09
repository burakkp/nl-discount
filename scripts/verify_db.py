import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database.session import SessionLocal
from core.database.models import Discount

def verify():
    db = SessionLocal()
    try:
        count = db.query(Discount).count()
        print(f"Success! The 'discounts' table exists and has {count} rows.")
    except Exception as e:
        print(f"Error checking 'discounts' table: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify()
