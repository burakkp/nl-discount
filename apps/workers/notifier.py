import os
from datetime import date, timedelta
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

# Import our database models
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from core.database.models import User, WatchlistItem, Discount, Store

class SmartNotificationEngine:
    def __init__(self):
        # 1. Initialize Firebase safely
        if not firebase_admin._apps:
            env = os.getenv("ENVIRONMENT", "DEV")
            key_path = "core/security/firebase_service_account.json" if env == "DEV" else "/etc/secrets/firebase_prod.json"
            try:
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
                print("✅ Notifier connected to Firebase.")
            except Exception as e:
                print(f"🚨 Notifier Firebase Error: {e}")

    def send_push_notification(self, token: str, title: str, body: str):
        """Sends the payload to Google's FCM servers."""
        if not token: return
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
            )
            response = messaging.send(message)
            print(f"📡 [PUSH SENT] to {token[-10:]}: {title}")
        except Exception as e:
            print(f"❌ Failed to send push: {e}")

    def process_user_watchlist(self, db: Session, user: User):
        """Finds active deals for a specific user and fires alerts."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Get what the user is tracking
        watched_items = db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()
        watched_ids = [item.master_product_id for item in watched_items]

        if not watched_ids: return

        # Query Supabase for active deals matching those items
        active_deals = db.query(Discount).filter(
            Discount.master_product_id.in_(watched_ids),
            Discount.end_date >= today
        ).all()

        new_deals = [d for d in active_deals if d.start_date == today]
        expiring_deals = [d for d in active_deals if d.end_date == tomorrow]

        # 1. Fire the "Fresh Week" Alert
        if new_deals:
            items_str = ", ".join([d.master_product_id for d in new_deals[:3]])
            self.send_push_notification(
                user.fcm_token,
                "🛒 New Deals Found!",
                f"{items_str} and more are on sale today."
            )

        # 2. Fire the "Last Chance" Alert
        if expiring_deals:
            items_str = ", ".join([d.master_product_id for d in expiring_deals[:2]])
            self.send_push_notification(
                user.fcm_token,
                "⏳ Last Chance!",
                f"Discounts on {items_str} end tomorrow."
            )

    def run_daily_digest(self, db: Session):
        """The Master Function triggered by the Cron Job."""
        print(f"🚀 Starting Daily Smart Digest for {date.today()}...")

        # Get all users who have an FCM token
        users = db.query(User).filter(User.fcm_token.isnot(None)).all()

        for user in users:
            self.process_user_watchlist(db, user)

        print("✅ Daily digest complete.")