import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
# Import your Base and models from your local path
from core.database.models import Base, Store, Discount 

load_dotenv()

# Safely get the Cloud URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL is missing from your .env file!")

print(f"🌍 Connecting to Cloud Database...")

# Connect to Supabase
engine = create_engine(DATABASE_URL)

print("🛠️ Building schema in the cloud...")
try:
    # This reads models.py and creates the tables in Supabase
    Base.metadata.create_all(bind=engine)
    print("✅ Success! Tables 'stores' and 'discounts' created in Supabase.")
except Exception as e:
    print(f"❌ Migration failed: {e}")