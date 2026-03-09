from datetime import datetime, timedelta

class RetailDateCalculator:
    def __init__(self):
        # Dutch retail usually anchors on Monday (0) or Wednesday (2) / Thursday (3)
        pass

    def calculate_deal_window(self, store_name, scraped_date_str):
        """
        Calculates the start and end date of a deal based on the store's business rules.
        """
        # Fallback to today if scraper failed to provide a date
        if not scraped_date_str:
            base_date = datetime.now().date()
        else:
            try:
                base_date = datetime.strptime(scraped_date_str, "%Y-%m-%d").date()
            except ValueError:
                base_date = datetime.now().date()

        # weekday(): Monday is 0, Sunday is 6
        current_weekday = base_date.weekday()
        
        # Find the Monday of the week this data was scraped
        monday_of_week = base_date - timedelta(days=current_weekday)
        sunday_of_week = monday_of_week + timedelta(days=6)

        store = store_name.lower()

        # Rule 1: AH, Jumbo, and PLUS run strictly Monday to Sunday
        if store in ["albert heijn", "jumbo", "plus"]:
            return {
                "start_date": monday_of_week,
                "end_date": sunday_of_week
            }
            
        # Rule 2: Aldi & Lidl have Monday deals, but often introduce new deals on Thursday
        # MVP Logic: If scraped Mon-Wed, assume Mon-Sun deal. If scraped Thu-Sun, assume Thu-Sun deal.
        elif store in ["aldi", "lidl"]:
            if current_weekday >= 3: # Thursday or later
                thursday_of_week = monday_of_week + timedelta(days=3)
                return {
                    "start_date": thursday_of_week,
                    "end_date": sunday_of_week
                }
            else:
                return {
                    "start_date": monday_of_week,
                    "end_date": sunday_of_week
                }

        # Fallback for unknown stores
        return {
            "start_date": monday_of_week,
            "end_date": sunday_of_week
        }

# --- ARCHITECT'S TEST SUITE ---
if __name__ == "__main__":
    calc = RetailDateCalculator()
    
    print("Testing with your JSON scraped date: 2026-03-03 (Tuesday)")
    print("-" * 50)
    print("AH:   ", calc.calculate_deal_window("Albert Heijn", "2026-03-03"))
    print("Jumbo:", calc.calculate_deal_window("Jumbo", "2026-03-03"))
    print("Aldi: ", calc.calculate_deal_window("Aldi", "2026-03-03"))
    
    print("\nTesting a Thursday scrape: 2026-03-05 (Thursday)")
    print("-" * 50)
    print("Lidl: ", calc.calculate_deal_window("Lidl", "2026-03-05"))