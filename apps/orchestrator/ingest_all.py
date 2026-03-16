import json
import os
import sys

from normalizer import DiscountNormalizer
from date_helper import RetailDateCalculator

# Make the project root importable regardless of where the script is invoked from
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.database.session import SessionLocal
from core.database.models import Discount, Store

class DataIngestor:
    def __init__(self):
        self.normalizer = DiscountNormalizer()
        self.date_calc = RetailDateCalculator()
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp")  # JSON files live in tmp/
        self.db = SessionLocal()

    def load_json(self, filepath):
        """Safely load JSON data."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Warning: File not found {filepath}")
            return []
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in {filepath}")
            return []

    def process_file(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        raw_data = self.load_json(filepath)

        processed_items = []
        store_name = filename.replace('_bonus.json', '').replace('_', ' ').title()  # Fallback name from filename
        for item in raw_data:
            # 1. Extract raw fields (handling differences between AH, Aldi, Jumbo, Lidl, Plus)
            store_name = item.get('store', store_name)
            scraped_date = item.get('scraped_date', None)
            product_name = item.get('name', 'Unknown Product')
            raw_deal = item.get('deal', '')
            explicit_price = item.get('price')  # Aldi and Lidl use this

            # 2. Normalize the Deal
            normalized_math = self.normalizer.normalize(raw_deal, explicit_price)
            deal_window = self.date_calc.calculate_deal_window(store_name, scraped_date)

            # 3. Construct the canonical record for the database
            canonical_record = {
                "store_name": store_name,
                "product_name": product_name,
                "brand": item.get('brand', None),  # Mostly Aldi provides this
                "original_deal_string": raw_deal,
                "deal_type": normalized_math.get('type'),
                "quantity_required": normalized_math.get('quantity'),
                "deal_price": normalized_math.get('deal_price'),
                "unit_price": normalized_math.get('unit_price'),
                "discount_percentage": normalized_math.get('discount_percentage'),
                "url": item.get('url', ''),
                "start_date": deal_window["start_date"],
                "end_date": deal_window["end_date"]
            }

            processed_items.append(canonical_record)

        print(f"✅ Processed {len(processed_items)} items from {store_name}.")
        return processed_items

    def _get_or_create_store(self, chain_name: str) -> Store:
        """Return an existing Store row, or create one on the fly."""
        store = (
            self.db.query(Store)
            .filter(Store.chain_name.ilike(chain_name))
            .first()
        )
        if not store:
            store = Store(chain_name=chain_name)
            self.db.add(store)
            self.db.flush()  # assigns store.id without a full commit
        return store

    def ingest_to_db(self, all_items):
        """Upsert processed discount records into the database."""
        print(f"\n🚀 Initiating Database Upsert for {len(all_items)} total discounts...")
        inserted = 0
        try:
            for item in all_items:
                store = self._get_or_create_store(item['store_name'])

                # The Discount schema has no Product FK — it stores a string ID.
                master_product_id = item['product_name'].lower().replace(' ', '_')[:100]

                discount = Discount(
                    master_product_id=master_product_id,
                    store_id=store.id,
                    deal_type=item['deal_type'],
                    deal_price=item['deal_price'],
                    unit_price=item['unit_price'],
                    start_date=item['start_date'],
                    end_date=item['end_date'],
                )
                self.db.add(discount)
                inserted += 1

            self.db.commit()
            print(f"💾 Database transaction complete. Inserted {inserted} discounts.")
        except Exception as exc:
            self.db.rollback()
            print(f"❌ DB error — transaction rolled back: {exc}")
            raise
        finally:
            self.db.close()

    def run(self):
        files_to_process = [
            "ah_bonus.json", 
            "jumbo_bonus.json", 
            "aldi_bonus.json", 
            "lidl_bonus.json", 
            "plus_bonus.json"
        ]
        
        master_list = []
        for file in files_to_process:
            master_list.extend(self.process_file(file))
            
        self.ingest_to_db(master_list)

if __name__ == "__main__":
    ingestor = DataIngestor()
    ingestor.run()