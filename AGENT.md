# 🤖 AGENT.md — Project Intelligence & Context

> **Note to Future Agents**: This document is your "Zero-Shot" context accelerator. It summarizes the architecture, operational gotchas, and strategic decisions that have defined this project. Respect the "Critical Path" and the "Enterprise Tool Bus" design.

---

## 🏛️ System Overview (The Full Stack)

This is a **Polyrepo** architecture designed for a hyper-local Dutch supermarket discount ecosystem.

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Backend** | Python / FastAPI | The Orchestrator & Tool Bus. |
| **Frontend** | Flutter (Dart) | User Interaction & Geospatial Visualization. |
| **Database** | Supabase (PostgreSQL + PostGIS) | Spatial & Relational Storage. |
| **AI Layer** | Google Gemini 2.5 Flash | Multimodal Vision Agent (OCR/Extraction). |
| **Identity** | Firebase Auth | Zero-Trust JWT Security ("The Bouncer"). |
| **Messaging** | Firebase Cloud Messaging | Temporal alerts for Watchlist matches. |

---

## 🧠 Agentic Knowledge & Workflows

### 1. The Vision Agent (Crowdsourcing)
- **Path**: `apps/api/routes/` and Gemini integration.
- **Workflow**: Snap Photo → Firebase Auth → FastAPI → Gemini Vision → JSON Extraction → Supabase.
- **Critical Prompting**: Gemini must return strict JSON: `{ "product_name": string, "price": float, "deal_type": string }`.

### 2. Data Normalization Engine
- **Logic**: Located in `core/` (backend).
- **Function**: Converts Dutch colloquialisms (e.g., "2e gratis", "1+1") into standardized unit prices.
- **Regex Alert**: The unit price extractor is highly sensitive. Test changes against existing samples in `data/`.

### 3. Entity Linking (Master Catalog)
- **Tool**: `RapidFuzz`.
- **Strategy**: Maps chaotic scraped names (e.g., "AH Verse Halfvolle Melk") to a canonical "Master Catalog" entry. This is vital for the **Watchlist** to work.

---

## 🛠️ Operational "Gotchas" (Troubleshooting)

### 🔴 Backend / Infrastructure
1. **Supabase SSL**: Connection strings **MUST** include `?sslmode=require`. Failing to do this results in intermittent "Server closed the connection" errors during heavy scraping.
2. **GitHub Actions**: When running `daily_sync.py`, you MUST set `PYTHONPATH=.` in the workflow file, or the `normalizer` module imports will fail.
3. **Database Environment**: 
   - `.env` usually contains two `DATABASE_URL` entries. 
   - Local: `localhost:5432` (Docker).
   - Prod: Supabase Pooler (`aws-1-eu-west-1.pooler.supabase.com`).

### 🔵 Frontend (Flutter)
1. **Linux Desktop Testing**: `geolocator` will crash on Linux without real GPS hardware. Use `MockLocationService` (check `lib/services/location_service.dart`) to bypass this.
2. **Firebase on Linux**: Firebase Messaging (FCM) is **not supported** on Linux Desktop. Guard all FCM calls with `if (!kIsWeb && !Platform.isLinux)`.
3. **Riverpod 3.x Migration**: We are in the process of moving to modern `AsyncNotifier` patterns. Avoid legacy `StateNotifier` for new features.
4. **Watchlist Regex**: Ensure `product_id` regex in the API service allows **spaces**. Older versions were too strict and blocked "Albert Heijn" searches.

---

## 🚀 The Critical Path (Upcoming Priorities)

1. **State Management Refactor**: Finalize the Riverpod migration to remove any remaining `setState` or `FutureBuilder` logic from complex screens.
2. **Watchlist UI/UX**: Enhance the "Catalog Search" experience with auto-suggestions and "Smart Category" grouping.
3. **Map Clustering**: Optimize the MapView for 500+ markers using procedural clustering to maintain 60fps.

---

## 🤝 Human-in-the-Loop (HITL)
**Ask the user if:**
- You are about to modify the **PostgreSQL Schema** (requires migration coordination).
- You are changing the **Master Catalog Mapping** logic (impacts all users' watchlists).
- You are deploying to **Render Prod** (requires manual verification of secrets).

---

**Directory Reference:**
- Backend Root: `/home/burakkp/Documents/Projects/nederland-discounts`
- Frontend Root: `/home/burakkp/Documents/Projects/nl_discounts_app`
