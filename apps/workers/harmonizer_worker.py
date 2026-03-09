"""
Harmonizer Worker
=================
Loads ah_bonus.json, jumbo_bonus.json, lidl_bonus.json, aldi_bonus.json
and produces a single standardized_discounts.json with a unified schema.

Unified output schema per item:
{
    "store":          str,          # "Albert Heijn" | "Jumbo" | "Lidl" | "Aldi" | "Plus"
    "name":           str,          # Product name
    "brand":          str | None,   # Brand (Aldi-only; null for others)
    "deal_type":      str,          # See DEAL_TYPES below
    "discount_pct":   float | None, # 0.0-1.0 (e.g. 0.5 = 50% off)
    "bundle_qty":     int | None,   # Units in deal (e.g. 2 for "2 voor X")
    "bundle_price":   float | None, # Total price for bundle
    "free_qty":       int | None,   # Free units (e.g. 1 for "1+1 gratis")
    "unit_price":     float | None, # Sale price per unit (from Lidl/Aldi)
    "deal_raw":       str | None,   # Original deal string
    "url":            str | None,
    "image":          str | None,
    "scraped_date":   str,
    "source_file":    str,          # Which worker produced this record
}

DEAL_TYPES:
    FIXED_BUNDLE    "2 voor 2.49" — buy N pay one price
    BOGO            "1+1 gratis", "2+1 gratis", "2+2 gratis", etc.
    HALF_PRICE_2ND  "2e halve prijs"
    PERCENTAGE      "25% korting", "-20%", "TOT -25%"
    FIXED_PRICE     Lidl single-item sale price; "voor X" in Jumbo
    FIXED_AMOUNT    "5,00 korting" — absolute euro discount
    CLEARANCE       "OP=OP" (Aldi — while-stocks-last, no special deal)
    UNKNOWN         Couldn't be parsed
"""
import json
import os
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Input / output paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
TMP = os.path.join(PROJECT_ROOT, "tmp")

INPUT_FILES = {
    "Albert Heijn": os.path.join(TMP, "ah_bonus.json"),
    "Jumbo":        os.path.join(TMP, "jumbo_bonus.json"),
    "Lidl":         os.path.join(TMP, "lidl_bonus.json"),
    "Aldi":         os.path.join(TMP, "aldi_bonus.json"),
    "Plus":         os.path.join(TMP, "plus_bonus.json"),
}
OUTPUT_FILE = os.path.join(TMP, "standardized_discounts.json")


# ---------------------------------------------------------------------------
# Deal normalizer
# ---------------------------------------------------------------------------
def normalize_deal(deal_raw: str | None, price_raw: str | None = None) -> dict:
    """
    Parse a Dutch deal string into a structured representation.

    Handles:
      - "2 voor 2,49"           → FIXED_BUNDLE
      - "Combikorting | 2 voor 4,50" → FIXED_BUNDLE (strips prefix)
      - "1+1 gratis"            → BOGO (free_qty=1, discount_pct=0.5)
      - "2+1 gratis"            → BOGO (buy 2 get 1 free)
      - "2+2 gratis"            → BOGO
      - "5+1 gratis"            → BOGO
      - "10+2 gratis"           → BOGO
      - "2e halve prijs"        → HALF_PRICE_2ND (discount_pct=0.25)
      - "25% korting"           → PERCENTAGE
      - "-20%"                  → PERCENTAGE (Aldi)
      - "TOT -25%"              → PERCENTAGE (Aldi)
      - "voor 1,99"             → FIXED_PRICE (Jumbo single price)
      - "5,00 korting"          → FIXED_AMOUNT
      - "OP=OP"                 → CLEARANCE
      - plain numeric "1.19"    → FIXED_PRICE (Lidl)
    """
    base = {
        "deal_type":    "UNKNOWN",
        "discount_pct": None,
        "bundle_qty":   None,
        "bundle_price": None,
        "free_qty":     None,
        "unit_price":   None,
    }

    # No deal text at all → try to use the price field as FIXED_PRICE
    if not deal_raw:
        if price_raw:
            try:
                base.update({"deal_type": "FIXED_PRICE",
                              "unit_price": _parse_price(price_raw)})
            except ValueError:
                pass
        return base

    # Strip channel prefixes like "Alleen online | " or "Combikorting | "
    # and "uitgelicht " filler words
    text = re.sub(r'^(Alleen\s+\w+\s*\|?\s*|Combikorting\s*\|\s*|uitgelicht\s*)',
                  '', deal_raw, flags=re.IGNORECASE).strip()

    text_lower = text.lower()

    # --- OP=OP (Aldi clearance / regular price) ---
    if text_lower == "op=op":
        base["deal_type"] = "CLEARANCE"
        if price_raw:
            try:
                base["unit_price"] = _parse_price(price_raw)
            except ValueError:
                pass
        return base

    # --- X+Y gratis (BOGO) e.g. "1+1 gratis", "2+1 gratis", "10+2 gratis" ---
    bogo = re.match(r'(\d+)\s*\+\s*(\d+)\s+gratis', text_lower)
    if bogo:
        buy_qty = int(bogo.group(1))
        free_qty = int(bogo.group(2))
        total_qty = buy_qty + free_qty
        # discount = free units / total units
        disc = free_qty / total_qty
        base.update({
            "deal_type":    "BOGO",
            "bundle_qty":   buy_qty,
            "free_qty":     free_qty,
            "discount_pct": round(disc, 4),
        })
        return base

    # --- N voor Y,ZZ (FIXED_BUNDLE) e.g. "2 voor 2,49", "4 VOOR" ---
    bundle = re.match(r'(\d+)\s+voor\s+([\d,.]+)', text_lower)
    if bundle:
        qty = int(bundle.group(1))
        price = _parse_price(bundle.group(2))
        base.update({
            "deal_type":    "FIXED_BUNDLE",
            "bundle_qty":   qty,
            "bundle_price": price,
            "unit_price":   round(price / qty, 4) if qty else None,
        })
        return base

    # Aldi "N VOOR" without a price (price is in price_raw) e.g. "2 VOOR", "4 VOOR"
    bundle_no_price = re.match(r'^(\d+)\s+voor$', text_lower)
    if bundle_no_price:
        qty = int(bundle_no_price.group(1))
        unit = None
        if price_raw:
            try:
                total = _parse_price(price_raw)
                unit = round(total / qty, 4)
            except ValueError:
                pass
        base.update({
            "deal_type":  "FIXED_BUNDLE",
            "bundle_qty": qty,
            "bundle_price": _parse_price(price_raw) if price_raw else None,
            "unit_price": unit,
        })
        return base

    # --- 2e halve prijs (HALF_PRICE_2ND = effectively 25% off when buying 2) ---
    if "halve prijs" in text_lower or "2e half" in text_lower:
        base.update({
            "deal_type":    "HALF_PRICE_2ND",
            "bundle_qty":   2,
            "discount_pct": 0.25,   # 50% off 2nd unit → 25% off total
        })
        return base

    # --- X% korting or -X% or TOT -X% (PERCENTAGE) ---
    pct = re.search(r'(\d+(?:[,.]\d+)?)\s*%', text_lower)
    if pct:
        val = float(pct.group(1).replace(',', '.')) / 100
        base.update({
            "deal_type":    "PERCENTAGE",
            "discount_pct": round(val, 4),
        })
        return base

    # --- "voor X,YY" (FIXED_PRICE single item) ---
    voor = re.match(r'^voor\s+([\d,.]+)$', text_lower)
    if voor:
        try:
            base.update({
                "deal_type":  "FIXED_PRICE",
                "unit_price": _parse_price(voor.group(1)),
            })
        except ValueError:
            pass
        return base

    # --- "X,YY korting" (FIXED_AMOUNT euro discount) ---
    amount = re.match(r'^([\d,.]+)\s+korting$', text_lower)
    if amount:
        try:
            base.update({
                "deal_type":    "FIXED_AMOUNT",
                "unit_price":   _parse_price(amount.group(1)),  # discount €
            })
        except ValueError:
            pass
        return base

    # --- Bare numeric string (Lidl price) ---
    if re.match(r'^\d+[.,]\d+$', text):
        try:
            base.update({
                "deal_type":  "FIXED_PRICE",
                "unit_price": _parse_price(text),
            })
        except ValueError:
            pass
        return base

    # --- "Alleen in de slijterij | voor X,YY" edge case ---
    slijterij_price = re.search(r'voor\s+([\d,.]+)', text_lower)
    if slijterij_price:
        try:
            base.update({
                "deal_type":  "FIXED_PRICE",
                "unit_price": _parse_price(slijterij_price.group(1)),
            })
        except ValueError:
            pass
        return base

    # --- "per 100 gram X" or "per stuk X" (AH deli/butcher counter prices) ---
    per_unit = re.match(r'^per\s+\d*\s*\w+\s+([\d,.]+)$', text_lower)
    if per_unit:
        try:
            base.update({
                "deal_type":  "PER_UNIT",
                "unit_price": _parse_price(per_unit.group(1)),
            })
        except ValueError:
            pass
        return base

    # --- "N stuks X" (AH multi-pack fixed price, e.g. "2 stuks 3.49") ---
    stuks = re.match(r'^(\d+)\s+stuks\s+([\d,.]+)$', text_lower)
    if stuks:
        qty = int(stuks.group(1))
        try:
            price = _parse_price(stuks.group(2))
            base.update({
                "deal_type":    "FIXED_BUNDLE",
                "bundle_qty":   qty,
                "bundle_price": price,
                "unit_price":   round(price / qty, 4),
            })
        except ValueError:
            pass
        return base

    base["deal_type"] = "UNKNOWN"
    return base



def _parse_price(s: str) -> float:
    """
    Parse Dutch/EU or EN price strings to float.
    Handles:
      '2,49'  → 2.49   (Dutch decimal comma)
      '2.49'  → 2.49   (English decimal point)
      '1.000' → 1000   (Dutch thousand separator — only if no cent part after)
      '1.299' → 1.299  (ambiguous; treat as decimal if < 4 chars after dot)
    Strategy: if the string has a comma, it's always Dutch (strip dots, replace comma).
    If only a dot, check: if exactly 2-3 digits after the dot → decimal; else → integer.
    """
    s = str(s).strip().replace('\u20ac', '')  # strip € sign
    if ',' in s:
        # Dutch format: possibly '1.234,56'
        return float(s.replace('.', '').replace(',', '.'))
    if '.' in s:
        # English format or ambiguous
        parts = s.split('.')
        # If last part has 1-2 digits it's a decimal (e.g. '2.49', '1.5')
        if len(parts) == 2 and len(parts[1]) <= 2:
            return float(s)
        # Otherwise treat dots as thousand separators ('1.000' → 1000)
        return float(s.replace('.', ''))
    return float(s)



# ---------------------------------------------------------------------------
# Per-store adapters
# ---------------------------------------------------------------------------
def adapt_ah(item: dict) -> dict:
    """Albert Heijn: deal string, no separate price field."""
    norm = normalize_deal(item.get("deal"))
    return {
        "store":        "Albert Heijn",
        "name":         item.get("name") or item.get("product") or "",
        "brand":        None,
        "deal_raw":     item.get("deal"),
        **norm,
        "url":          item.get("url"),
        "image":        None,
        "scraped_date": item.get("scraped_date", ""),
        "source_file":  "ah_bonus.json",
    }


def adapt_jumbo(item: dict) -> dict:
    """Jumbo: deal string, no separate price field."""
    norm = normalize_deal(item.get("deal"))
    return {
        "store":        "Jumbo",
        "name":         item.get("name", ""),
        "brand":        None,
        "deal_raw":     item.get("deal"),
        **norm,
        "url":          item.get("url"),
        "image":        item.get("image"),
        "scraped_date": item.get("scraped_date", ""),
        "source_file":  "jumbo_bonus.json",
    }


def adapt_lidl(item: dict) -> dict:
    """
    Lidl: deal field IS the sale price string.
    description holds unit info ("500 g", "Per stuk").
    """
    norm = normalize_deal(item.get("deal"), item.get("price"))
    return {
        "store":        "Lidl",
        "name":         item.get("name", ""),
        "brand":        None,
        "deal_raw":     item.get("deal"),
        **norm,
        "url":          item.get("url"),
        "image":        item.get("image"),
        "scraped_date": item.get("scraped_date", ""),
        "source_file":  "lidl_bonus.json",
    }


def adapt_aldi(item: dict) -> dict:
    """Aldi: deal holds promo label ('-20%', 'OP=OP', '2 VOOR').
       price holds the numeric sale price."""
    norm = normalize_deal(item.get("deal"), item.get("price"))
    # For CLEARANCE / PERCENTAGE from Aldi, unit_price = sale price
    if norm["deal_type"] in ("CLEARANCE", "PERCENTAGE") and not norm["unit_price"]:
        try:
            norm["unit_price"] = _parse_price(item["price"])
        except (KeyError, ValueError, TypeError):
            pass
    return {
        "store":        "Aldi",
        "name":         item.get("name", ""),
        "brand":        item.get("brand") or None,
        "deal_raw":     item.get("deal"),
        **norm,
        "url":          item.get("url"),
        "image":        item.get("image"),
        "scraped_date": item.get("scraped_date", ""),
        "source_file":  "aldi_bonus.json",
    }


def adapt_plus(item: dict) -> dict:
    """Plus: deal is the promo badge (e.g. '2 VOOR 6.00', '1+1 GRATIS', '50% KORTING').
       price is an optional extracted price string."""
    norm = normalize_deal(item.get("deal"), item.get("price"))
    return {
        "store":        "Plus",
        "name":         item.get("name", ""),
        "brand":        None,
        "deal_raw":     item.get("deal"),
        **norm,
        "url":          item.get("url"),
        "image":        item.get("image"),
        "scraped_date": item.get("scraped_date", ""),
        "source_file":  "plus_bonus.json",
    }


ADAPTERS = {
    "Albert Heijn": adapt_ah,
    "Jumbo":        adapt_jumbo,
    "Lidl":         adapt_lidl,
    "Aldi":         adapt_aldi,
    "Plus":         adapt_plus,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def harmonize() -> list[dict]:
    results = []
    for store, path in INPUT_FILES.items():
        if not os.path.exists(path):
            print(f"  ⚠️  {path} not found, skipping {store}", flush=True)
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        adapter = ADAPTERS[store]
        store_results = [adapter(item) for item in items]
        print(f"  ✅ {store}: {len(store_results)} items", flush=True)
        results.extend(store_results)
    return results


if __name__ == "__main__":
    print("🔄 Harmonizing discount data from all stores...", flush=True)
    data = harmonize()

    # Summary stats
    from collections import Counter
    types = Counter(d["deal_type"] for d in data)
    stores = Counter(d["store"] for d in data)

    os.makedirs(TMP, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(data)} total items saved → {OUTPUT_FILE}", flush=True)

    print("\n📊 By store:")
    for store, cnt in stores.most_common():
        print(f"   {store:<15} {cnt:>4} items")

    print("\n📊 By deal type:")
    for dtype, cnt in types.most_common():
        print(f"   {dtype:<18} {cnt:>4} items")
