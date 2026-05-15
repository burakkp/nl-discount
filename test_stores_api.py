import requests

def test_stores_nearby():
    base_url = "http://localhost:8000" # Assuming backend is running locally
    params = {
        "lat": 51.88,
        "lng": 5.43,
        "radius_km": 10
    }
    try:
        response = requests.get(f"{base_url}/stores/nearby", params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_stores_nearby()
