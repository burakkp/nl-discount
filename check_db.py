from core.database.session import SessionLocal
from core.database.models import Store, Discount

db = SessionLocal()
stores = db.query(Store).all()
print(f"Total stores: {len(stores)}")
for s in stores:
    print(f"Store: {s.chain_name}, ID: {s.id}")

discounts = db.query(Discount).all()
print(f"Total discounts: {len(discounts)}")
from collections import Counter
c = Counter([d.store_id for d in discounts])
print("Discounts per store_id:", c)

db.close()
