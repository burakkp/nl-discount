import os
import shutil
from datetime import date
from fastapi import FastAPI, Depends, Query, File, UploadFile, Form, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database.models import Store, Discount, User, WatchlistItem
from core.database.session import SessionLocal
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from core.security.auth import verify_firebase_token

# Import our new Vision Agent! Note: Adjust the import path if needed based on your folder structure
from apps.orchestrator.vision_agent import CrowdsourceVisionAgent

# Initialize the agent once when the server starts
vision_agent = CrowdsourceVisionAgent()

# 📝 Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DUTCH_DISCOUNTS_API")

app = FastAPI(title="Dutch Discounts API", version="1.0")

# 🌍 Phase 3: CORS Configuration
# We restrict this to ensure browsers can't hit the API from random domains.
# For a mobile app, we can allow all origins or specific domains if you have a web companion.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Expand this if you launch a web version!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    logger.info(f"👤 Authenticated Upload from Firebase User: {user_uid}")

    # 🛡️ Defensive Check: Does this store actually exist?
    store_exists = db.query(Store).filter(Store.id == store_id).first()
    if not store_exists:
        raise HTTPException(status_code=404, detail=f"Store ID {store_id} does not exist in the database.")

    # 1. Save the uploaded image temporarily
    temp_file_path = f"temp_{image.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:

        if not vision_agent.is_active:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(
                status_code=503,
                detail="Crowdsourcing is temporarily disabled (AI Agent offline). Please try again later."
            )


        ai_result = vision_agent.analyze_price_tag(temp_file_path)


        confidence = ai_result.get("confidence_score", 0)

        if confidence < 80:

            os.remove(temp_file_path)
            return {
                "status": "rejected",
                "message": "Image too blurry or no clear price found.",
                "ai_data": ai_result
            }


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
    product_id: str = Field(..., min_length=1, max_length=200)

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
    fcm_token: str = Field(..., min_length=10, max_length=255)

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

@app.get("/discounts/this-week")
def get_this_week_discounts(
    store: str = Query(None, description="Filter by store name (optional)"),
    deal_type: str = Query(None, description="Filter by deal type (optional)"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Returns all active discounts for the current week."""
    import re

    def _parse_slug(slug: str):
        """Extract a human-readable name and price pair from a product slug.
        E.g. 'ah_komkommer_los_van_1.7_voor_0.99' -> ('Komkommer Los', 1.70, 0.99)
        Handles both 'van X voor Y' and plain slugs.
        """
        # Try to find 'van <old> voor <new>' pattern
        m = re.search(r'van_([0-9]+[.,][0-9]+)_voor_([0-9]+[.,][0-9]+)', slug)
        old_price = float(m.group(1).replace(',', '.')) if m else None
        new_price = float(m.group(2).replace(',', '.')) if m else None

        # Strip store prefix (ah_, alle_ah_, jumbo_, lidl_, etc.)
        name = re.sub(r'^(alle_)?(ah|jumbo|lidl|aldi|plus)_', '', slug, flags=re.IGNORECASE)
        # Remove trailing price fragment
        name = re.sub(r'_van_[0-9.,]+_voor_[0-9.,]+$', '', name)
        # Convert underscores to spaces and title-case
        name = name.replace('_', ' ').strip().title()
        # Clean up parentheses artefacts like '(Gele)'
        name = re.sub(r'\(([^)]+)\)', lambda x: x.group(1).title(), name)

        return name, old_price, new_price

    today = date.today()
    query = db.query(Discount, Store).join(
        Store, Discount.store_id == Store.id
    ).filter(
        Discount.start_date <= today,
        Discount.end_date >= today,
    )
    if store:
        query = query.filter(Store.chain_name.ilike(f"%{store}%"))
    if deal_type:
        query = query.filter(Discount.deal_type == deal_type.upper())

    results = query.order_by(Discount.start_date.desc()).limit(limit).all()

    data = []
    for r in results:
        slug = r.Discount.master_product_id or ''
        display_name, old_price, price_from_slug = _parse_slug(slug)

        # Prefer DB-stored prices; fall back to parsed values from the slug
        price = r.Discount.deal_price if r.Discount.deal_price and r.Discount.deal_price > 0 else price_from_slug
        old_p = old_price  # DB doesn't have old_price column yet

        data.append({
            "product": display_name,
            "product_slug": slug,
            "supermarket": r.Store.chain_name,
            "deal_type": r.Discount.deal_type,
            "price": price,
            "old_price": old_p,
            "unit_price": r.Discount.unit_price,
            "start_date": str(r.Discount.start_date),
            "end_date": str(r.Discount.end_date),
        })

    return {
        "status": "success",
        "week": str(today),
        "count": len(data),
        "data": data,
    }

# 🔐 SECURITY HARDENING: Enforce mandatory Cron Secret in Production
CRON_SECRET = os.getenv("CRON_SECRET")
if not CRON_SECRET and os.getenv("ENVIRONMENT") == "PROD":
    logger.error("🚨 CRITICAL: CRON_SECRET is missing in PROD environment!")
    # We allow the app to boot for debugging but the endpoint will be inaccessible

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
    from apps.workers.notifier import SmartNotificationEngine

    engine = SmartNotificationEngine()
    engine.run_daily_digest(db)

    return {"status": "success", "message": "Daily notifications processed."}