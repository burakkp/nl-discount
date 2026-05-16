import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Store, Base

# Read from environment variable — never hardcode credentials.
# For local dev, set this in your shell or a .env file (which is git-ignored).
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:password123@localhost:5432/discount_db"  # local dev fallback only
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_test_stores():
    db = SessionLocal()

    # Coordinates for Tiel, Gelderland
    test_stores = [
        {"chain": "Albert Heijn", "address": "Waterstraat 68, Tiel", "lat": 51.884, "lng": 5.430},
        {"chain": "Jumbo", "address": "Kijkuit 1, Tiel", "lat": 51.886, "lng": 5.428},
        {"chain": "Lidl", "address": "Nieuwe Tielseweg 114, Tiel", "lat": 51.881, "lng": 5.435}
    ]

    print("🚀 Connecting to database...")
    for s in test_stores:
        existing = db.query(Store).filter(Store.address == s['address']).first()
        if not existing:
            location_wkt = f"SRID=4326;POINT({s['lng']} {s['lat']})"
            new_store = Store(chain_name=s['chain'], address=s['address'], location=location_wkt)
            db.add(new_store)
            print(f"➕ Added {s['chain']} at {s['address']}")
        else:
            print(f"⏭️  Skipped {s['chain']} (Already exists)")

    try:
        db.commit()
        print("✅ Successfully seeded test stores in Tiel!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error inserting stores: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_test_stores()