# tests/test_api_projection.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_nearby_discounts_projection():
    # Test coordinates in Amsterdam (near Westerstraat Jumbo / Albert Heijn)
    response = client.get("/discounts/nearby?lat=52.378&lng=4.885&radius_km=5.0")
    assert response.status_code == 200, f"API failed with {response.status_code}"
    
    data = response.json().get("data", [])
    assert len(data) > 0, "No nearby discounts found for test coordinates"
    
    # Check that the first item has the enriched fields
    first = data[0]
    assert "title" in first, "Field 'title' missing from projection"
    assert "image_url" in first, "Field 'image_url' missing from projection"
    assert "description" in first, "Field 'description' missing from projection"
    
    # Check that title is clean (not a raw slug)
    assert "_" not in first["title"], f"Title '{first['title']}' appears to be a raw slug!"
    
    print("✅ test_nearby_discounts_projection PASSED")

if __name__ == "__main__":
    test_nearby_discounts_projection()
