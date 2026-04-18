import asyncio
import os
import sys
import json
import requests
from datetime import date

# Add the project root to sys.path so we can import from apps
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import workers and orchestrators
# Note: We import the scrape functions directly
from apps.workers.ah_worker import scrape_ah_bonus
from apps.workers.aldi_worker import scrape_aldi_bonus
from apps.workers.jumbo_worker import scrape_jumbo_bonus
from apps.workers.lidl_worker import scrape_lidl_bonus
from apps.workers.plus_worker import scrape_plus_bonus
from apps.workers.harmonizer_worker import harmonize
from apps.orchestrator.ingest_all import DataIngestor

async def main():
    print(f"🚀 [START] Full Autonomous Sync - {date.today()}", flush=True)
    
    # 1. Run Workers (Sequential to avoid IP blocking on GitHub Actions)
    print("\n--- Phase 1: Scraping Supermarkets ---", flush=True)
    scrapers = [
        ("Albert Heijn", scrape_ah_bonus, "ah_bonus.json"),
        ("Aldi", scrape_aldi_bonus, "aldi_bonus.json"),
        ("Jumbo", scrape_jumbo_bonus, "jumbo_bonus.json"),
        ("Lidl", scrape_lidl_bonus, "lidl_bonus.json"),
        ("Plus", scrape_plus_bonus, "plus_bonus.json"),
    ]
    
    # Use the absolute path relative to the script location
    tmp_dir = os.path.join(project_root, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    for name, scrape_fn, filename in scrapers:
        print(f"📦 Scraping {name}...", flush=True)
        try:
            # Each worker returns a list of dictionaries
            items = await scrape_fn()
            
            output_path = os.path.join(tmp_dir, filename)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            
            print(f"   ✅ Saved {len(items)} items to {filename}.", flush=True)
        except Exception as e:
            print(f"   ❌ Error scraping {name}: {e}", flush=True)

    # 2. Harmonize (Unifies all JSONs into standardized_discounts.json)
    print("\n--- Phase 2: Harmonizing Data ---", flush=True)
    try:
        harmonize()
        print("✅ Data harmonization complete.", flush=True)
    except Exception as e:
        print(f"❌ Harmonization failed: {e}", flush=True)

    # 3. Ingest (Upserts into PostgreSQL/Supabase)
    print("\n--- Phase 3: Database Ingestion ---", flush=True)
    try:
        # Note: ingest_all.py currently looks at individual JSON files in tmp/
        ingestor = DataIngestor()
        ingestor.run()
        print("✅ Database ingestion complete.", flush=True)
    except Exception as e:
        print(f"❌ Ingestion failed: {e}", flush=True)

    # 4. Trigger Smart Notifications (via Production API)
    # The user requested that notifications only be sent if deals match watchlists.
    # The /admin/trigger-notifications endpoint handles this filtering logic internally.
    print("\n--- Phase 4: Triggering Smart Notifications ---", flush=True)
    render_url = os.getenv("RENDER_API_URL", "https://nl-discounts-api.onrender.com")
    cron_secret = os.getenv("CRON_SECRET")
    
    if cron_secret:
        try:
            resp = requests.post(
                f"{render_url}/admin/trigger-notifications",
                headers={"Authorization": f"Bearer {cron_secret}"},
                timeout=60
            )
            if resp.status_code == 200:
                print(f"📡 Push Alerts Triggered Successfully: {resp.json().get('message')}", flush=True)
            else:
                print(f"⚠️ Notification trigger returned {resp.status_code}: {resp.text}", flush=True)
        except Exception as e:
            print(f"❌ FAILED to contact Render API: {e}", flush=True)
    else:
        print("ℹ️ Skipping notifications (CRON_SECRET not set in environment).", flush=True)

    print("\n✅ [FINISH] Full Sync Cycle Complete.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
