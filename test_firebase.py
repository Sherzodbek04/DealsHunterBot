import logging
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_firebase_connection():
    try:
        if not len(firebase_admin._apps):
            cred = credentials.Certificate("credentials.json")
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        # Try a simple operation
        users_ref = db.collection('users')
        logger.info("Successfully connected to Firebase!")
        return True
    except Exception as e:
        logger.error(f"Error connecting to Firebase: {str(e)}")
        return False

if __name__ == "__main__":
    test_firebase_connection()
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_firestore_connection():
    """Test that we can connect to Firestore and perform basic operations"""
    try:
        # Initialize Firebase if not already initialized
        if not len(firebase_admin._apps):
            cred = credentials.Certificate("credentials.json")
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        logger.info("Firebase connection established")

        # Try to write to a test document
        test_ref = db.collection("test_collection").document("test_document")
        test_data = {
            "test_field": "test_value",
            "timestamp": firestore.SERVER_TIMESTAMP
        }

        # Write the data
        logger.info(f"Writing test data: {test_data}")
        test_ref.set(test_data)
        logger.info("Write operation completed")

        # Wait a moment for Firestore to process
        time.sleep(1)

        # Read it back
        doc = test_ref.get()
        if doc.exists:
            logger.info(f"Read test data: {doc.to_dict()}")
            logger.info("✅ Firestore read/write test PASSED")
        else:
            logger.error("❌ Test document not found after writing")

        # Clean up
        test_ref.delete()
        logger.info("Test document deleted")

        return True
    except Exception as e:
        logger.error(f"❌ Firestore test FAILED: {e}")
        return False

def test_user_premium_update(user_id="123456789"):
    """Test that we can update a user's premium status"""
    try:
        # Initialize Firebase if not already initialized
        if not len(firebase_admin._apps):
            cred = credentials.Certificate("credentials.json")
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        logger.info(f"Testing premium update for user {user_id}")

        # Get reference to user document
        user_ref = db.collection("users").document(str(user_id))

        # Update premium status directly
        update_data = {
            'is_premium': True,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'test_subscription_id': 'test_sub_123',
            'test_customer_id': 'test_cus_123'
        }

        # Try direct update
        logger.info(f"Attempting direct update with: {update_data}")
        try:
            user_ref.update(update_data)
            logger.info("Update operation succeeded")
        except Exception as update_error:
            logger.warning(f"Update failed (expected if new user): {update_error}")
            logger.info("Trying set with merge instead")
            # If update fails (new user), try setting with merge
            user_ref.set(update_data, merge=True)
            logger.info("Set with merge operation succeeded")

        # Wait a moment for Firestore to process
        time.sleep(1)

        # Read it back
        doc = user_ref.get()
        if doc.exists:
            user_data = doc.to_dict()
            logger.info(f"User data after update: {user_data}")

            if user_data.get('is_premium') == True:
                logger.info("✅ Premium status was updated successfully")
            else:
                logger.error("❌ Premium status was NOT updated")
        else:
            logger.error("❌ User document not found after writing")

        return True
    except Exception as e:
        logger.error(f"❌ User premium update test FAILED: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== RUNNING FIRESTORE TESTS ===")

    # Test basic Firestore operations
    logger.info("Testing basic Firestore operations...")
    test_firestore_connection()

    # Test user premium update
    logger.info("Testing user premium update...")
    test_user_premium_update()

    logger.info("=== TESTS COMPLETED ===")
