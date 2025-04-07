import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from stores.amazon_store import AmazonStore
from stores.aliexpress_store import AliexpressStore
from stores.ebay_store import EbayStore
from stores.shein_store import SheinStore

logger = logging.getLogger(__name__)

class Deal:
    def __init__(self, title: str, price: float, original_price: float, 
                 link: str, platform: str, discount_percentage: float):
        self.title = title
        self.price = price
        self.original_price = original_price
        self.link = link
        self.platform = platform
        self.discount_percentage = discount_percentage
        self.fetched_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'price': self.price,
            'original_price': self.original_price,
            'url': self.link,
            'store': self.platform,
            'discount_percentage': self.discount_percentage,
            'fetched_at': self.fetched_at.isoformat()
        }

class DealFetcher:
    def __init__(self):
        self.stores = {
            'amazon': AmazonStore(),
            'aliexpress': AliexpressStore(),
            'ebay': EbayStore(),
            'shein': SheinStore()
        }
        self.deals_per_page = 5
        self.max_deals_per_day = 15  # 3 pages for basic users

    def get_store_deals(self, store_name: str, page: int = 1, is_premium: bool = False, filters: Optional[Dict] = None) -> Tuple[List[Dict], int]:
        """Fetch deals from a specific store with pagination

        Args:
            store_name: Name of the store to fetch deals from
            page: Page number to fetch (starts at 1)
            is_premium: Whether user is premium (affects pagination limits)
            filters: Optional dictionary of filters to apply

        Returns:
            Tuple of (deals list, total pages)
        """
        if store_name not in self.stores:
            logger.warning(f"Attempted to fetch deals for unknown store: {store_name}")
            return [], 0

        try:
            store = self.stores[store_name]
            
            # Get total number of deals for pagination
            total_deals = store.get_total_deals(filters)
            
            # Calculate total pages based on user status
            if is_premium:
                total_pages = (total_deals + self.deals_per_page - 1) // self.deals_per_page
            else:
                # Basic users limited to 3 pages (15 deals)
                total_pages = min(3, (total_deals + self.deals_per_page - 1) // self.deals_per_page)

            # For basic users, enforce the 15 deals limit
            if not is_premium and page > 3:
                return [], total_pages

            # Get deals for current page
            deals = store.fetch_deals(page=page, limit=self.deals_per_page, filters=filters)

            # For basic users, don't return more than max_deals_per_day
            if not is_premium:
                remaining_deals = self.max_deals_per_day - ((page - 1) * self.deals_per_page)
                if remaining_deals <= 0:
                    return [], total_pages
                deals = deals[:remaining_deals]

            return deals, total_pages

        except Exception as e:
            logger.error(f"Error fetching deals for store {store_name}: {str(e)}")
            return [], 0

    def get_all_deals(self, page: int = 1, filters: Optional[Dict] = None) -> Tuple[List[Dict], int]:
        """Fetch deals from all stores with pagination"""
        all_deals = []
        for store_name, store in self.stores.items():
            try:
                deals = store.fetch_deals(page=page, limit=self.deals_per_page, filters=filters)
                all_deals.extend(deals)
            except Exception as e:
                logger.error(f"Error fetching deals for store {store_name}: {str(e)}")
                continue

        # Sort by discount percentage and paginate
        sorted_deals = sorted(all_deals, key=lambda x: float(x.get('discount_percentage', '0')), reverse=True)
        start_idx = (page - 1) * self.deals_per_page
        end_idx = start_idx + self.deals_per_page
        
        total_deals = len(sorted_deals)
        total_pages = (total_deals + self.deals_per_page - 1) // self.deals_per_page
        
        return sorted_deals[start_idx:end_idx], total_pages

    def format_deals_message(self, deals: List[Dict], lang: str = 'en') -> str:
        """Format deals into a readable message with proper translation"""
        from translations.lang import TRANSLATIONS

        if not deals:
            return TRANSLATIONS[lang]['no_deals_found']

        # Just take the first few deals to avoid message length issues
        display_deals = deals[:5]  # Display at most 5 deals

        message = ""
        deal_count = len(display_deals)
        message += f"{TRANSLATIONS[lang]['deal_count_label']} {deal_count}\n\n"

        for i, deal in enumerate(display_deals, 1):
            message += f"{i}. {TRANSLATIONS[lang]['product_name_label']} {deal['title']}\n"
            message += f"{TRANSLATIONS[lang]['price_label']} ${deal['price']:.2f}\n"
            message += f"{TRANSLATIONS[lang]['original_price_label']} ${deal['original_price']:.2f}\n"
            message += f"{TRANSLATIONS[lang]['discount_label']} {deal['discount_percentage']:.1f}%\n"
            message += f"🏪 {deal.get('store', 'Unknown')}\n"
            message += f"🔗 {deal.get('url', '#')}\n\n"

        message += TRANSLATIONS[lang]['notification_info']
        return message

    def get_available_stores(self) -> List[str]:
        """Get list of available stores"""
        return list(self.stores.keys())

    def get_store_name(self, store_id: str) -> str:
        """Get display name for store"""
        store = self.stores.get(store_id)
        return store.get_store_name() if store else store_id.capitalize()