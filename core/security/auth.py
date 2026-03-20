from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth, credentials
import firebase_admin
import os
import json
from dotenv import load_dotenv

load_dotenv()

# 1. Setup the FastAPI Bearer Token schema
security = HTTPBearer()

# 2. Ensure Firebase is initialized (Idempotent check)
def initialize_firebase():
    if firebase_admin._apps:
        return  # Already initialised, skip.

    env = os.getenv("ENVIRONMENT", "DEV")

    try:
        if env == "DEV":
            # Local dev: load from the JSON file on disk.
            key_path = os.path.join(
                os.path.dirname(__file__), "firebase_dev.json"
            )
            cred = credentials.Certificate(key_path)
        else:
            # Production / Render: load from the JSON string stored in an env var.
            # Set FIREBASE_CREDENTIALS_JSON to the *contents* of your service-account JSON.
            cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if not cred_json:
                raise ValueError(
                    "FIREBASE_CREDENTIALS_JSON env var is not set. "
                    "Paste the service-account JSON as its value in Render's environment settings."
                )
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)

        firebase_admin.initialize_app(cred)
        print("🔐 Firebase Auth initialised successfully.")
    except Exception as e:
        print(f"🚨 CRITICAL: Could not initialise Firebase for Auth: {e}")

initialize_firebase()

# 3. The Core Dependency (The Bouncer)
def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verifies the JWT token sent by the mobile app.
    Returns the Firebase User ID (UID) if valid.
    """
    token = credentials.credentials
    
    try:
        # firebase_admin.auth reaches out to Google (or uses cached keys) to verify the signature
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        
        # You can also extract the user's email or phone number here if needed!
        # email = decoded_token.get("email")
        
        return uid
        
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature. Access denied.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )