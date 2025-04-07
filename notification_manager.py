import logging
from datetime import datetime, timedelta
from typing import List, Optional
from firebase_admin import firestore

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.notification_limits = {
            'basic': {
                'max_stores': 1,
                'notifications_per_day': 3
            },
            'premium': {
                'max_stores': float('inf'),  # No limit for premium users
                'notifications_per_day': 8
            }
        }
        self.db = firestore.client()
        self.notifications_ref = self.db.collection('notifications')

    def can_add_notification(self, user_id: str, store: str, is_premium: bool) -> bool:
        """Check if user can add more notifications based on their tier"""
        try:
            # Get user's current store notifications from database
            user_notifications = self.get_user_notifications(user_id)
            logger.debug(f"Current notifications for user {user_id}: {len(user_notifications)}")

            # Get user's tier limits
            tier_limits = self.notification_limits['premium' if is_premium else 'basic']
            logger.debug(f"User {user_id} tier limits: {tier_limits}")

            # Check store limit
            current_stores = set(notif['store'] for notif in user_notifications)
            if store not in current_stores and len(current_stores) >= tier_limits['max_stores']:
                logger.info(f"User {user_id} has reached their store limit ({tier_limits['max_stores']})")
                return False

            # Check daily notification limit
            today = datetime.utcnow().date()
            notifications_today = len([
                n for n in user_notifications 
                if n.get('last_sent') and datetime.fromisoformat(n['last_sent']).date() == today
            ])
            logger.debug(f"User {user_id} notifications today: {notifications_today}")

            if notifications_today >= tier_limits['notifications_per_day']:
                logger.info(f"User {user_id} has reached their daily notification limit ({tier_limits['notifications_per_day']})")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking notification limits for user {user_id}: {str(e)}")
            return False

    def toggle_notification(self, user_id: str, store: str, is_premium: bool) -> bool:
        """Toggle notification for a store"""
        try:
            # Get user's current notifications
            user_notifications = self.get_user_notifications(user_id)
            store_notifications = [n for n in user_notifications if n['store'] == store]

            if store_notifications:
                # Remove notification if it exists
                logger.info(f"Removing notification for user {user_id} and store {store}")
                for notif in store_notifications:
                    self.notifications_ref.document(notif['id']).delete()
                return True
            else:
                # Check if user can add notification
                if not self.can_add_notification(user_id, store, is_premium):
                    logger.info(f"User {user_id} cannot add more notifications")
                    return False

                # Add notification if it doesn't exist
                return self.add_notification(user_id, store, is_premium)

        except Exception as e:
            logger.error(f"Error toggling notification for user {user_id} and store {store}: {str(e)}")
            return False

    def add_notification(self, user_id: str, store: str, is_premium: bool) -> bool:
        """Add a new notification for the user"""
        try:
            if not self.can_add_notification(user_id, store, is_premium):
                logger.info(f"Cannot add notification for user {user_id} and store {store}")
                return False

            # Add notification to database
            notification = {
                'user_id': user_id,
                'store': store,
                'created_at': datetime.utcnow().isoformat(),
                'last_sent': None
            }
            logger.info(f"Adding notification for user {user_id} and store {store}")

            # Save to Firestore
            doc_ref = self.notifications_ref.add(notification)
            notification['id'] = doc_ref[1].id  # Save document ID
            return True

        except Exception as e:
            logger.error(f"Error adding notification for user {user_id}: {str(e)}")
            return False

    def get_user_notifications(self, user_id: str) -> List[dict]:
        """Get all notifications for a user from Firestore"""
        try:
            logger.debug(f"Getting notifications for user {user_id}")
            notifications = []
            docs = self.notifications_ref.where('user_id', '==', user_id).stream()

            for doc in docs:
                notification = doc.to_dict()
                notification['id'] = doc.id
                notifications.append(notification)

            return notifications
        except Exception as e:
            logger.error(f"Error getting notifications for user {user_id}: {str(e)}")
            return []

    def should_notify(self, notification: dict, is_premium: bool) -> bool:
        """Check if notification should be sent based on user tier and last notification time"""
        try:
            if not notification.get('last_sent'):
                return True

            tier_limits = self.notification_limits['premium' if is_premium else 'basic']
            hours_between = 24 / tier_limits['notifications_per_day']
            last_sent = datetime.fromisoformat(notification['last_sent'])
            next_notification_time = last_sent + timedelta(hours=hours_between)

            return datetime.utcnow() >= next_notification_time

        except Exception as e:
            logger.error(f"Error checking notification timing: {str(e)}")
            return False

    def record_notification_sent(self, notification: dict) -> bool:
        """Record that a notification was sent"""
        try:
            notification['last_sent'] = datetime.utcnow().isoformat()
            self.notifications_ref.document(notification['id']).update({
                'last_sent': notification['last_sent']
            })
            return True
        except Exception as e:
            logger.error(f"Error recording notification: {str(e)}")
            return False