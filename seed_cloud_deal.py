import os
from datetime import date, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# Adjust this import based on your exact folder structure
from core.database.models import Store, Discount

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
db = sessionmaker(bind=engine)()

print("🌍 Connecting to Supabase...")

# 1. Find or create our test store in Tiel
store = db.query(Store).filter(Store.address == "Waterstraat 68, Tiel").first()
if not store:
    location_wkt = "SRID=4326;POINT(5.430 51.884)"
    store = Store(chain_name="Albert Heijn", address="Waterstraat 68, Tiel", location=location_wkt)
    db.add(store)
    db.commit()
    print("➕ Added Test Store to Cloud.")

# 2. Inject a fresh deal valid for TODAY
today = date.today()
fresh_deal = Discount(
    master_product_id="Verse Stroopwafels",
    store_id=store.id,
    deal_type="FIXED_PRICE",
    deal_price=1.99,
    start_date=today - timedelta(days=1),
    end_date=today + timedelta(days=6) # Valid until next week!
)

db.add(fresh_deal)
db.commit()
print(f"✅ Fresh deal injected into Supabase Cloud! Valid until {fresh_deal.end_date}")
db.close()