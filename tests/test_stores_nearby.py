# tests/test_stores_nearby.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_stores_nearby():
    response = client.get("/stores/nearby?lat=52.378&lng=4.885&radius_km=5.0")
    assert response.status_code == 200, f"API failed with {response.status_code}"
    
    data = response.json().get("data", [])
    assert len(data) > 0, "No stores found"
    
    for store in data[:5]:
        print(f"Store: {store['chain_name']} | Lat: {store['latitude']} | Lng: {store['longitude']}")

if __name__ == "__main__":
    test_stores_nearby()
