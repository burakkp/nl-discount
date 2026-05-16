import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:password123@localhost:5432/discount_db"  # local dev fallback only
)
engine = create_engine(DATABASE_URL)

def patch_database():
    with engine.connect() as conn:
        print("🛠️ Patching database schema...")
        try:
            conn.execute(text("ALTER TABLE discounts ADD COLUMN start_date DATE;"))
            conn.execute(text("ALTER TABLE discounts ADD COLUMN end_date DATE;"))
            conn.execute(text("ALTER TABLE discounts ADD COLUMN original_price FLOAT;"))
            conn.execute(text("ALTER TABLE discounts ADD COLUMN unit_label VARCHAR;"))
            conn.commit()
            print("✅ Columns added successfully!")
        except Exception as e:
            print(f"⚠️ Notice: {e}")
            print("If it says 'column already exists', you are good to go!")

if __name__ == "__main__":
    patch_database()