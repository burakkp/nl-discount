import sys
import os
import requests

sys.path.insert(0, "/home/burakkp/Documents/Projects/nederland-discounts")
from core.database.session import SessionLocal
from core.database.models import Store

def fetch_real_stores():
    db = SessionLocal()

    # First, let's delete the fake stores we just added
    # We will keep the original ones that have deals attached to them
    # Actually, we can just delete stores that have "Centrum, " in address as those are our fakes
    fakes = db.query(Store).filter(Store.address.like("Centrum, %")).all()
    for f in fakes:
        db.delete(f)
    db.commit()

    # Define chains to search
    chains = ["Albert Heijn", "Jumbo", "Aldi", "Lidl", "PLUS"]

    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # We will grab around Amsterdam, Rotterdam, Utrecht, and Tiel
    # Bounding box around NL roughly: 50.7, 3.3, 53.5, 7.2
    # To keep it fast, we'll just query the whole country but limit to 100 per chain
    
    print("🌍 Fetching REAL supermarket locations from OpenStreetMap...")
    
    for chain in chains:
        query = f"""
        [out:json][timeout:25];
        area["name"="Nederland"]->.searchArea;
        (
          node["shop"="supermarket"]["name"~"{chain}", i](area.searchArea);
        );
        out 50;
        """
        headers = {"User-Agent": "NederlandDiscountsApp/1.0 (test@example.com)"}
        response = requests.get(overpass_url, params={'data': query}, headers=headers)
        if response.status_code == 200:
            data = response.json()
            nodes = data.get('elements', [])
            print(f"✅ Found {len(nodes)} real locations for {chain}")
            
            for node in nodes:
                lat = node.get('lat')
                lon = node.get('lon')
                tags = node.get('tags', {})
                name = tags.get('name', chain)
                street = tags.get('addr:street', '')
                housenumber = tags.get('addr:housenumber', '')
                city = tags.get('addr:city', '')
                
                address = f"{street} {housenumber}, {city}".strip(", ")
                if not address:
                    address = city if city else "Nederland"
                
                # Check if exists
                existing = db.query(Store).filter(Store.chain_name == chain, Store.address == address).first()
                if not existing:
                    new_store = Store(
                        chain_name=chain,
                        address=address,
                        location=f"SRID=4326;POINT({lon} {lat})"
                    )
                    db.add(new_store)
            db.commit()
        else:
            print(f"❌ Failed to fetch {chain}: {response.status_code}")

    print("🚀 All real locations saved to database!")
    db.close()

if __name__ == "__main__":
    fetch_real_stores()
