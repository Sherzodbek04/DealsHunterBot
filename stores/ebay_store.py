from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class EbayStore:
    def __init__(self):
        # Generate 100 test products with varied data
        self.test_deals = []
        for i in range(100):
            # Vary prices and discounts for more realistic data
            base_price = 19.99 + (i * 1.0)  # Medium price range for eBay
            discount = 25.0 + (i % 35)  # Discounts between 25% and 60%
            original_price = base_price / (1 - discount/100)
            
            self.test_deals.append({
                'id': f'EBAY_{i}',  # Unique identifier for API integration
                'title': f'eBay Product {i}',
                'price': base_price,
                'original_price': original_price,
                'url': f'https://ebay.com/sample/product_{i}',
                'discount_percentage': discount,
                'stock_status': 'In Stock' if i % 5 != 0 else 'Limited Stock',
                'rating': 3.8 + (i % 2),  # Alternating between 3.8 and 4.8
                'reviews_count': 800 + i,
                'category': f'Category {i % 5}',  # 5 different categories
                'brand': f'Brand {i % 3}',  # 3 different brands
                'condition': 'New' if i % 3 == 0 else 'Used - Like New',
                'seller_rating': 98.5 + (i % 1.5),  # Seller ratings between 98.5% and 100%
                'shipping': 'Free Shipping' if i % 2 == 0 else 'Standard Shipping',
                'last_updated': '2024-03-06'  # Simulated last update time
            })

    def fetch_deals(self, page: int = 1, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch deals from eBay with pagination and filtering
        Args:
            page: Page number (1-based)
            limit: Number of items per page
            filters: Optional dictionary of filters (for future API implementation)
        """
        try:
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            
            # Get deals for current page
            deals = self.test_deals[start_idx:end_idx]
            
            # Apply filters if provided (simulating API filtering)
            if filters:
                deals = self._apply_filters(deals, filters)
            
            return [self.format_deal(deal) for deal in deals]
            
        except Exception as e:
            logger.error(f"Error fetching deals from eBay: {str(e)}")
            return []

    def _apply_filters(self, deals: List[Dict], filters: Dict) -> List[Dict]:
        """Apply filters to deals (simulating API filtering)"""
        filtered_deals = deals.copy()
        
        for key, value in filters.items():
            if key == 'min_discount':
                filtered_deals = [d for d in filtered_deals if d['discount_percentage'] >= value]
            elif key == 'max_price':
                filtered_deals = [d for d in filtered_deals if d['price'] <= value]
            elif key == 'category':
                filtered_deals = [d for d in filtered_deals if d['category'] == value]
            elif key == 'brand':
                filtered_deals = [d for d in filtered_deals if d['brand'] == value]
            elif key == 'in_stock':
                filtered_deals = [d for d in filtered_deals if d['stock_status'] == 'In Stock']
            elif key == 'condition':
                filtered_deals = [d for d in filtered_deals if d['condition'] == value]
            elif key == 'free_shipping':
                filtered_deals = [d for d in filtered_deals if d['shipping'] == 'Free Shipping']
        
        return filtered_deals

    def get_store_name(self) -> str:
        """Get display name for the store"""
        return "eBay"

    def format_deal(self, raw_deal: Dict) -> Dict:
        """Format the raw deal data into standard format"""
        return {
            'id': raw_deal['id'],
            'title': raw_deal['title'],
            'price': float(raw_deal['price']),
            'original_price': float(raw_deal['original_price']),
            'url': raw_deal['url'],
            'store': self.get_store_name(),
            'discount_percentage': float(raw_deal['discount_percentage']),
            'metadata': {
                'stock_status': raw_deal.get('stock_status'),
                'rating': raw_deal.get('rating'),
                'reviews_count': raw_deal.get('reviews_count'),
                'category': raw_deal.get('category'),
                'brand': raw_deal.get('brand'),
                'condition': raw_deal.get('condition'),
                'seller_rating': raw_deal.get('seller_rating'),
                'shipping': raw_deal.get('shipping'),
                'last_updated': raw_deal.get('last_updated')
            }
        }

    def get_total_deals(self, filters: Optional[Dict] = None) -> int:
        """Get total number of deals (for pagination)"""
        if filters:
            filtered_deals = self._apply_filters(self.test_deals, filters)
            return len(filtered_deals)
        return len(self.test_deals)