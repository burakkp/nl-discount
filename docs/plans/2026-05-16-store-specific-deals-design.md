# Store-Specific Deals Architecture & Scalability Design

## 1. Executive Summary
Nederland Discounts is transitioning from a legacy "Single-Store Ingestion" model to a **"Multi-Store Ingestion & Geofenced Projection"** architecture. This enables hyper-local, store-specific deals (e.g., manager specials, clearance items, crowdsourced price tags) while maintaining full automated compatibility with existing nationwide weekly flyer scrapers.

## 2. Architectural Design

```mermaid
graph TD
    subgraph Data Ingestion Layer
        S1[ah_bonus.json] --> DI[ingest_all.py]
        S2[jumbo_bonus.json] --> DI
        S3[aldi_bonus.json] --> DI
        DI -->|Query all matching stores| DB[(PostgreSQL / Supabase)]
        DI -->|Upsert Discount row per Store ID| DB
    end

    subgraph Backend API Layer
        DB -->|ST_DWithin + store_id| API1[/discounts/nearby]
        DB -->|Filter Store.address ilike '%Amsterdam%'| API2[/discounts/this-week]
        API1 -->|Enrich: Title, Image, Desc| APP[Flutter Mobile App]
        API2 -->|Deduplicated Home Feed| APP
    end
```

### 2.1 Data Ingestion (`apps/orchestrator/ingest_all.py`)
- **Multi-Store Replication:** `_get_or_create_store` is updated to query `Store.chain_name.ilike(chain)` using `.all()` instead of `.first()`.
- **Isolated Inventory Rows:** During database ingestion, every scraped weekly deal is upserted into the `discounts` table for **every** physical store ID of that chain. This ensures every map marker (e.g., Jumbo Tiel, Aldi Tiel) possesses its own independent deal records, ready for local store overrides.

### 2.2 API Projection (`apps/api/main.py`)
- **`/discounts/nearby` (Map Tab):** Upgraded to include `Discount.image_url` and `Discount.description` in the PostGIS query. Uses `_parse_slug` to format premium, human-readable titles and extract baseline old prices.
- **`/discounts/this-week` (Home Feed):** To prevent duplicate deals from appearing on the nationwide home feed, the query filters by `Store.address.ilike("%Amsterdam%")` to select exactly one canonical store per chain.

---

## 3. Scalability & Cost Report (10k vs 100k DAU)

### 3.1 Database Storage Sizing & Memory Footprint
- **Total Physical Stores:** ~4,000 supermarkets nationwide.
- **Active Deals per Store:** ~200 weekly flyer deals.
- **Total `Discount` DB Rows:** 4,000 stores × 200 deals = **800,000 rows**.
- **Storage Footprint:** 800,000 rows × 300 bytes $\approx$ **240 MB**.
- **Performance Impact:** 240 MB fits entirely inside the RAM buffer pool of an entry-level database instance (1 GB RAM), ensuring **zero disk I/O bottlenecks**.

### 3.2 Throughput & QPS (Queries Per Second) Analysis
Assuming 3 sessions per DAU per day (12 API calls/day):

| Metric | 10,000 DAU | 100,000 DAU |
| :--- | :--- | :--- |
| **Daily API Requests** | 120,000 req / day | 1,200,000 req / day |
| **Average QPS** | ~1.4 QPS | ~14 QPS |
| **Peak QPS (3x Evening Rush)** | **~4.2 QPS** | **~42 QPS** |

- **`/discounts/this-week` Latency:** <5ms (via B-Tree index on `store_id, start_date, end_date`).
- **`/discounts/nearby` Latency:** <10ms (via PostGIS GiST spatial index on `Store.location` + B-Tree on `store_id`).
- **Server Capacity:** A standard asynchronous FastAPI server with connection pooling easily processes 500+ QPS. 42 QPS at 100k DAU is well within safety margins.

### 3.3 Monthly Infrastructure Cost Breakdown

#### Tier 1: 10,000 DAU (~$30 - $40 / month)
- **Database (Supabase Pro / Render Starter Postgres):** 2 vCPU, 1 GB RAM ($20 - $25/mo).
- **Backend API (Render Web Service / Cloud Run):** 1 instance, 1 vCPU, 512 MB RAM ($10 - $15/mo).

#### Tier 2: 100,000 DAU (~$115 - $190 / month)
- **Database (Supabase Medium / Render Standard Postgres):** 2–4 vCPU, 4 GB RAM. Dedicated connection pooling ($65 - $95/mo).
- **Backend API (Render Standard / Cloud Run Auto-scaling):** 2 instances, 2 vCPU, 1 GB RAM ($50 - $80/mo).
- **Caching Layer (Cloudflare CDN / Redis):** Cloudflare CDN caching for `/discounts/this-week` intercepts 50% of traffic ($0 - $15/mo).

### 3.4 Business ROI & Monetization Alignment
At 100,000 DAU, if 1% of users (1,000 users) subscribe to a premium "Hyper-Local Store Alerts & Ad-Free" tier at €2.99/month, the app generates **€2,990 / month** in recurring revenue against <€190/month infrastructure cost (**15.7x ROI / 93% gross margin**).

---

## 4. Small Market Integration & Future-Proofing Architecture

### 4.1 Architectural Strategy for Independent & Small Markets
As Nederland Discounts expands beyond major national chains (Albert Heijn, Jumbo, Aldi, Lidl, Plus) to include independent local grocers, ethnic supermarkets, and regional small markets (e.g., local Turkish/Moroccan bakeries, organic co-ops, regional farm stands), the architecture is specifically hardened to accommodate them seamlessly without altering core table schemas or API contracts.

### 4.2 Ingestion Engine Isolation (`apps/orchestrator/`)
- **Directory-Based Ingestion Pipelines:** Small markets often possess unique scraping formats or custom JSON structures stored in their own dedicated folders (e.g., `scrapers/small_markets/dirk/`, `scrapers/small_markets/ekoplaza/`).
- **Plug-and-Play Orchestration:** `ingest_all.py` and `DataIngestor` operate purely on normalized dictionary schemas (`store_name`, `product_name`, `deal_price`, `start_date`, `end_date`). As long as small-market scrapers output this standardized JSON payload, `ingest_all.py` will automatically ingest them into `Store` and `Discount` tables with zero code modifications.

### 4.3 Geofenced Discovery & API Compatibility
- **Natural Hyper-Local Discovery:** Because small markets have limited physical footprints (often 1 to 5 stores total), our multi-store replication and PostGIS `ST_DWithin` architecture is the **perfect fit**. A local bakery in Rotterdam will automatically appear on `/discounts/nearby` exclusively for users within that 5km Rotterdam radius, preserving clean geofenced isolation without polluting nationwide search results for users in Amsterdam.
- **Dynamic Store Filtering:** The existing frontend active store provider and backend filtering (`?store=Ekoplaza`) dynamically adapt to any new `chain_name` inserted into the database, instantly populating new small markets in the mobile UI's horizontal store selector bar.
