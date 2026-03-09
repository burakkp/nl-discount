from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Store, Discount

# Adjust to your exact DB URL
DATABASE_URL = "postgresql://admin:password123@localhost:5432/discount_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def inject_test_discount():
    db = SessionLocal()
    
    print("🔍 Looking for the Tiel Albert Heijn...")
    # Find the store we seeded earlier
    ah_store = db.query(Store).filter(Store.address == "Waterstraat 68, Tiel").first()
    
    if not ah_store:
        print("❌ Could not find the store. Did the store seeder run correctly?")
        return

    print(f"✅ Found store: {ah_store.chain_name} (ID: {ah_store.id})")
    
    # Check if the discount is already there
    existing_deal = db.query(Discount).filter(Discount.store_id == ah_store.id).first()
    if not existing_deal:
        print("🛒 Injecting 'Test Komkommer' discount...")
        test_discount = Discount(
            master_product_id="cat_komkommer_01",
            store_id=ah_store.id,
            deal_type="FIXED_PRICE",
            deal_price=0.99,
            unit_price=0.99
        )
        db.add(test_discount)
        db.commit()
        print("✅ Discount successfully injected into the database!")
    else:
        print("✅ Discount already exists in this store.")
        
    db.close()

if __name__ == "__main__":
    inject_test_discount()