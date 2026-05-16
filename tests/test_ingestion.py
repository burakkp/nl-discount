# tests/test_ingestion.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database.session import SessionLocal
from core.database.models import Store, Discount

def test_multi_store_ingestion():
    db = SessionLocal()
    # Check Jumbo stores in Amsterdam and Tiel
    jumbo_stores = db.query(Store).filter(Store.chain_name.ilike("Jumbo")).all()
    assert len(jumbo_stores) >= 2, "Need at least 2 Jumbo stores for test"
    
    for s in jumbo_stores:
        cnt = db.query(Discount).filter(Discount.store_id == s.id).count()
        assert cnt > 0, f"Jumbo store {s.id} ({s.address}) has 0 deals! Multi-store ingestion failed."
    db.close()
    print("✅ test_multi_store_ingestion PASSED")

if __name__ == "__main__":
    test_multi_store_ingestion()
