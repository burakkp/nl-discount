from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database.models import Store, Discount
from core.database.session import SessionLocal

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