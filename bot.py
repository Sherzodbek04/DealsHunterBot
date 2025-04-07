import logging
import os
import sys
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from user_manager import UserManager
from deal_fetcher import DealFetcher
import signal
import firebase_admin
from firebase_admin import credentials, firestore
from translations.lang import TRANSLATIONS
from stripe_config import create_checkout_session, cancel_stripe_subscription
from notification_manager import NotificationManager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for more verbose output
)

logger = logging.getLogger(__name__)
user_manager = UserManager()
deal_fetcher = DealFetcher()
notification_manager = NotificationManager()

# Keep track of running application
telegram_app = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    cleanup()
    os._exit(0)

def cleanup():
    """Cleanup function to stop all services"""
    logger.info("Cleaning up resources...")
    global telegram_app
    if telegram_app:
        logger.info("Stopping Telegram bot...")
        telegram_app.stop()
        telegram_app = None

def get_store_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Get keyboard with store buttons"""
    store_buttons = []
    for store_id in deal_fetcher.get_available_stores():
        store_name = deal_fetcher.get_store_name(store_id)
        store_buttons.append([InlineKeyboardButton(f"🏪 {store_name}", callback_data=f"store_{store_id}")])

    store_buttons.append([InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")])
    return InlineKeyboardMarkup(store_buttons)

def get_store_deals_keyboard(store_id: str, page: int, total_pages: int, lang: str, is_notification: bool = False) -> InlineKeyboardMarkup:
    """Get keyboard for store deals with pagination"""
    keyboard = []

    # Only show navigation buttons if not in notification mode
    if not is_notification:
        # Add page indicator
        if total_pages > 1:
            keyboard.append([
                InlineKeyboardButton(
                    TRANSLATIONS[lang]["page_indicator"].format(current=page, total=total_pages),
                    callback_data="noop"
                )
            ])

        # Add Load More/Previous navigation buttons
        if page > 1 or page < total_pages:
            navigation = []
            if page > 1:
                navigation.append(
                    InlineKeyboardButton(
                        TRANSLATIONS[lang]["load_previous"],
                        callback_data=f"page_{store_id}_{page-1}"
                    )
                )
            if page < total_pages:
                navigation.append(
                    InlineKeyboardButton(
                        TRANSLATIONS[lang]["load_more"],
                        callback_data=f"page_{store_id}_{page+1}"
                    )
                )
            if navigation:
                keyboard.append(navigation)

    # Add action buttons
    keyboard.extend([
        [InlineKeyboardButton(TRANSLATIONS[lang]["back_to_stores_button"], callback_data="check_sales")],
        [InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")]
    ])

    return InlineKeyboardMarkup(keyboard)

def get_main_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = {
        'en': ["🏷 Check Sales", "🔔 Set Notification", "🌐 Change Language", "⭐️ Premium"],
        'uz': ["🏷 Chegirmalar", "🔔 Bildirishnoma", "🌐 Tilni o'zgartirish", "⭐️ Premium"],
        'ru': ["🏷 Скидки", "🔔 Уведомления", "🌐 Язык", "⭐️ Премиум"]
    }
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data)] for text, data in zip(
            buttons[lang], 
            ["check_sales", "notifications", "change_language", "premium"])
    ])

def get_language_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Get language selection keyboard markup"""
    keyboard = [[
        InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    ], 
    [
        InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")
    ]]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Get back to main menu keyboard markup"""
    keyboard = [[
        InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")
    ]]
    return InlineKeyboardMarkup(keyboard)

def get_premium_keyboard(is_premium: bool, lang: str) -> InlineKeyboardMarkup:
    """Get premium keyboard markup"""
    if not is_premium:
        keyboard = [[
            InlineKeyboardButton(TRANSLATIONS[lang]["premium_button"], callback_data="upgrade_premium")
        ],
        [
            InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")
        ]]
        return InlineKeyboardMarkup(keyboard)
    else:
        keyboard = [[
            InlineKeyboardButton(TRANSLATIONS[lang]["cancel_subscription"], callback_data="cancel_subscription")
        ],
        [
            InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")
        ]]
        return InlineKeyboardMarkup(keyboard)

def get_notifications_menu_keyboard(user_id: str, lang: str) -> InlineKeyboardMarkup:
    """Get keyboard for notifications menu"""
    keyboard = []

    # Get current notifications
    notifications = notification_manager.get_user_notifications(str(user_id))
    store_notifications = {}
    for notif in notifications:
        store = notif['store']
        if store not in store_notifications:
            store_notifications[store] = 0
        store_notifications[store] += 1

    # Add button for each available store
    for store_id in deal_fetcher.get_available_stores():
        store_name = deal_fetcher.get_store_name(store_id)
        status = "✅" if store_id in store_notifications else "⚪️"
        count = f" ({store_notifications[store_id]})" if store_id in store_notifications else ""
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {store_name}{count}",
                callback_data=f"toggle_notify_{store_id}"
            )
        ])

    keyboard.append([InlineKeyboardButton(TRANSLATIONS[lang]["back_button"], callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.effective_user.id
        logger.info(f"Start command received from user {user_id}")

        user_manager.create_user_if_not_exists(user_id)
        logger.debug(f"User {user_id} initialized/verified in database")

        lang = user_manager.get_user_language(user_id)
        logger.debug(f"Retrieved language '{lang}' for user {user_id}")

        await update.message.reply_text(
            TRANSLATIONS[lang]["welcome"],
            reply_markup=get_main_menu_keyboard(lang)
        )
        logger.info(f"Sent welcome message to user {user_id} in language {lang}")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")
        await update.message.reply_text(
            "Sorry, there was an error processing your command. Please try again later."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    try:
        user_id = query.from_user.id
        lang = user_manager.get_user_language(user_id)
        logger.info(f"Button callback received: {query.data} from user {user_id} with language {lang}")

        if query.data == "main_menu":
            await query.edit_message_text(
                TRANSLATIONS[lang]["welcome"],
                reply_markup=get_main_menu_keyboard(lang))

        elif query.data == "check_sales":
            await query.edit_message_text(
                TRANSLATIONS[lang]["store_section_title"],
                reply_markup=get_store_keyboard(lang))

        elif query.data.startswith("store_"):
            store_id = query.data.split("_")[1]
            page = 1
            is_premium = user_manager.is_user_premium(user_id)

            # Get deals with premium status
            deals, total_pages = deal_fetcher.get_store_deals(store_id, page, is_premium)
            store_name = deal_fetcher.get_store_name(store_id)

            header = TRANSLATIONS[lang]["store_deals_header"].format(store_name)
            message = header + "\n\n" + deal_fetcher.format_deals_message(deals, lang)

            # Don't show pagination in notification mode
            is_notification = query.data.startswith("notify_")
            await query.edit_message_text(
                message,
                reply_markup=get_store_deals_keyboard(store_id, page, total_pages, lang, is_notification),
                disable_web_page_preview=True
            )

        elif query.data.startswith("page_"):
            _, store_id, page = query.data.split("_")
            page = int(page)
            is_premium = user_manager.is_user_premium(user_id)

            # Get deals with premium status
            deals, total_pages = deal_fetcher.get_store_deals(store_id, page, is_premium)
            store_name = deal_fetcher.get_store_name(store_id)

            header = TRANSLATIONS[lang]["store_deals_header"].format(store_name)

            # If we have deals for this page, display them
            if deals:
                message = header + "\n\n" + deal_fetcher.format_deals_message(deals, lang)
            else:
                # For basic users who reach their limit
                if not is_premium and page > 3:
                    message = header + "\n\n" + TRANSLATIONS[lang]["premium_info"]
                else:
                    message = header + "\n\n" + TRANSLATIONS[lang]["no_deals_found"]

            # Keep pagination for regular deal viewing
            await query.edit_message_text(
                message,
                reply_markup=get_store_deals_keyboard(store_id, page, total_pages, lang, False),
                disable_web_page_preview=True
            )

        elif query.data.startswith("notify_"):
            store_id = query.data.split("_")[1]
            is_premium = user_manager.is_user_premium(user_id)

            # Check if user can add notification
            can_add = notification_manager.can_add_notification(str(user_id), store_id, is_premium)
            if not can_add:
                # Show appropriate limit message
                limit_message = TRANSLATIONS[lang]["notification_limit"]
                if is_premium:
                    limit_message = "You've reached your daily notification limit (8 notifications). Try again tomorrow!"
                else:
                    limit_message = "Basic users can only set notifications for one store (up to 3 times per day). Upgrade to Premium for more!"

                await query.edit_message_text(
                    limit_message,
                    reply_markup=get_premium_keyboard(False, lang)
                )
                return

            # Add notification
            success = notification_manager.add_notification(str(user_id), store_id, is_premium)
            if success:
                # Show success message with current notification status
                notifications = notification_manager.get_user_notifications(str(user_id))
                store_count = len(set(n['store'] for n in notifications))

                status_message = (
                    f"✅ Notification set for {deal_fetcher.get_store_name(store_id)}!\n\n"
                    f"You have notifications set for {store_count} store(s).\n"
                    f"Today's notifications: {len([n for n in notifications if n.get('last_sent')])}"
                )

                await query.edit_message_text(
                    status_message,
                    reply_markup=get_store_deals_keyboard(store_id, 1, 3, lang, True)
                )
            else:
                await query.edit_message_text(
                    "Failed to set notification. Please try again later.",
                    reply_markup=get_store_deals_keyboard(store_id, 1, 3, lang, True)
                )

        elif query.data == "notifications":
            logger.info(f"User {user_id} opened notifications menu")
            await query.edit_message_text(
                TRANSLATIONS[lang]["notifications_msg"],
                reply_markup=get_notifications_menu_keyboard(user_id, lang))

        elif query.data == "noop":
            # No operation button (used for display-only buttons like page indicators)
            await query.answer()

        elif query.data.startswith("toggle_notify_"):
            store_id = query.data.split("_")[2]
            is_premium = user_manager.is_user_premium(user_id)
            logger.info(f"User {user_id} (Premium: {is_premium}) attempting to toggle notification for store {store_id}")

            try:
                # Toggle notification in Firestore
                success = notification_manager.toggle_notification(str(user_id), store_id, is_premium)
                if success:
                    logger.info(f"Successfully toggled notification for user {user_id} and store {store_id}")
                    # Get updated notifications to show correct status
                    await query.edit_message_text(
                        TRANSLATIONS[lang]["notification_success"],
                        reply_markup=get_notifications_menu_keyboard(user_id, lang)
                    )
                else:
                    logger.error(f"Failed to toggle notification for user {user_id} and store {store_id}")
                    # Show appropriate limit message
                    limit_message = TRANSLATIONS[lang]["notification_limit"]
                    if is_premium:
                        limit_message = TRANSLATIONS[lang]["notification_limit_premium"]
                    else:
                        limit_message = TRANSLATIONS[lang]["notification_limit_basic"]

                    await query.edit_message_text(
                        limit_message,
                        reply_markup=get_premium_keyboard(False, lang)
                    )
            except Exception as e:
                logger.error(f"Error handling notification toggle for user {user_id}: {str(e)}")
                await query.edit_message_text(
                    "An error occurred. Please try again or use /start to restart.",
                    reply_markup=get_main_menu_keyboard(lang)
                )

        elif query.data == "change_language":
            await query.edit_message_text(
                TRANSLATIONS[lang]["change_language_msg"],
                reply_markup=get_language_keyboard(lang))

        elif query.data.startswith("lang_"):
            selected_lang = query.data.split("_")[1]
            user_id = query.from_user.id

            user_manager.save_user_language(user_id, selected_lang)
            logger.info(f"Language changed to {selected_lang} for user {user_id}")

            await query.edit_message_text(
                TRANSLATIONS[selected_lang]["language_set"],
                reply_markup=get_back_to_main_menu_keyboard(selected_lang))

        elif query.data == "premium":
            is_premium = user_manager.is_user_premium(user_id)
            await query.edit_message_text(
                TRANSLATIONS[lang]["premium_info"],
                reply_markup=get_premium_keyboard(is_premium, lang))

        elif query.data == "upgrade_premium":
            checkout_url = create_checkout_session(str(user_id))
            if checkout_url:
                await query.edit_message_text(
                    TRANSLATIONS[lang]["checkout_session_text"] + checkout_url,
                    disable_web_page_preview=True
                )
            else:
                await query.edit_message_text(
                    "Sorry, there was an error creating your checkout session. Please try again later.",
                    reply_markup=get_back_to_main_menu_keyboard(lang)
                )
        elif query.data == "cancel_subscription":
            user_id = query.from_user.id
            logger.info(f"🔄 Starting subscription cancellation for user {user_id}")

            is_premium = user_manager.is_user_premium(user_id)
            if not is_premium:
                logger.warning(f"User {user_id} tried to cancel subscription but isn't marked as premium")
                await query.edit_message_text(
                    "⚠️ You don't appear to have an active premium subscription.",
                    reply_markup=get_back_to_main_menu_keyboard(lang)
                )
                return

            await query.edit_message_text(
                "⏳ Processing your cancellation request...",
                reply_markup=None
            )

            customer_id = user_manager.get_stripe_customer_id(user_id)
            if not customer_id:
                customer_id = get_customer_id_by_user_id(str(user_id))

            if customer_id:
                logger.info(f"✅ Found Stripe customer ID: {customer_id}")

                subscription_id = get_active_subscription_by_customer(customer_id)

                if subscription_id:
                    logger.info(f"✅ Found active subscription: {subscription_id}")

                    success = cancel_stripe_subscription(subscription_id)
                    logger.info(f"Cancellation result: {'✅ Success' if success else '❌ Failed'}")

                    if success:
                        user_manager.users_ref.document(str(user_id)).update({
                            'is_premium': False,
                            'subscription_id': None
                        })
                        logger.info(f"Updated premium status to False for user {user_id}")

                        message = "✅ Your subscription has been canceled successfully. You can re-subscribe anytime!"
                        await query.edit_message_text(
                            message,
                            reply_markup=get_back_to_main_menu_keyboard(lang)
                        )
                    else:
                        await query.edit_message_text(
                            "❌ Error canceling your subscription. Please try again later.",
                            reply_markup=get_back_to_main_menu_keyboard(lang)
                        )
                else:
                    logger.warning(f"⚠️ No active subscription found for customer {customer_id}")

                    if is_premium:
                        user_manager.users_ref.document(str(user_id)).update({
                            'is_premium': False,
                            'subscription_id': None
                        })
                        logger.info(f"Fixed premium status inconsistency for user {user_id}")

                    await query.edit_message_text(
                        "⚠️ You don't have an active subscription with us.",
                        reply_markup=get_back_to_main_menu_keyboard(lang)
                    )
            else:
                logger.warning(f"⚠️ No Stripe customer found for user {user_id}")

                if is_premium:
                    user_manager.users_ref.document(str(user_id)).update({
                        'is_premium': False,
                        'subscription_id': None
                    })
                    logger.info(f"Fixed premium status inconsistency for user {user_id}")

                await query.edit_message_text(
                    "⚠️ No subscription found. Your premium status has been reset.",
                    reply_markup=get_back_to_main_menu_keyboard(lang)
                )

    except Exception as e:
        logger.error(f"Error in button callback: {str(e)}")
        await query.edit_message_text(
            "An error occurred. Please try again or use /start to restart.",
            reply_markup=get_main_menu_keyboard("en"))

def main() -> None:
    """Start the bot with enhanced error handling and logging"""
    global telegram_app
    logger.info("Starting bot initialization...")

    cleanup()

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        sys.exit(1)

    logger.info("Bot token verified, proceeding with initialization")

    try:
        # Initialize Firebase if not already initialized
        if not len(firebase_admin._apps):
            cred = credentials.Certificate("credentials.json")
            firebase_admin.initialize_app(cred)
            logger.debug("Firebase initialized successfully")
        else:
            logger.debug("Firebase already initialized")

        logger.debug("Building Telegram application...")
        telegram_app = Application.builder().token(token).build()
        logger.info("Successfully built Telegram application")

        logger.debug("Adding command handlers...")
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CallbackQueryHandler(button_callback))
        logger.info("Successfully added command handlers")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers configured")

        logger.info("Starting bot polling...")
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot polling started successfully")

    except Exception as e:
        logger.error(f"Critical error during bot initialization: {str(e)}")
        logger.exception("Full traceback:")
        cleanup()
        sys.exit(1)

if __name__ == '__main__':
    try:
        logger.info("=== STARTING BOT ===")
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        cleanup()
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        logger.exception("Full traceback:")
        cleanup()
        sys.exit(1)

def get_customer_id_by_user_id(user_id):
    #Implementation for getting customer id from user id.  Placeholder.
    return None

def get_active_subscription_by_customer(customer_id):
    #Implementation for getting active subscription. Placeholder.
    return None