import os
from datetime import date, timedelta
import firebase_admin
from firebase_admin import credentials, messaging

class SmartNotificationEngine:
    def __init__(self):
        env = os.getenv("ENVIRONMENT", "DEV")
        
        # Determine which key to use
        if env == "DEV":
            key_path = "core/security/firebase_dev.json" # Adjust to match your exact filename
        else:
            key_path = "core/security/firebase_prod.json"

        # Safety Check: Only initialize if Firebase isn't already running
        if not firebase_admin._apps:
            try:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                print(f"✅ Firebase Admin SDK initialized in {env} mode.")
            except FileNotFoundError:
                print(f"🚨 CRITICAL: Firebase key not found at {key_path}")

    def classify_and_notify(self, user, active_deals):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        new_deals = []
        expiring_deals = []

        for deal in active_deals:
            if deal.start_date == today:
                new_deals.append(deal)
            elif deal.end_date == tomorrow:
                expiring_deals.append(deal)

        # 1. Fire the "Fresh Week" Alert
        if new_deals:
            items_str = ", ".join([d.product_name for d in new_deals[:3]])
            title = "🛒 New Deals on your Shopping List!"
            body = f"{items_str} and more are on sale nearby starting today."
            # Note: We need a send_push_notification method defined below
            self.send_push_notification(user.fcm_token, title, body)

        # 2. Fire the "Last Chance" Alert
        if expiring_deals:
            items_str = ", ".join([d.product_name for d in expiring_deals[:2]])
            title = "⏳ Last Chance!"
            body = f"The discount on {items_str} ends tomorrow. Grab it while you can!"
            self.send_push_notification(user.fcm_token, title, body)

    def send_push_notification(self, token, title, body):
        """Actually sends the payload to Firebase."""
        # For testing purposes today, we will just print to console
        print(f"📡 [PUSH TO {token}] {title} | {body}")

    def run_daily_digest(self):
        print(f"🚀 Running Smart Digest for {date.today()}...")
        # Get users and their shopping lists
        # For each user -> Get active deals -> self.classify_and_notify(user, deals)

if __name__ == "__main__":
    # Test execution
    engine = SmartNotificationEngine()
    engine.run_daily_digest()