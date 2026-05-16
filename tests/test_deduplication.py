# tests/test_deduplication.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_this_week_deduplication():
    # Fetch top 50 deals from the this-week feed
    response = client.get("/discounts/this-week?page=1&page_size=50")
    assert response.status_code == 200, f"API failed with {response.status_code}"
    
    data = response.json().get("data", [])
    assert len(data) > 0, "No deals found in this-week feed"
    
    # Collect unique deal identifiers (supermarket + product_slug)
    # This ensures that multi-store replication doesn't produce duplicate entries for the same chain's deal
    deal_ids = [(item["supermarket"], item["product_slug"]) for item in data]
    unique_deal_ids = set(deal_ids)
    
    # Assert no duplicates from store replication
    assert len(deal_ids) == len(unique_deal_ids), f"Found duplicate store replicated deals in home feed! Total: {len(deal_ids)}, Unique: {len(unique_deal_ids)}"
    print("✅ test_this_week_deduplication PASSED")

if __name__ == "__main__":
    test_this_week_deduplication()
