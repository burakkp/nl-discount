import sys
import os

sys.path.insert(0, "/home/burakkp/Documents/Projects/nederland-discounts")
from core.database.session import SessionLocal
from core.database.models import Store

def seed_real_stores():
    db = SessionLocal()

    # Clear old fakes
    fakes = db.query(Store).filter(Store.address.ilike("%Centrum, %")).all()
    for f in fakes:
        db.delete(f)
    db.commit()

    real_stores = [
        # Amsterdam Real Locations
        {"chain_name": "Albert Heijn", "address": "Jodenbreestraat 21, Amsterdam", "lat": 52.3694, "lng": 4.9036},
        {"chain_name": "Albert Heijn", "address": "Prinsengracht 691, Amsterdam", "lat": 52.3621, "lng": 4.8885},
        {"chain_name": "Jumbo", "address": "Jodenbreestraat 17, Amsterdam", "lat": 52.3698, "lng": 4.9040},
        {"chain_name": "Jumbo", "address": "Westerstraat 98, Amsterdam", "lat": 52.3789, "lng": 4.8824},
        {"chain_name": "Aldi", "address": "Nieuwe Weteringstraat 24-28, Amsterdam", "lat": 52.3596, "lng": 4.8911},
        {"chain_name": "Lidl", "address": "Hobbemakade 29, Amsterdam", "lat": 52.3551, "lng": 4.8879},
        {"chain_name": "Lidl", "address": "Elandsgracht 44, Amsterdam", "lat": 52.3688, "lng": 4.8787},
        {"chain_name": "Plus", "address": "Zeilstraat 40, Amsterdam", "lat": 52.3486, "lng": 4.8722},

        # Tiel Real Locations
        {"chain_name": "Albert Heijn", "address": "Waterstraat 68, Tiel", "lat": 51.8841, "lng": 5.4278},
        {"chain_name": "Jumbo", "address": "Hertog Arnoldstraat 1, Tiel", "lat": 51.8888, "lng": 5.4350},
        {"chain_name": "Aldi", "address": "Teisterbantlaan 2, Tiel", "lat": 51.8906, "lng": 5.4373},
        {"chain_name": "Lidl", "address": "Oude Haven 5, Tiel", "lat": 51.8858, "lng": 5.4215},
        {"chain_name": "Plus", "address": "Burgemeester Schullstraat 2, Tiel", "lat": 51.8864, "lng": 5.4312},
    ]

    for store in real_stores:
        existing = db.query(Store).filter(Store.address == store["address"]).first()
        if not existing:
            new_store = Store(
                chain_name=store["chain_name"],
                address=store["address"],
                location=f"SRID=4326;POINT({store['lng']} {store['lat']})"
            )
            db.add(new_store)
        else:
            existing.location = f"SRID=4326;POINT({store['lng']} {store['lat']})"
            
    db.commit()
    
    # Finally, link missing location existing stores so they dont break code
    # e.g., the blank ones created by ingest_all
    empty_stores = db.query(Store).filter(Store.location == None).all()
    for s in empty_stores:
        # Just stick them to Amsterdam centroid to avoid SQL errors
        s.address = "Amsterdam"
        s.location = f"SRID=4326;POINT(4.9041 52.3676)"
    db.commit()

    print("🚀 Real locations inserted!")
    db.close()

if __name__ == "__main__":
    seed_real_stores()
