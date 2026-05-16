from datetime import date
from typing import Any, List, Optional
from sqlalchemy import String, Float, Integer, ForeignKey, Boolean, Date, Text
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from geoalchemy2 import Geography

Base = declarative_base()

class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chain_name: Mapped[Optional[str]] = mapped_column(String, index=True) # AH, Jumbo, Lidl
    address: Mapped[Optional[str]] = mapped_column(String)
    city: Mapped[Optional[str]] = mapped_column(String)

    # The Magic Column: PostGIS Geography point (Longitude, Latitude)
    location: Mapped[Any] = mapped_column(Geography(geometry_type='POINT', srid=4326))

    discounts: Mapped[List["Discount"]] = relationship("Discount", back_populates="store")

class Discount(Base):
    __tablename__ = "discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    master_product_id: Mapped[Optional[str]] = mapped_column(String, index=True) # e.g., "cat_komkommer_01"
    store_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("stores.id"))

    deal_type: Mapped[Optional[str]] = mapped_column(String)       # "MULTI_BUY", "PERCENTAGE", etc.
    deal_price: Mapped[Optional[float]] = mapped_column(Float)       # 2.49
    original_price: Mapped[Optional[float]] = mapped_column(Float)   # 3.99 (the "van" price)
    unit_price: Mapped[Optional[float]] = mapped_column(Float)       # 1.245 (price per unit in bundle)
    unit_label: Mapped[Optional[str]] = mapped_column(String)      # "500g", "per stuk", "per kilo"
    image_url: Mapped[Optional[str]] = mapped_column(String)       # Direct URL to the product image
    description: Mapped[Optional[str]] = mapped_column(Text)       # Full deal description text from card
    deal_options: Mapped[Optional[str]] = mapped_column(Text)      # JSON: [{"qty": 4, "price": 7.99}, ...] for multi-tier deals

    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)

    store: Mapped[Optional["Store"]] = relationship("Store", back_populates="discounts")

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True) # Firebase UID

    fcm_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    watchlists: Mapped[List["WatchlistItem"]] = relationship("WatchlistItem", back_populates="user")

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    master_product_id: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="watchlists")