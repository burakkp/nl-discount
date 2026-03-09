from rapidfuzz import process, fuzz

class ProductLinker:
    def __init__(self):
        # This is your "Master Database" of canonical products.
        # In production, this would be loaded from your Postgres `products` table.
        self.master_catalog = [
            "Komkommer",
            "Courgette",
            "Volle Melk",
            "Halfvolle Melk",
            "Coca-Cola Regular",
            "Coca-Cola Zero",
            "Trostomaten",
            "Kipfilet",
            "Rundergehakt"
        ]
        
        # We set a threshold. If the match is below 75%, it's marked as "Unknown" 
        # and goes to a human-in-the-loop review queue.
        self.confidence_threshold = 75.0 

    def _clean_for_matching(self, text):
        """Removes store brands to improve match accuracy."""
        text = text.lower()
        stop_words = ["ah", "jumbo", "aldi", "biologisch", "luxe", "excellent", "premium"]
        
        for word in stop_words:
            text = text.replace(word, "").strip()
        return text

    def link_product(self, raw_scraped_name):
        """
        Finds the closest master product for a scraped product.
        """
        cleaned_name = self._clean_for_matching(raw_scraped_name)
        
        # extractOne returns a tuple: (Best Match String, Confidence Score, Index)
        best_match = process.extractOne(
            cleaned_name, 
            self.master_catalog, 
            scorer=fuzz.token_set_ratio # token_set_ratio ignores word order ("melk volle" == "volle melk")
        )
        
        if best_match and best_match[1] >= self.confidence_threshold:
            return {
                "master_product": best_match[0],
                "confidence": round(best_match[1], 2),
                "status": "AUTO_MATCHED"
            }
        else:
            return {
                "master_product": "Needs Review",
                "confidence": round(best_match[1], 2) if best_match else 0.0,
                "status": "UNMATCHED"
            }

# --- ARCHITECT'S TEST SUITE ---
if __name__ == "__main__":
    linker = ProductLinker()
    
    # Messy data from your JSONs
    scraped_items = [
        "AH Biologisch komkommer",       # Should match "Komkommer"
        "Jumbo Komkommers",              # Should match "Komkommer"
        "Lidl Trostomaten per kilo",     # Should match "Trostomaten"
        "AH Volle melk 1 Liter",         # Should match "Volle Melk"
        "Coca-Cola 4-pack",              # Should match "Coca-Cola Regular"
        "Gekke Paashaas Chocolade"       # Should fail (Needs Review)
    ]

    print(f"{'RAW SCRAPED NAME':<30} | {'MASTER PRODUCT':<20} | CONFIDENCE")
    print("-" * 75)
    for item in scraped_items:
        result = linker.link_product(item)
        print(f"{item:<30} | {result['master_product']:<20} | {result['confidence']}% [{result['status']}]")