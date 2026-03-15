import requests
import os
from dotenv import load_dotenv

load_dotenv()

# 🚨 PASTE YOUR FIREBASE WEB API KEY HERE
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

def get_test_token():
    print("📱 Simulating Mobile App Login...")
    
    # This hits Google's Identity Toolkit to create an anonymous user and get a token
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    payload = {"returnSecureToken": True}
    
    response = requests.post(url, json=payload)
    data = response.json()
    
    if "idToken" in data:
        print("\n✅ Login Successful! Here is your Mobile App JWT Token:\n")
        print("Bearer " + data["idToken"])
        print("\n📋 Copy the token (WITHOUT the word 'Bearer ') and paste it into Swagger UI!")
    else:
        print(f"❌ Error getting token: {data}")

if __name__ == "__main__":
    get_test_token()