from sqlalchemy import Column, String, Float, Integer, ForeignKey, Boolean, Date
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
    unit_price = Column(Float)       # 1.245

    start_date = Column(Date)
    end_date = Column(Date)
    
    store = relationship("Store", back_populates="discounts")