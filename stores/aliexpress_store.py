from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AliexpressStore:
    def __init__(self):
        # Generate 100 test products with varied data
        self.test_deals = []
        for i in range(100):
            # Vary prices and discounts for more realistic data
            base_price = 9.99 + (i * 0.5)  # Lower price range for Aliexpress
            discount = 40.0 + (i % 50)  # Discounts between 40% and 90%
            original_price = base_price / (1 - discount/100)
            
            self.test_deals.append({
                'id': f'ALI_{i}',  # Unique identifier for API integration
                'title': f'AliExpress Product {i}',
                'price': base_price,
                'original_price': original_price,
                'url': f'https://aliexpress.com/sample/product_{i}',
                'discount_percentage': discount,
                'stock_status': 'In Stock' if i % 5 != 0 else 'Limited Stock',
                'rating': 4.0 + (i % 2),  # Alternating between 4.0 and 5.0
                'reviews_count': 500 + i,
                'category': f'Category {i % 5}',  # 5 different categories
                'brand': f'Brand {i % 3}',  # 3 different brands
                'shipping': 'Free Shipping' if i % 3 == 0 else 'Standard Shipping',
                'delivery_time': f'{5 + (i % 10)}-{15 + (i % 10)} days',
                'last_updated': '2024-03-06'  # Simulated last update time
            })

    def fetch_deals(self, page: int = 1, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch deals from AliExpress with pagination and filtering
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
            logger.error(f"Error fetching deals from AliExpress: {str(e)}")
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
            elif key == 'free_shipping':
                filtered_deals = [d for d in filtered_deals if d['shipping'] == 'Free Shipping']
        
        return filtered_deals

    def get_store_name(self) -> str:
        """Get display name for the store"""
        return "AliExpress"

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
                'shipping': raw_deal.get('shipping'),
                'delivery_time': raw_deal.get('delivery_time'),
                'last_updated': raw_deal.get('last_updated')
            }
        }

    def get_total_deals(self, filters: Optional[Dict] = None) -> int:
        """Get total number of deals (for pagination)"""
        if filters:
            filtered_deals = self._apply_filters(self.test_deals, filters)
            return len(filtered_deals)
        return len(self.test_deals)