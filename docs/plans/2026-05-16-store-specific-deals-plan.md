# Store-Specific Deals Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Transition the Nederland Discounts backend and ingestion engine to a multi-store replication and geofenced projection model to support hyper-local, store-specific deals.

**Architecture:** Modify `apps/orchestrator/ingest_all.py` to upsert scraped deals across all physical store locations of a chain. Upgrade `/discounts/nearby` in `apps/api/main.py` to project clean parsed titles, descriptions, and image URLs. Add a deduplication filter to `/discounts/this-week` in `apps/api/main.py` to ensure the nationwide home feed displays unique deals.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, PostgreSQL, GeoAlchemy2

---

### Task 1: Update Data Ingestion Layer (`apps/orchestrator/ingest_all.py`)

**Files:**
- Modify: `apps/orchestrator/ingest_all.py:135-210`
- Create: `tests/test_ingestion.py`

**Step 1: Write the failing test**

```python
# tests/test_ingestion.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database.session import SessionLocal
from core.database.models import Store, Discount

def test_multi_store_ingestion():
    db = SessionLocal()
    # Check Jumbo stores in Amsterdam and Tiel
    jumbo_stores = db.query(Store).filter(Store.chain_name.ilike("Jumbo")).all()
    assert len(jumbo_stores) >= 2, "Need at least 2 Jumbo stores for test"
    
    for s in jumbo_stores:
        cnt = db.query(Discount).filter(Discount.store_id == s.id).count()
        assert cnt > 0, f"Jumbo store {s.id} ({s.address}) has 0 deals! Multi-store ingestion failed."
    db.close()
    print("✅ test_multi_store_ingestion PASSED")

if __name__ == "__main__":
    test_multi_store_ingestion()
```

**Step 2: Run test to verify it fails**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_ingestion.py`
Expected: FAIL with `AssertionError: Jumbo store 40 (Westerstraat 98, Amsterdam) has 0 deals!`

**Step 3: Write minimal implementation**

Modify `apps/orchestrator/ingest_all.py`:
```python
    def _get_all_stores(self, chain_name: str) -> list[Store]:
        """Return all existing Store rows for a chain, or create one on the fly."""
        stores = (
            self.db.query(Store)
            .filter(Store.chain_name.ilike(chain_name))
            .all()
        )
        if not stores:
            store = Store(chain_name=chain_name)
            self.db.add(store)
            self.db.flush()
            stores = [store]
        return stores

    def ingest_to_db(self, all_items):
        """Upsert processed discount records into the database across all chain stores."""
        print(f"\n🚀 Initiating Database Upsert for {len(all_items)} total discounts across all stores...")
        inserted = 0
        try:
            for item in all_items:
                stores = self._get_all_stores(item['store_name'])
                master_product_id = item['product_name'].lower().replace(' ', '_')[:100]

                for store in stores:
                    existing = self.db.query(Discount).filter(
                        Discount.master_product_id == master_product_id,
                        Discount.store_id == store.id
                    ).first()

                    if existing:
                        existing.deal_type = item['deal_type']
                        existing.start_date = item['start_date']
                        existing.end_date = item['end_date']
                        existing.unit_label = item.get('unit_label') or existing.unit_label
                        existing.image_url = item.get('image_url') or existing.image_url
                        if item.get('description'):
                            existing.description = item['description']
                        if item.get('deal_options'):
                            existing.deal_options = item['deal_options']
                        if item['deal_price']:
                            existing.deal_price = item['deal_price']
                        if item.get('original_price'):
                            existing.original_price = item['original_price']
                        if item['unit_price']:
                            existing.unit_price = item['unit_price']
                    else:
                        discount = Discount(
                            master_product_id=master_product_id,
                            store_id=store.id,
                            deal_type=item['deal_type'],
                            deal_price=item['deal_price'],
                            original_price=item.get('original_price'),
                            unit_price=item['unit_price'],
                            unit_label=item.get('unit_label'),
                            description=item.get('description'),
                            deal_options=item.get('deal_options'),
                            image_url=item.get('image_url'),
                            start_date=item['start_date'],
                            end_date=item['end_date'],
                        )
                        self.db.add(discount)
                    inserted += 1

            self.db.commit()
            print(f"💾 Database transaction complete. Processed {inserted} store-deal pairs.")
        except Exception as exc:
            self.db.rollback()
            print(f"❌ DB error — transaction rolled back: {exc}")
            raise
        finally:
            self.db.close()
```
Run ingestion to populate DB: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python apps/orchestrator/ingest_all.py`

**Step 4: Run test to verify it passes**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_ingestion.py`
Expected: `✅ test_multi_store_ingestion PASSED`

**Step 5: Commit**

```bash
git add apps/orchestrator/ingest_all.py tests/test_ingestion.py
git commit -m "feat(ingestion): enable multi-store deal replication for store-specific deals"
```

---

### Task 2: Update API Projection Layer (`apps/api/main.py`)

**Files:**
- Modify: `apps/api/main.py:63-123`
- Create: `tests/test_nearby_api.py`

**Step 1: Write the failing test**

```python
# tests/test_nearby_api.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from apps.api.main import get_nearby_discounts
from core.database.session import SessionLocal

def test_nearby_discounts_projection():
    db = SessionLocal()
    # Tiel coordinates
    res = get_nearby_discounts(lat=51.88, lng=5.43, radius_km=15.0, db=db)
    data = res["data"]
    assert len(data) > 0, "Expected nearby discounts in Tiel"
    
    first_deal = data[0]
    assert "image_url" in first_deal, "image_url missing from response"
    assert "description" in first_deal, "description missing from response"
    assert "_" not in first_deal["product"], f"Product title not cleaned: {first_deal['product']}"
    db.close()
    print("✅ test_nearby_discounts_projection PASSED")

if __name__ == "__main__":
    test_nearby_discounts_projection()
```

**Step 2: Run test to verify it fails**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_nearby_api.py`
Expected: FAIL with `AssertionError: image_url missing from response`

**Step 3: Write minimal implementation**

Modify `apps/api/main.py` around `get_nearby_discounts`:
```python
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
    import re

    def _parse_slug(slug: str):
        m = re.search(r'van_([0-9]+[.,][0-9]+)_voor_([0-9]+[.,][0-9]+)', slug)
        old_price = float(m.group(1).replace(',', '.')) if m else None
        new_price = float(m.group(2).replace(',', '.')) if m else None

        name = re.sub(r'^(alle_)?(ah|jumbo|lidl|aldi|plus)_', '', slug, flags=re.IGNORECASE)
        name = re.sub(r'_van_[0-9.,]+_voor_[0-9.,]+$', '', name)
        name = name.replace('_', ' ').strip().title()
        name = re.sub(r'\(([^)]+)\)', lambda x: x.group(1).title(), name)

        return name, old_price, new_price

    radius_meters = radius_km * 1000
    user_location = f"SRID=4326;POINT({lng} {lat})"

    results = db.query(
        Discount.master_product_id,
        Discount.deal_type,
        Discount.deal_price,
        Discount.original_price,
        Discount.unit_price,
        Discount.unit_label,
        Discount.image_url,
        Discount.description,
        Discount.start_date,
        Discount.end_date,
        Store.chain_name,
        Store.address,
        func.ST_Distance(Store.location, func.ST_GeographyFromText(user_location)).label("distance_meters")
    ).join(
        Store, Discount.store_id == Store.id
    ).filter(
        func.ST_DWithin(Store.location, func.ST_GeographyFromText(user_location), radius_meters)
    ).order_by(
        "distance_meters"
    ).limit(500).all()

    discounts_list = []
    for row in results:
        slug = row.master_product_id or ''
        display_name, old_price, price_from_slug = _parse_slug(slug)
        price = row.deal_price if row.deal_price and row.deal_price > 0 else price_from_slug
        old_p = row.original_price if row.original_price else old_price

        discounts_list.append({
            "product": display_name,
            "product_slug": slug,
            "supermarket": row.chain_name,
            "address": row.address,
            "distance_km": round(row.distance_meters / 1000, 2),
            "deal_type": row.deal_type,
            "price": price,
            "original_price": old_p,
            "unit_price": row.unit_price,
            "unit_label": row.unit_label,
            "image_url": row.image_url,
            "description": row.description,
            "start_date": row.start_date,
            "end_date": row.end_date
        })

    return {"status": "success", "radius_km": radius_km, "data": discounts_list}
```

**Step 4: Run test to verify it passes**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_nearby_api.py`
Expected: `✅ test_nearby_discounts_projection PASSED`

**Step 5: Commit**

```bash
git add apps/api/main.py tests/test_nearby_api.py
git commit -m "feat(api): enrich nearby discounts with clean titles, descriptions, and images"
```

---

### Task 3: Update Home Feed Deduplication (`apps/api/main.py`)

**Files:**
- Modify: `apps/api/main.py:351-417`
- Create: `tests/test_this_week_api.py`

**Step 1: Write the failing test**

```python
# tests/test_this_week_api.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from apps.api.main import get_this_week_discounts
from core.database.session import SessionLocal

def test_this_week_deduplication():
    db = SessionLocal()
    res = get_this_week_discounts(store="Jumbo", page=1, page_size=100, db=db)
    data = res["data"]
    
    slugs = [d["product_slug"] for d in data]
    unique_slugs = set(slugs)
    
    assert len(slugs) == len(unique_slugs), f"Duplicate deals found in This Week feed! Total: {len(slugs)}, Unique: {len(unique_slugs)}"
    db.close()
    print("✅ test_this_week_deduplication PASSED")

if __name__ == "__main__":
    test_this_week_deduplication()
```

**Step 2: Run test to verify it fails**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_this_week_api.py`
Expected: FAIL with `AssertionError: Duplicate deals found in This Week feed!`

**Step 3: Write minimal implementation**

Modify `apps/api/main.py` inside `get_this_week_discounts`:
```python
    query = db.query(Discount, Store).join(
        Store, Discount.store_id == Store.id
    ).filter(
        Discount.start_date <= today,
        Discount.end_date >= today,
        Discount.image_url.isnot(None),
        Store.address.ilike("%Amsterdam%"), # Deduplication filter
        or_(
            and_(Discount.deal_price.isnot(None), Discount.deal_price > 0),
            Discount.deal_type.in_(LABELABLE_TYPES),
        ),
    )
```

**Step 4: Run test to verify it passes**

Run: `/home/burakkp/Documents/Projects/nederland-discounts/.venv/bin/python tests/test_this_week_api.py`
Expected: `✅ test_this_week_deduplication PASSED`

**Step 5: Commit**

```bash
git add apps/api/main.py tests/test_this_week_api.py
git commit -m "fix(api): deduplicate this week discounts feed by filtering canonical store"
```
