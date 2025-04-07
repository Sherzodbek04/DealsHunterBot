import logging
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self):
        """Initialize Firestore users collection reference"""
        try:
            # Initialize Firebase if not already initialized
            if not len(firebase_admin._apps):
                cred = credentials.Certificate("credentials.json")
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            self.users_ref = self.db.collection('users')
            logger.info("Firebase connection initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Firebase: {str(e)}")
            raise

    def get_user_language(self, user_id: int) -> str:
        """Get users preferred language from Firestore
        Returns 'en' if user doesn't exist or error occurs"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict().get('language', 'en')
            logger.warning(f"User {user_id} not found, returning default language")
            return 'en'
        except Exception as e:
            logger.error(f"Error getting user language: {str(e)}")
            return 'en'

    def save_user_language(self, user_id: int, language: str) -> None:
        """Save users language preference to Firestore
        Creates user document if it doesn't exist"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc_ref.set({'language': language}, merge=True)
            logger.info(f"Language preference saved for user {user_id}: {language}")
        except Exception as e:
            logger.error(f"Error saving user language: {str(e)}")
            raise

    def create_user_if_not_exists(self, user_id: int) -> None:
        """Create a new user with default preferences if not exists"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            if not doc_ref.get().exists:
                doc_ref.set({
                    'language': 'en',
                    'created_at': firestore.SERVER_TIMESTAMP
                })
                logger.info(f"Created new user: {user_id}")
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

    def is_user_premium(self, user_id: int) -> bool:
        """Check if user has premium status"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc = doc_ref.get()
            if not doc.exists:
                # Create new user record with default premium status
                doc_ref.set({
                    'is_premium': False,
                    'created_at': firestore.SERVER_TIMESTAMP
                }, merge=True)
                return False

            user_data = doc.to_dict()
            return user_data.get('is_premium', False)
        except Exception as e:
            logger.error(f"Error checking premium status: {str(e)}")
            return False

    def save_user_subscription_id(self, user_id: int, subscription_id: str) -> None:
        """Save the user's Stripe subscription ID"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc_ref.set({'subscription_id': subscription_id}, merge=True)
            logger.info(f"Saved subscription ID for user {user_id}: {subscription_id}")
        except Exception as e:
            logger.error(f"Error saving subscription ID: {e}")

    def save_stripe_customer_id(self, user_id: int, customer_id: str) -> None:
        """Save the user's Stripe customer ID"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc_ref.set({'stripe_customer_id': customer_id}, merge=True)
            logger.info(f"Saved Stripe customer ID for user {user_id}: {customer_id}")
        except Exception as e:
            logger.error(f"Error saving Stripe customer ID: {e}")

    def get_stripe_customer_id(self, user_id: int) -> Optional[str]:
        """Get the user's Stripe customer ID"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                customer_id = user_data.get('stripe_customer_id')
                if customer_id:
                    logger.info(f"Found Stripe customer ID {customer_id} for user {user_id}")
                    return customer_id
                logger.warning(f"No Stripe customer ID found for user {user_id}")
                return None
            logger.warning(f"User document not found for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving Stripe customer ID: {e}")
            return None

    def get_user_subscription_id(self, user_id: int) -> Optional[str]:
        """Retrieve the user's Stripe subscription ID"""
        try:
            doc_ref = self.users_ref.document(str(user_id))
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                # Try to get subscription_id first
                subscription_id = user_data.get('subscription_id')
                if subscription_id:
                    logger.info(f"Found subscription_id {subscription_id} for user {user_id}")
                    return subscription_id

                # If not found, try subscription_item_id
                subscription_item_id = user_data.get('subscription_item_id')
                if subscription_item_id:
                    logger.info(f"Found subscription_item_id {subscription_item_id} for user {user_id}")
                    return subscription_item_id

                logger.warning(f"No subscription IDs found for user {user_id}")
                return None

            logger.warning(f"User document not found for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving subscription ID: {e}")
            return None