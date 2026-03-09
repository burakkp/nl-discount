import re

class DiscountNormalizer:
    def __init__(self):
        # The Architect's Regex Dictionary: Designed to catch all Dutch retail dialects
        self.patterns = {
            "x_voor_y": r'(\d+)\s*(?:voor|stuks)\s*(?:€)?\s*(\d+[.,]\d+)', # Matches "2 voor 4.50" or "3 stuks 3.49"
            "x_plus_y_gratis": r'(\d+)\s*\+\s*(\d+)\s*gratis',            # Matches "1+1 gratis", "2+3 gratis"
            "percentage_off": r'(\d+)\s*%\s*(?:korting)?',                # Matches "25% korting", "-20%", "50%"
            "second_half_price": r'2e\s*halve\s*prijs',                   # Matches "2e halve prijs"
            "euro_off": r'(?:€)?\s*(\d+[.,]\d+)\s*korting',               # Matches "€1.50 korting"
            "absolute_price": r'(?:voor|per.*?)\s*(?:€)?\s*(\d+[.,]\d+)'  # Matches "voor 1.99" or "per 500 gram 0.99"
        }

    def _clean_string(self, text):
        """Standardizes text: lowercase, removes newlines, trims spaces."""
        if not text: return ""
        # Handle Jumbo's multi-line strings like "Combikorting\n2 voor 4,50"
        return str(text).lower().replace('\n', ' ').strip()

    def _to_float(self, price_str):
        """
        Converts a Dutch/EU price string to float.
        Robust: uses regex to pull the first valid number so that
        malformed concatenations like '3. 74 7.493.747.49' don't crash.
        Examples: '4,50' → 4.5 | '€ 3.99' → 3.99 | '3. 74 7.49...' → 3.74
        """
        if not price_str:
            return 0.0
        s = str(price_str).strip()
        # Extract the first valid number: digits with optional comma/dot decimal
        match = re.search(r'\d+[.,]\d+|\d+', s.replace(' ', ''))
        if not match:
            return 0.0
        raw = match.group(0)
        # Dutch comma → English dot
        return float(raw.replace(',', '.'))

    def normalize(self, deal_text, explicit_price=None):
        """
        Parses the deal string and calculates the actual math.
        Returns a standardized dictionary for the database.
        """
        deal_text = self._clean_string(deal_text)
        
        # Handle edge case: Aldi's "4 VOOR" where price is in a separate field
        if "voor" in deal_text and not re.search(r'\d+[.,]\d+', deal_text) and explicit_price:
            deal_text = f"{deal_text} {explicit_price}"

        # 1. Check for "X voor Y" (MULTI_BUY)
        match = re.search(self.patterns["x_voor_y"], deal_text)
        if match:
            qty = int(match.group(1))
            price = self._to_float(match.group(2))
            return {
                "type": "MULTI_BUY",
                "quantity": qty,
                "deal_price": price,
                "unit_price": round(price / qty, 2) if qty > 0 else price,
                "discount_percentage": None
            }

        # 2. Check for "X+Y gratis" (BOGO)
        match = re.search(self.patterns["x_plus_y_gratis"], deal_text)
        if match:
            buy = int(match.group(1))
            free = int(match.group(2))
            total_qty = buy + free
            discount_pct = free / total_qty
            return {
                "type": "BOGO",
                "quantity": total_qty,
                "deal_price": self._to_float(explicit_price), # Might be None if original price isn't known
                "unit_price": None,
                "discount_percentage": round(discount_pct * 100, 2)
            }

        # 3. Check for "2e halve prijs" (Effectively 25% off total for 2 items)
        if re.search(self.patterns["second_half_price"], deal_text):
            return {
                "type": "PERCENTAGE",
                "quantity": 2,
                "deal_price": None,
                "unit_price": None,
                "discount_percentage": 25.0
            }

        # 4. Check for Percentage Discount
        match = re.search(self.patterns["percentage_off"], deal_text)
        if match:
            return {
                "type": "PERCENTAGE",
                "quantity": 1,
                "deal_price": self._to_float(explicit_price),
                "unit_price": None,
                "discount_percentage": float(match.group(1))
            }

        # 5. Check for Euro Discount (e.g. €1,50 korting)
        match = re.search(self.patterns["euro_off"], deal_text)
        if match:
            return {
                "type": "FIXED_DISCOUNT",
                "quantity": 1,
                "deal_price": self._to_float(explicit_price),
                "unit_price": None,
                "discount_percentage": None,
                "discount_amount": self._to_float(match.group(1))
            }

        # 6. Fallback: Just a strict price (Lidl style or "voor X")
        match = re.search(self.patterns["absolute_price"], deal_text)
        price_val = self._to_float(match.group(1)) if match else self._to_float(explicit_price)
        
        return {
            "type": "FIXED_PRICE" if price_val else "UNKNOWN",
            "quantity": 1,
            "deal_price": price_val,
            "unit_price": price_val,
            "discount_percentage": None
        }

# --- ARCHITECT's TEST SUITE ---
if __name__ == "__main__":
    normalizer = DiscountNormalizer()
    
    # Testing strings explicitly found in your provided JSON files
    test_cases = [
        # Store, Deal Text, Explicit Price
        ("Jumbo", "Combikorting\n2 voor 4,50", None),           # Jumbo Multibuy
        ("AH", "uitgelicht 1+1 gratis", None),                  # AH BOGO
        ("Aldi", "-20%", "6.49"),                               # Aldi Percentage
        ("AH", "2e halve prijs", None),                         # AH/Jumbo 2nd half
        ("Jumbo", "Alleen in de slijterij\n5,00 korting", None),# Jumbo Euro off
        ("Aldi", "4 VOOR", "1.00"),                             # Aldi Split string
        ("Lidl", "1.19", "1.19"),                               # Lidl standard
        ("PLUS", "2+3 gratis", None)                            # Anticipating PLUS
    ]

    print(f"{'STORE':<7} | {'RAW DEAL TEXT':<40} | NORMALIZED OUTPUT")
    print("-" * 120)
    for store, deal, price in test_cases:
        result = normalizer.normalize(deal, explicit_price=price)
        # Formatting for console output
        clean_text = deal.replace('\n', ' ')[:38]
        print(f"{store:<7} | {clean_text:<40} | {result}")