import os
import shutil
from fastapi import FastAPI, Depends, Query, File, UploadFile, Form, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database.models import Store, Discount, User, WatchlistItem
from core.database.session import SessionLocal
from pydantic import BaseModel

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../core/security'))
from auth import verify_firebase_token

# Import our new Vision Agent! Note: Adjust the import path if needed based on your folder structure
from apps.orchestrator.vision_agent import CrowdsourceVisionAgent

# Initialize the agent once when the server starts
vision_agent = CrowdsourceVisionAgent()

app = FastAPI(title="Dutch Discounts API", version="1.0")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/discounts/nearby")
def get_nearby_discounts(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
    radius_km: float = Query(5.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """
    Finds all active discounts within X kilometers of the user's GPS coordinates.
    """
    radius_meters = radius_km * 1000

    # 1. Construct the PostGIS Point from the user's Lat/Lng
    # PostGIS expects Longitude first, then Latitude! -> POINT(lng lat)
    user_location = f"SRID=4326;POINT({lng} {lat})"

    # 2. The Architectural Query
    # We join Discounts with Stores, and use ST_DWithin to filter by distance
    results = db.query(
        Discount.master_product_id,
        Discount.deal_type,
        Discount.deal_price,
        Discount.start_date,
        Discount.end_date,
        Store.chain_name,
        Store.address,
        # ST_Distance calculates the exact distance to the store in meters
        func.ST_Distance(Store.location, func.ST_GeographyFromText(user_location)).label("distance_meters")
    ).join(
        Store, Discount.store_id == Store.id
    ).filter(
        # ST_DWithin acts as a high-speed bounding box filter
        func.ST_DWithin(Store.location, func.ST_GeographyFromText(user_location), radius_meters)
    ).order_by(
        "distance_meters" # Closest stores first
    ).limit(100).all()

    # 3. Format for the Mobile App
    discounts_list = []
    for row in results:
        discounts_list.append({
            "product": row.master_product_id,
            "supermarket": row.chain_name,
            "address": row.address,
            "distance_km": round(row.distance_meters / 1000, 2),
            "deal_type": row.deal_type,
            "price": row.deal_price,
            "start_date": row.start_date,
            "end_date": row.end_date
        })

    return {"status": "success", "radius_km": radius_km, "data": discounts_list}


@app.post("/discounts/crowdsource")
async def crowdsource_discount(
    store_id: int = Form(..., description="The ID of the store the user is currently in"),
    lat: float = Form(..., description="User's current latitude for geofencing"),
    lng: float = Form(..., description="User's current longitude for geofencing"),
    image: UploadFile = File(..., description="Photo of the price tag"),
    db: Session = Depends(get_db),
    user_uid: str = Depends(verify_firebase_token)
):
    """
    Accepts a user-uploaded photo of a price tag, uses AI to extract the deal,
    and adds it to the database if the AI is highly confident.
    """
    # If the code reaches this line, the token is 100% valid.
    print(f"👤 Authenticated Upload from Firebase User: {user_uid}")

    # 🛡️ Defensive Check: Does this store actually exist?
    store_exists = db.query(Store).filter(Store.id == store_id).first()
    if not store_exists:
        raise HTTPException(status_code=404, detail=f"Store ID {store_id} does not exist in the database.")

    # 1. Save the uploaded image temporarily
    temp_file_path = f"temp_{image.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:
        # 2. Hand the image to the AI Agent
        ai_result = vision_agent.analyze_price_tag(temp_file_path)

        # 3. Decision Engine: Is the AI confident enough?
        confidence = ai_result.get("confidence_score", 0)

        if confidence < 80:
            # AI is confused. Reject it or send it to a human review queue.
            os.remove(temp_file_path)
            return {
                "status": "rejected",
                "message": "Image too blurry or no clear price found.",
                "ai_data": ai_result
            }

        # 4. Database Upsert! (The AI was confident)
        new_deal = Discount(
            master_product_id=ai_result.get("product_name", "Unknown").lower().replace(" ", "_"),
            store_id=store_id,
            deal_type=ai_result.get("deal_type", "UNKNOWN"),
            deal_price=ai_result.get("price", 0.0),
            # In a real app, we'd calculate start/end dates based on today
            # We would also set a flag like `is_verified = False`
        )

        db.add(new_deal)
        db.commit()

        # Clean up the temp image
        os.remove(temp_file_path)

        return {
            "status": "success",
            "message": "Deal successfully extracted and added to the database!",
            "deal_added": ai_result
        }

    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))

# 1. Pydantic schema for the incoming request
class WatchlistRequest(BaseModel):
    product_id: str

# 2. GET: Fetch the user's current watchlist
@app.get("/watchlist")
async def get_watchlist(
    db: Session = Depends(get_db),
    user_uid: str = Depends(verify_firebase_token)
):
    # Find the user by their Firebase UID
    user = db.query(User).filter(User.device_id == user_uid).first()
    if not user:
        return {"status": "success", "data": []}

    items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
    return {"status": "success", "data": [item.master_product_id for item in items]}

# 3. POST: Add an item to the watchlist
@app.post("/watchlist")
async def add_to_watchlist(
    request: WatchlistRequest,
    db: Session = Depends(get_db),
    user_uid: str = Depends(verify_firebase_token)
):
    # Ensure user exists in our DB
    user = db.query(User).filter(User.device_id == user_uid).first()
    if not user:
        user = User(device_id=user_uid)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Check if item already exists to prevent duplicates
    existing = db.query(WatchlistItem).filter(
        WatchlistItem.user_id == user.id,
        WatchlistItem.master_product_id == request.product_id
    ).first()

    if not existing:
        new_item = WatchlistItem(user_id=user.id, master_product_id=request.product_id)
        db.add(new_item)
        db.commit()

    return {"status": "success", "message": f"{request.product_id} added to watchlist."}

# 4. DELETE: Remove an item
@app.delete("/watchlist/{product_id}")
async def remove_from_watchlist(
    product_id: str,
    db: Session = Depends(get_db),
    user_uid: str = Depends(verify_firebase_token)
):
    user = db.query(User).filter(User.device_id == user_uid).first()
    if user:
        db.query(WatchlistItem).filter(
            WatchlistItem.user_id == user.id,
            WatchlistItem.master_product_id == product_id
        ).delete()
        db.commit()

    return {"status": "success", "message": "Item removed."}

class FCMTokenRequest(BaseModel):
    fcm_token: str

@app.put("/users/fcm-token")
async def update_fcm_token(
    request: FCMTokenRequest,
    db: Session = Depends(get_db),
    user_uid: str = Depends(verify_firebase_token)
):
    """Saves the user's physical device token for Push Notifications."""
    user = db.query(User).filter(User.device_id == user_uid).first()

    # If the user doesn't exist yet, create them!
    if not user:
        user = User(device_id=user_uid, fcm_token=request.fcm_token)
        db.add(user)
    else:
        user.fcm_token = request.fcm_token

    db.commit()
    return {"status": "success", "message": "Device token securely saved."}

# Pull a master password from the environment
CRON_SECRET = os.getenv("CRON_SECRET", "my-local-secret-123")

@app.post("/admin/trigger-notifications")
async def trigger_notifications(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Secure endpoint triggered daily by an external Cron service.
    """
    # 🛡️ THE CRON BOUNCER
    if authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized Cron Trigger")

    # 🚀 Run the Engine
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '../workers'))
    from notifier import SmartNotificationEngine

    engine = SmartNotificationEngine()
    engine.run_daily_digest(db)

    return {"status": "success", "message": "Daily notifications processed."}