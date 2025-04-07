import os
import logging
import stripe

logger = logging.getLogger(__name__)

# Initialize Stripe with environment variable
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
PRICE_ID = os.environ.get("STRIPE_PRICE_ID")

def create_checkout_session(user_id: str):
    """Create a Checkout Session for a user - SIMPLIFIED"""
    try:
        # Check required configuration
        if not stripe.api_key:
            logger.error("Stripe API key not configured")
            return None

        if not PRICE_ID:
            logger.error("Stripe Price ID not configured")
            return None

        logger.info(f"=== CREATING CHECKOUT SESSION FOR USER {user_id} ===")

        # Import firestore here to avoid circular imports
        from firebase_admin import firestore
        db = firestore.client()

        # Simple approach: Create a new customer every time
        # This avoids issues with invalid customers
        logger.info(f"Creating new Stripe customer for user {user_id}")
        customer = stripe.Customer.create(
            metadata={"user_id": user_id}
        )
        customer_id = customer.id
        logger.info(f"Created customer ID: {customer_id}")

        # Basic session parameters - keep it simple
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price": PRICE_ID,
                "quantity": 1
            }],
            "mode": "subscription",
            "success_url": "https://t.me/dailydealsfinderbot?start=success",
            "cancel_url": "https://t.me/dailydealsfinderbot?start=cancel",
            "customer": customer_id,
            # IMPORTANT: Make sure user_id is in metadata for webhook processing
            "metadata": {"user_id": user_id}
        }

        # Create checkout session
        logger.info(f"Creating checkout session with parameters: {session_params}")
        session = stripe.checkout.Session.create(**session_params)

        session_id = session.id
        logger.info(f"Created checkout session ID: {session_id}")

        # Save essential data to Firestore right away
        # This will help with debugging and ensure customer ID is saved
        logger.info(f"Saving customer ID to Firestore for user {user_id}")
        db.collection('users').document(user_id).set({
            'stripe_customer_id': customer_id,
            'latest_checkout_session': session_id,
            'checkout_created_at': firestore.SERVER_TIMESTAMP
        }, merge=True)

        logger.info(f"✅ Successfully created checkout process for user {user_id}")
        return session.url
    except Exception as e:
        logger.error(f"💥 ERROR creating checkout session: {e}")
        logger.error(f"Stacktrace: {traceback.format_exc()}")
        return None

def get_customer_id_by_user_id(user_id: str) -> str:
    """Retrieve customer ID from Firestore for the given user ID"""
    try:
        if not stripe.api_key:
            logger.error("Stripe API key not configured")
            return None

        logger.info(f"Looking for customer ID in Firestore for user: {user_id}")

        # Import Firestore here to avoid circular imports
        from firebase_admin import firestore
        db = firestore.client()

        # Get user document from Firestore
        user_doc = db.collection('users').document(user_id).get()

        if not user_doc.exists:
            logger.warning(f"User document not found for user_id: {user_id}")
            return None

        user_data = user_doc.to_dict()
        customer_id = user_data.get('stripe_customer_id')

        if not customer_id:
            logger.warning(f"No Stripe customer ID found for user: {user_id}")
            return None

        logger.info(f"Found Stripe customer ID: {customer_id} for user: {user_id}")
        return customer_id

    except Exception as e:
        logger.error(f"Error finding Stripe customer: {e}")
        return None

def get_active_subscription_by_customer(customer_id: str) -> str:
    """Get the active subscription ID for a customer"""
    try:
        if not customer_id:
            logger.error("No customer ID provided")
            return None

        logger.info(f"Retrieving active subscriptions for customer: {customer_id}")

        # Get all subscriptions for this customer
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status='active',
            limit=1
        )

        if not subscriptions.data:
            logger.warning(f"No active subscriptions found for customer: {customer_id}")
            return None

        subscription = subscriptions.data[0]
        logger.info(f"Found active subscription: {subscription.id} for customer: {customer_id}")
        return subscription.id

    except Exception as e:
        logger.error(f"Error retrieving subscription: {e}")
        return None

def cancel_stripe_subscription(subscription_id: str) -> bool:
    """Cancel an active Stripe subscription"""
    try:
        if not stripe.api_key:
            logger.error("Stripe API key not configured")
            return False

        if not subscription_id:
            logger.error("No subscription ID provided")
            return False

        logger.info(f"Attempting to cancel subscription with ID: {subscription_id}")

        # Retrieve the subscription to check its status
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            logger.info(f"Successfully retrieved subscription: {subscription.id}")

            # Check if already canceled
            if subscription.status == 'canceled':
                logger.info(f"Subscription {subscription_id} is already canceled.")
                return True

            # Important: Check if the subscription is active before attempting to cancel
            if subscription.status not in ['active', 'trialing']:
                logger.warning(f"Cannot cancel subscription with status: {subscription.status}")
                return False

            # Cancel subscription immediately
            result = stripe.Subscription.delete(subscription_id)
            logger.info(f"Subscription {subscription_id} canceled immediately. Status: {result.status}")
            return True

        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid subscription ID: {subscription_id}. Error: {e}")
            return False

    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        return False