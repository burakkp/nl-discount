import json
import os
import sys

from .normalizer import DiscountNormalizer
from .date_helper import RetailDateCalculator

# Use setuptools/standard imports where possible, but keep a fallback for direct script execution
try:
    from core.database.session import SessionLocal
    from core.database.models import Discount, Store
except ImportError:
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
            raw_deal = item.get('deal', '') or ''
            explicit_price = item.get('price')  # Aldi and Lidl use this

            # Skip pure promotional items with no price-related content
            # (e.g. "Gratis bezorging bij...", "Care Giftsets")
            promo_only = (
                not explicit_price
                and not item.get('discount_price')
                and raw_deal == ''
                and not any(p in product_name.lower() for p in [
                    'van ', 'voor ', 'gratis', 'korting', '%', 'halve'
                ])
            )
            if promo_only:
                continue

            # 2. Normalize the Deal
            normalized_math = self.normalizer.normalize(raw_deal, explicit_price)
            deal_window = self.date_calc.calculate_deal_window(store_name, scraped_date)

            # AH embeds prices in the name: "AH Avocado Los van 4.17 voor 2.99"
            # when deal/price fields are empty. Extract them here.
            item_disc_price = item.get('discount_price')
            item_orig_price = item.get('original_price')
            if not item_disc_price and not explicit_price:
                import re as _re
                m = _re.search(r'van\s+([\d,.]+)\s+voor\s+([\d,.]+)', product_name)
                if m:
                    item_orig_price = item_orig_price or m.group(1).replace(',', '.')
                    item_disc_price = m.group(2).replace(',', '.')
                else:
                    # "voor X.XX" pattern (single price)
                    m2 = _re.search(r'\bvoor\s+([\d,.]+)', product_name)
                    if m2:
                        item_disc_price = m2.group(1).replace(',', '.')

            # 3. Construct the canonical record for the database
            # normalize_deal returns: deal_type, unit_price, bundle_price, bundle_qty, discount_pct, free_qty
            # deal_price = the consumer-facing price (bundle total or unit price)
            deal_price = (
                item_disc_price                          # AH name-extracted
                or item.get('deal_price')                # set by harmonizer adapters
                or normalized_math.get('bundle_price')   # "2 voor 3.49" → 3.49
                or normalized_math.get('unit_price')     # FIXED_PRICE or PERCENTAGE with price_raw
                or explicit_price                        # Aldi/Lidl/Plus price field (last resort)
            )
            # original_price: prefer AH-extracted, then item field
            original_price = (
                item_orig_price
                or item.get('original_price')
            )
            # Convert to float safely
            def _safe_float(v):
                try:
                    return float(v) if v is not None else None
                except (TypeError, ValueError):
                    return None

            import json as _json
            deal_options_raw = item.get('deal_options', [])

            canonical_record = {
                "store_name": store_name,
                "product_name": product_name,
                "brand": item.get('brand', None),
                "original_deal_string": raw_deal,
                "deal_type": normalized_math.get('deal_type'),
                "quantity_required": normalized_math.get('bundle_qty'),
                "deal_price": _safe_float(deal_price),
                "original_price": _safe_float(original_price),
                "unit_price": _safe_float(normalized_math.get('unit_price')),
                "unit_label": item.get('unit_label') or item.get('example'),
                "description": item.get('description'),
                "deal_options": _json.dumps(deal_options_raw) if deal_options_raw else None,
                "discount_percentage": normalized_math.get('discount_pct'),
                "url": item.get('url', ''),
                "image_url": item.get('image') or item.get('image_url'),
                "start_date": deal_window["start_date"],
                "end_date": deal_window["end_date"]
            }

            processed_items.append(canonical_record)

        print(f"✅ Processed {len(processed_items)} items from {store_name}.")
        return processed_items

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
            self.db.flush()  # assigns store.id without a full commit
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
                        # Always update deal_type and dates
                        existing.deal_type = item['deal_type']
                        existing.start_date = item['start_date']
                        existing.end_date = item['end_date']
                        existing.unit_label = item.get('unit_label') or existing.unit_label
                        existing.image_url = item.get('image_url') or existing.image_url
                        # Always overwrite description and deal_options (richer data)
                        if item.get('description'):
                            existing.description = item['description']
                        if item.get('deal_options'):
                            existing.deal_options = item['deal_options']
                        # Only overwrite prices if the new value is non-None and non-zero
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