from core.database.session import SessionLocal
from core.database.models import Store, Discount
from sqlalchemy import func
from datetime import date
from collections import Counter

db = SessionLocal()
today = date.today()

results = db.query(Store.chain_name).join(
    Store, Discount.store_id == Store.id
).filter(
    Discount.start_date <= today,
    Discount.end_date >= today,
).order_by(Discount.start_date.desc()).limit(50).all()

print("Stores in the latest 50 deals:")
c = Counter([r.chain_name for r in results])
print(c)
