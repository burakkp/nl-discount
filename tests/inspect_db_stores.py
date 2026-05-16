# tests/inspect_db_stores.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database.session import SessionLocal
from core.database.models import Store
from sqlalchemy import func

def inspect_stores():
    db = SessionLocal()
    stores = db.query(
        Store.id,
        Store.chain_name,
        Store.address,
        func.ST_AsText(Store.location).label("loc")
    ).all()
    
    print(f"Total stores in DB: {len(stores)}")
    for s in stores:
        print(f"ID: {s.id} | Chain: {s.chain_name} | Address: {s.address} | Loc: {s.loc}")
    db.close()

if __name__ == "__main__":
    inspect_stores()
