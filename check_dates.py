from core.database.session import SessionLocal
from core.database.models import Store, Discount
from sqlalchemy import func
from datetime import date

db = SessionLocal()
today = date.today()
print(f"Today is: {today}")

all_deals = db.query(func.count(Discount.id)).scalar()
active_deals = db.query(func.count(Discount.id)).filter(Discount.start_date <= today, Discount.end_date >= today).scalar()

print(f"Total deals: {all_deals}")
print(f"Active deals (valid today): {active_deals}")

if active_deals < 10:
    sample = db.query(Discount.start_date, Discount.end_date).limit(5).all()
    print("Sample dates from DB:", sample)
