import sys
import os
sys.path.insert(0, "/home/burakkp/Documents/Projects/nederland-discounts")
from core.database.session import SessionLocal
from core.database.models import Store
from sqlalchemy import func
from typing import TypedDict

class CityDict(TypedDict):
    name: str
    lat: float
    lng: float

def seed_stores():
    db = SessionLocal()
    
    # Base cities
    cities: list[CityDict] = [
        {"name": "Amsterdam", "lat": 52.3676, "lng": 4.9041},
        {"name": "Rotterdam", "lat": 51.9225, "lng": 4.47917},
        {"name": "Utrecht", "lat": 52.0907, "lng": 5.1214},
        {"name": "Den Haag", "lat": 52.0705, "lng": 4.3007},
        {"name": "Eindhoven", "lat": 51.4416, "lng": 5.4697},
        {"name": "Tiel", "lat": 51.8841, "lng": 5.4278},
        {"name": "Groningen", "lat": 53.2194, "lng": 6.5665},
    ]
    
    chains = ["Albert Heijn", "Jumbo", "Aldi", "Lidl", "Plus"]
    
    # 1. Give the existing empty stores a location in Amsterdam so they don't break
    empty_stores = db.query(Store).filter(Store.location == None).all()
    for s in empty_stores:
        s.address = "Centrum, Amsterdam"
        s.location = f"SRID=4326;POINT(4.9041 52.3676)"
    
    db.commit()
    
    # 2. Add stores for every chain in every city
    for city in cities:
        # Create a slight offset for each chain so they don't overlap exactly
        offsets = {
            "Albert Heijn": (0.001, 0.001),
            "Jumbo": (-0.001, 0.002),
            "Aldi": (0.002, -0.001),
            "Lidl": (-0.002, -0.002),
            "Plus": (0.003, 0.001),
        }
        
        for chain in chains:
            lat = city["lat"] + offsets[chain][0]
            lng = city["lng"] + offsets[chain][1]
            
            # Check if this specific store exists to avoid duplicates
            addr = f"Centrum, {city['name']}"
            existing = db.query(Store).filter(Store.chain_name == chain, Store.address == addr).first()
            if not existing:
                new_store = Store(
                    chain_name=chain,
                    address=addr,
                    location=f"SRID=4326;POINT({lng} {lat})"
                )
                db.add(new_store)
                
    db.commit()
    print("✅ Seeded comprehensive store locations across the Netherlands!")
    db.close()

if __name__ == "__main__":
    seed_stores()
