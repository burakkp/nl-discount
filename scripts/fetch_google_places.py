import sys
import os
import requests

sys.path.insert(0, "/home/burakkp/Documents/Projects/nederland-discounts")
from core.database.session import SessionLocal
from core.database.models import Store

def get_api_key():
    try:
        with open("/home/burakkp/Documents/Projects/nederland-discounts/.env", "r") as f:
            for line in f:
                if line.startswith("GOOGLE_PLACES_API_KEY="):
                    return line.strip().split("=", 1)[1]
    except FileNotFoundError:
        pass
    return None

def fetch_google_places():
    api_key = get_api_key()
    if not api_key:
        print("❌ Could not find MAPS_API_KEY in local.properties")
        return

    db = SessionLocal()
    chains = ["Albert Heijn", "Jumbo", "Aldi", "Lidl", "PLUS"]
    cities = ["Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven", "Tiel"]
    
    print("🌍 Fetching REAL supermarket locations from Google Places API...")

    total_added = 0

    for chain in chains:
        for city in cities:
            query = f"{chain} in {city}, Netherlands"
            url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query}&key={api_key}"
            
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    print(f"⚠️ No results for {chain} in {city}. API Response: {data.get('status')} - {data.get('error_message', '')}")
                    
                added = 0
                for place in results:
                    lat = place['geometry']['location']['lat']
                    lng = place['geometry']['location']['lng']
                    address = place.get('formatted_address', '')
                    
                    # Avoid duplicates
                    existing = db.query(Store).filter(Store.address == address).first()
                    if not existing:
                        new_store = Store(
                            chain_name=chain,
                            address=address,
                            location=f"SRID=4326;POINT({lng} {lat})"
                        )
                        db.add(new_store)
                        added += 1
                        total_added += 1
                
                db.commit()
                print(f"✅ Found {len(results)} ({added} new) locations for {chain} in {city}")
            else:
                print(f"❌ Failed to fetch {chain} in {city}: {response.status_code}")

    print(f"🚀 Successfully imported {total_added} authentic store locations from Google Maps!")
    db.close()

if __name__ == "__main__":
    fetch_google_places()
