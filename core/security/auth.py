from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth, credentials
import firebase_admin
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Setup the FastAPI Bearer Token schema
security = HTTPBearer()

# 2. Ensure Firebase is initialized (Idempotent check just like before)
def initialize_firebase():
    if not firebase_admin._apps:
        env = os.getenv("ENVIRONMENT", "DEV")
        key_path = "core/security/firebase_dev.json" if env == "DEV" else "core/security/firebase_prod.json"
        
        try:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            print("🔐 Firebase Auth initialized for FastAPI.")
        except Exception as e:
            print(f"🚨 CRITICAL: Could not initialize Firebase for Auth: {e}")

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