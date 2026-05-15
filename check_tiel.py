from core.database.session import SessionLocal
from core.database.models import Store, Discount
from sqlalchemy import func

db = SessionLocal()
user_location = f"SRID=4326;POINT(5.43 51.88)"
radius_meters = 15000

results = db.query(
    Store.chain_name,
    func.count(Discount.id).label("deal_count")
).join(
    Discount, Store.id == Discount.store_id
).filter(
    func.ST_DWithin(Store.location, func.ST_GeographyFromText(user_location), radius_meters)
).group_by(Store.chain_name).all()

print("Stores within 15km of Tiel:")
for r in results:
    print(f"{r.chain_name}: {r.deal_count} deals")
