from core.database.session import engine
from sqlalchemy import text

def patch_db():
    with engine.connect() as conn:
        print("Checking if image_url exists in discounts table...")
        # Check if the column exists
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='discounts' AND column_name='image_url'"))
        if not res.fetchone():
            print("Adding image_url column...")
            conn.execute(text("ALTER TABLE discounts ADD COLUMN image_url VARCHAR;"))
            conn.commit()
            print("Successfully added image_url column.")
        else:
            print("image_url column already exists.")

if __name__ == "__main__":
    patch_db()
