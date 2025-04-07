import logging
import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
import stripe
import socket
import time
import traceback
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Verify environment variables first
required_env_vars = {
    'STRIPE_SECRET_KEY': None,
    'STRIPE_WEBHOOK_SECRET': None,
    'TELEGRAM_BOT_TOKEN': None
}

# Check all required environment variables
for var_name in required_env_vars:
    value = os.getenv(var_name)
    if not value:
        error_msg = f"Required environment variable {var_name} is not set!"
        logger.error(error_msg)
        raise ValueError(error_msg)
    required_env_vars[var_name] = value
    logger.info(f"✓ {var_name} is properly set")

# Initialize Firebase with error handling
try:
    if not len(firebase_admin._apps):
        cred = credentials.Certificate("credentials.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("✓ Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    raise

app = Flask(__name__)

# Initialize Stripe
stripe.api_key = required_env_vars['STRIPE_SECRET_KEY']
webhook_secret = required_env_vars['STRIPE_WEBHOOK_SECRET']

# Initialize Telegram bot with error handling
try:
    bot = Bot(token=required_env_vars['TELEGRAM_BOT_TOKEN'])
    logger.info("✓ Telegram bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Telegram bot: {e}")
    logger.error(f"Stacktrace: {traceback.format_exc()}")
    sys.exit(1)

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

def wait_for_port_available(port, max_retries=5, retry_delay=2):
    """Wait for port to become available"""
    retries = max_retries
    while retries > 0:
        if not is_port_in_use(port):
            return True
        logger.warning(f"Port {port} is in use, waiting... ({retries} retries left)")
        retries -= 1
        time.sleep(retry_delay)
    return False

@app.route('/')
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'stripe-webhook',
        'timestamp': time.time()
    })

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    # Log all incoming requests
    logger.info("======= RECEIVED STRIPE WEBHOOK =======")
    logger.info(f"Headers: {dict(request.headers)}")

    payload = request.get_data(as_text=True)
    logger.debug(f"Payload (first 100 chars): {payload[:100]}...")
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Check webhook secret
        if not webhook_secret:
            logger.error("💥 WEBHOOK SECRET IS MISSING!")
            return jsonify({"error": "Webhook secret not configured"}), 500

        # Construct event
        logger.info("Verifying Stripe signature...")
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        event_type = event['type']
        logger.info(f"✅ VALID WEBHOOK: {event_type}")

        # Extract and validate session data for checkout completion
        if event_type == 'checkout.session.completed':
            session = event['data']['object']

            # Validate session metadata
            metadata = session.get('metadata', {})
            if not metadata:
                logger.error("❌ No metadata found in session")
                return jsonify({"error": "No metadata in session"}), 400

            user_id = metadata.get('user_id')
            if not user_id:
                logger.error("❌ No user_id found in session metadata")
                return jsonify({"error": "No user_id in metadata"}), 400

            # Ensure user_id is a string
            user_id = str(user_id)
            logger.info(f"✅ Valid user_id found in metadata: {user_id}")

            # Log full session data for debugging
            logger.info(f"Full session data: {session}")

            # Proceed with payment handling
            handle_successful_payment(session)

        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            handle_subscription_cancelled(subscription)

        return jsonify(success=True), 200

    except ValueError as e:
        logger.error(f"💥 WEBHOOK VALUE ERROR: {e}")
        return jsonify({"error": str(e)}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"💥 SIGNATURE VERIFICATION FAILED: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        logger.error(f"💥 UNEXPECTED ERROR: {e}")
        logger.error(f"Stacktrace: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500

def handle_successful_payment(session):
    """Handle successful payment webhook"""
    logger.info("=== PROCESSING SUCCESSFUL PAYMENT ===")
    logger.info(f"Full session data: {session}")

    # Extract essential data with detailed logging
    checkout_session_id = session.get("id")
    logger.info(f"Processing checkout session ID: {checkout_session_id}")

    # Get user ID from session metadata with verification
    metadata = session.get("metadata", {})
    logger.info(f"Session metadata: {metadata}")

    user_id = metadata.get("user_id")
    logger.info(f"Extracted user_id from metadata: {user_id}")

    if not user_id:
        logger.error("❌ No user ID found in session metadata")
        return

    # Ensure user_id is string
    user_id = str(user_id)
    logger.info(f"Processing payment for user ID: {user_id}")

    # Get subscription ID with verification
    subscription_id = session.get('subscription')
    logger.info(f"Subscription ID from session: {subscription_id}")

    # Get customer ID with verification
    customer_id = session.get('customer')
    logger.info(f"Customer ID from session: {customer_id}")

    try:
        # Get reference to user document
        user_ref = db.collection("users").document(user_id)
        logger.info(f"Got reference to user document: {user_id}")

        # First verify if the document exists
        user_doc = user_ref.get()
        if user_doc.exists:
            logger.info(f"Found existing user document: {user_doc.to_dict()}")
        else:
            logger.info("Creating new user document")

        # Prepare update data with all necessary fields
        update_data = {
            'is_premium': True,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'checkout_session_id': checkout_session_id,
            'subscription_status': 'active',
            'premium_updated_at': firestore.SERVER_TIMESTAMP,
            'subscription_id': subscription_id,
            'stripe_customer_id': customer_id
        }

        logger.info(f"Preparing to update with data: {update_data}")

        # Try updating with retry logic
        max_retries = 3
        success = False
        last_error = None

        for attempt in range(max_retries):
            try:
                # First attempt: try update
                if attempt == 0:
                    user_ref.update(update_data)
                # Subsequent attempts: try set with merge
                else:
                    user_ref.set(update_data, merge=True)

                logger.info(f"✅ Update attempt {attempt + 1} successful")
                success = True
                break
            except Exception as e:
                last_error = e
                logger.error(f"❌ Update attempt {attempt + 1} failed: {e}")
                time.sleep(1)  # Wait before retry

        if not success:
            logger.error(f"All update attempts failed. Last error: {last_error}")
            return

        # Verify the update
        time.sleep(1)  # Wait for Firestore consistency
        updated_doc = user_ref.get()

        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            logger.info(f"Updated user data: {updated_data}")

            if updated_data.get('is_premium') == True:
                logger.info(f"✅ SUCCESS: Premium status verified for user {user_id}")

                # Send success message to user
                try:
                    message = "🎉 Congratulations! You are now a Premium member. Enjoy exclusive deals!"
                    bot.send_message(chat_id=user_id, text=message)
                    logger.info(f"✅ Success notification sent to user {user_id}")
                except Exception as msg_err:
                    logger.error(f"Failed to send success message: {msg_err}")
            else:
                logger.error(f"❌ FAILURE: Premium status not set for user {user_id}")
        else:
            logger.error(f"❌ FAILURE: User document {user_id} not found after update!")

    except Exception as e:
        logger.error(f"💥 CRITICAL ERROR updating premium status: {e}")
        logger.error(f"Stacktrace: {traceback.format_exc()}")

def handle_subscription_cancelled(subscription):
    """Handle subscription cancellation webhook - SIMPLIFIED"""
    try:
        # Log the full subscription data for debugging
        logger.info(f"SUBSCRIPTION CANCELLED EVENT: {subscription}")

        # Get subscription ID
        subscription_id = subscription.get("id")
        if not subscription_id:
            logger.error("No subscription ID found in cancellation event")
            return

        # Get customer ID from subscription
        customer_id = subscription.get("customer")
        if not customer_id:
            logger.error("No customer ID found in cancellation event")
            return

        logger.info(f"Looking for user with customer_id: {customer_id}")

        # Find user by customer ID - simplest approach
        users_ref = db.collection("users")
        query = users_ref.where("stripe_customer_id", "==", customer_id).limit(1)
        docs = query.get()

        if not docs:
            logger.error(f"❌ No user found with customer_id: {customer_id}")

            # Fallback to subscription ID
            logger.info(f"Trying to find user by subscription_id: {subscription_id}")
            query = users_ref.where("subscription_id", "==", subscription_id).limit(1)
            docs = query.get()

            if not docs:
                logger.error(f"❌ No user found for subscription {subscription_id} either")
                return

        # Get the user document
        user_doc = docs[0]
        user_id = user_doc.id
        logger.info(f"Found user {user_id} for cancelled subscription")

        # Simple update to remove premium status
        update_data = {
            "is_premium": False,
            "subscription_id": None,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        # Log what we're about to update
        logger.info(f"About to update user {user_id} with: {update_data}")

        # Update the user document
        user_doc.reference.update(update_data)
        logger.info(f"✅ Updated user {user_id} - removed premium status")

        # Verify the update was successful
        time.sleep(1)  # Wait a moment for Firestore to process
        updated_doc = user_doc.reference.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            logger.info(f"VERIFICATION - User data in Firestore: {updated_data}")

            if updated_data.get('is_premium') == False:
                logger.info(f"✅ SUCCESS: Premium status was removed for user {user_id}")
            else:
                logger.error(f"❌ FAILURE: Premium status was NOT removed for user {user_id}")
                # Emergency update
                user_doc.reference.set({'is_premium': False}, merge=True)
                logger.info("💥 Made emergency update to remove premium status")

        # Send cancellation notification
        try:
            message = "⚠️ Your Premium subscription has been canceled. You can re-subscribe anytime!"
            bot.send_message(chat_id=user_id, text=message)
            logger.info(f"❌ Notification sent: User {user_id} downgraded from Premium")
        except Exception as msg_err:
            logger.error(f"Failed to send cancellation message: {msg_err}")

    except Exception as e:
        logger.error(f"💥 CRITICAL ERROR handling subscription cancellation: {e}")
        logger.error(f"Stacktrace: {traceback.format_exc()}")

if __name__ == '__main__':
    try:
        port = 5000  # Using port 5000 as per Replit requirements
        logger.info(f"Attempting to start webhook server on port {port}")

        # Check if port is available
        if wait_for_port_available(port):
            logger.info(f"Port {port} is available, starting server")
            # Disable reloader to prevent duplicate processes
            app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
        else:
            error_msg = f"Could not start webhook server - port {port} is in use after multiple attempts"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")
        raise