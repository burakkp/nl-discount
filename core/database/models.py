from sqlalchemy import Column, String, Float, Integer, ForeignKey, Boolean, Date, Text
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geography

Base = declarative_base()

class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    chain_name = Column(String, index=True) # AH, Jumbo, Lidl
    address = Column(String)
    city = Column(String)

    # The Magic Column: PostGIS Geography point (Longitude, Latitude)
    location = Column(Geography(geometry_type='POINT', srid=4326))

    discounts = relationship("Discount", back_populates="store")

class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True, index=True)
    master_product_id = Column(String, index=True) # e.g., "cat_komkommer_01"
    store_id = Column(Integer, ForeignKey("stores.id"))

    deal_type = Column(String)       # "MULTI_BUY", "PERCENTAGE", etc.
    deal_price = Column(Float)       # 2.49
    original_price = Column(Float)   # 3.99 (the "van" price)
    unit_price = Column(Float)       # 1.245 (price per unit in bundle)
    unit_label = Column(String)      # "500g", "per stuk", "per kilo"
    image_url = Column(String)       # Direct URL to the product image
    description = Column(Text)       # Full deal description text from card
    deal_options = Column(Text)      # JSON: [{"qty": 4, "price": 7.99}, ...] for multi-tier deals

    start_date = Column(Date)
    end_date = Column(Date)

    store = relationship("Store", back_populates="discounts")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True) # Firebase UID

    fcm_token = Column(String, nullable=True)

    # Relationships
    watchlists = relationship("WatchlistItem", back_populates="user")

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    master_product_id = Column(String)

    # Relationships
    user = relationship("User", back_populates="watchlists")