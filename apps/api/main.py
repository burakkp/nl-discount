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
from firebase_admin import auth

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

@app.get("/healthz", tags=["ops"])
def health_check():
    """Render health-check endpoint. Returns 200 when the API is running."""
    return {"status": "ok", "version": "1.0"}

@app.get("/", tags=["ops"])
def root():
    return {"message": "Dutch Discounts API is live 🇳🇱", "docs": "/docs"}

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_optional_user_uid(authorization: Optional[str] = Header(None)):
    """
    Optional authentication: returns UID if valid token present, else None.
    Does not raise 401 if header is missing.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token.get("uid")
    except Exception:
        return None

import re

def _parse_slug(slug: str):
    """Extract a human-readable name and price pair from a product slug.
    E.g. 'ah_komkommer_los_van_1.7_voor_0.99' -> ('Komkommer Los', 1.70, 0.99)
    Handles both 'van X voor Y' and plain slugs.
    """
    m = re.search(r'van_([0-9]+[.,][0-9]+)_voor_([0-9]+[.,][0-9]+)', slug)
    old_price = float(m.group(1).replace(',', '.')) if m else None
    new_price = float(m.group(2).replace(',', '.')) if m else None

    name = re.sub(r'^(alle_)?(ah|jumbo|lidl|aldi|plus)_', '', slug, flags=re.IGNORECASE)
    name = re.sub(r'_van_[0-9.,]+_voor_[0-9.,]+$', '', name)
    name = name.replace('_', ' ').strip().title()
    name = re.sub(r'\(([^)]+)\)', lambda x: x.group(1).title(), name)

    return name, old_price, new_price

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
        Discount.original_price,
        Discount.unit_price,
        Discount.unit_label,
        Discount.start_date,
        Discount.end_date,
        Discount.image_url,
        Discount.description,
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
    ).limit(500).all()


    # 3. Format for the Mobile App
    discounts_list = []
    for row in results:
        slug = row.master_product_id or ''
        display_name, old_price, price_from_slug = _parse_slug(slug)
        price = row.deal_price if row.deal_price and row.deal_price > 0 else price_from_slug
        old_p = row.original_price if row.original_price else old_price

        discounts_list.append({
            "product": slug,
            "title": display_name,
            "supermarket": row.chain_name,
            "address": row.address,
            "distance_km": round(row.distance_meters / 1000, 2),
            "deal_type": row.deal_type,
            "price": price,
            "original_price": old_p,
            "unit_price": row.unit_price,
            "unit_label": row.unit_label,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "image_url": row.image_url,
            "description": row.description
        })

    return {"status": "success", "radius_km": radius_km, "data": discounts_list}


@app.get("/stores/nearby")
def get_nearby_stores(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
    radius_km: float = Query(5.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db),
    user_uid: Optional[str] = Depends(get_optional_user_uid)
):
    """
    Returns supermarkets within radius, enriched with watchlist hit counts if authenticated.
    """
    radius_meters = radius_km * 1000
    user_location = f"SRID=4326;POINT({lng} {lat})"
    today = date.today()

    # Find the user's DB ID if authenticated
    user_id = None
    if user_uid:
        user = db.query(User).filter(User.device_id == user_uid).first()
        if user:
            user_id = user.id

    # Core Query: Stores in radius
    # We use func.ST_AsText and some parsing or just func.ST_X/Y if available
    query = db.query(
        Store.id,
        Store.chain_name,
        Store.address,
        func.ST_Y(func.ST_AsText(Store.location)).label("lat_val"),
        func.ST_X(func.ST_AsText(Store.location)).label("lng_val"),
        func.ST_Distance(Store.location, func.ST_GeographyFromText(user_location)).label("distance_meters")
    ).filter(
        func.ST_DWithin(Store.location, func.ST_GeographyFromText(user_location), radius_meters)
    )

    stores = query.all()
    results = []

    for s in stores:
        # Calculate watchlist hits for this store
        hits = 0
        if user_id:
            hits = db.query(func.count(Discount.id)).join(
                WatchlistItem, WatchlistItem.master_product_id == Discount.master_product_id
            ).filter(
                Discount.store_id == s.id,
                WatchlistItem.user_id == user_id,
                Discount.start_date <= today,
                Discount.end_date >= today
            ).scalar()

        results.append({
            "id": s.id,
            "chain_name": s.chain_name,
            "address": s.address,
            "latitude": float(s.lat_val) if s.lat_val else 0.0,
            "longitude": float(s.lng_val) if s.lng_val else 0.0,
            "distance_km": round(s.distance_meters / 1000, 2),
            "watchlist_hits": hits
        })

    return {"status": "success", "data": results}


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


        try:
            confidence = int(ai_result.get("confidence_score", 0))
        except (ValueError, TypeError):
            confidence = 0

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
    query_str: str = Query(None, alias="query", description="Search for specific products"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Returns all active discounts for the current week."""
    today = date.today()
    # Rename to avoid shadowing the query-param `deal_type` inside the loop below
    deal_type_filter = deal_type

    # Only surface items that have EITHER a real price OR a known deal type we can label.
    # This must be done at the SQL level so pagination counts are accurate.
    from sqlalchemy import or_, and_, select
    LABELABLE_TYPES = ('BOGO', 'HALF_PRICE_2ND', 'PERCENTAGE', 'FIXED_AMOUNT',
                       'FIXED_BUNDLE', 'FIXED_PRICE', 'PER_UNIT', 'CLEARANCE',
                       'MULTI_BUY', 'FIXED_DISCOUNT')

    # Subquery to find the canonical (minimum) store ID for each chain
    canonical_stores_subq = select(func.min(Store.id)).group_by(Store.chain_name).scalar_subquery()

    query = db.query(Discount, Store).join(
        Store, Discount.store_id == Store.id
    ).filter(
        Discount.start_date <= today,
        Discount.end_date >= today,
        Discount.image_url.isnot(None),
        Store.id.in_(canonical_stores_subq),
        # Must have a price OR a deal type we can render a label for
        or_(
            and_(Discount.deal_price.isnot(None), Discount.deal_price > 0),
            Discount.deal_type.in_(LABELABLE_TYPES),
        ),
    )
    if store:
        query = query.filter(Store.chain_name.ilike(f"%{store}%"))
    if query_str:
        query = query.filter(Discount.master_product_id.ilike(f"%{query_str}%"))
    if deal_type_filter:
        query = query.filter(Discount.deal_type == deal_type_filter.upper())

    # Pagination logic
    offset = (page - 1) * page_size
    results = query.order_by(Discount.id.desc()).offset(offset).limit(page_size).all()

    data = []
    seen = set()
    for r in results:
        slug = r.Discount.master_product_id or ''
        deal_key = (r.Store.chain_name, slug)
        if deal_key in seen:
            continue
        seen.add(deal_key)

        display_name, old_price, price_from_slug = _parse_slug(slug)

        # Prefer DB-stored prices; fall back to parsed values from the slug
        price = r.Discount.deal_price if r.Discount.deal_price and r.Discount.deal_price > 0 else price_from_slug
        old_p = r.Discount.original_price if r.Discount.original_price else old_price

        # Build a human-readable deal label for items without a numeric price
        # (BOGO, percentage discounts, half-price — no base price on source page)
        deal_type = r.Discount.deal_type or 'UNKNOWN'
        deal_label = None
        if not price:
            if deal_type == 'BOGO':
                deal_label = '1+1 GRATIS'
            elif deal_type == 'HALF_PRICE_2ND':
                deal_label = '2e HALVE PRIJS'
            elif deal_type == 'PERCENTAGE':
                # unit_price stores the discount fraction (e.g. 0.25 = 25%)
                up = r.Discount.unit_price
                if up and up <= 1.0:
                    deal_label = f'{int(round(up * 100))}% KORTING'
                else:
                    deal_label = 'KORTING'
            elif deal_type == 'FIXED_AMOUNT' and r.Discount.unit_price:
                deal_label = f'\u20ac{r.Discount.unit_price:.2f} KORTING'
            elif deal_type not in ('UNKNOWN', None):
                deal_label = deal_type.replace('_', ' ')

        # Skip items with no numeric price AND no deal label — nothing to show
        if not price and not deal_label:
            continue

        import json as _json
        deal_options_parsed = []
        if r.Discount.deal_options:
            try:
                deal_options_parsed = _json.loads(r.Discount.deal_options)
            except Exception:
                pass

        data.append({
            "product": display_name,
            "product_slug": slug,
            "supermarket": r.Store.chain_name,
            "deal_type": deal_type,
            "deal_label": deal_label,
            "price": price,
            "old_price": old_p,
            "unit_price": r.Discount.unit_price,
            "unit_label": r.Discount.unit_label,
            "description": r.Discount.description,
            "deal_options": deal_options_parsed,   # [{qty:4, price:7.99}, {qty:6, price:10.99}]
            "image_url": r.Discount.image_url,
            "start_date": str(r.Discount.start_date),
            "end_date": str(r.Discount.end_date),
        })

    return {
        "status": "success",
        "week": str(today),
        "page": page,
        "page_size": page_size,
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