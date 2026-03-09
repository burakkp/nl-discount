from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Discount, Store
from datetime import date, timedelta

DATABASE_URL = "postgresql://admin:password123@localhost:5432/discount_db"
engine = create_engine(DATABASE_URL)
db = sessionmaker(bind=engine)()

# Find a test store
store = db.query(Store).first()

today = date.today() # March 9, 2026
tomorrow = today + timedelta(days=1)

# 1. Inject a "Fresh Week" Deal (Starts today)
fresh_deal = Discount(
    master_product_id="cat_melk_01",
    store_id=store.id,
    deal_price=0.99,
    start_date=today,
    end_date=today + timedelta(days=6)
)

# 2. Inject a "Last Chance" Deal (Ends tomorrow)
expiring_deal = Discount(
    master_product_id="cat_eieren_01",
    store_id=store.id,
    deal_price=1.49,
    start_date=today - timedelta(days=5),
    end_date=tomorrow
)

db.add(fresh_deal)
db.add(expiring_deal)
db.commit()
print(f"✅ Injected test deals for {today} into the DB!")
db.close()