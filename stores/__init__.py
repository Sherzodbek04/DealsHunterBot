from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseStore(ABC):
    @abstractmethod
    def fetch_deals(self, page: int = 1, limit: int = 5) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_store_name(self) -> str:
        pass

    def format_deal(self, deal: Dict[str, Any]) -> str:
        return f"""
🏷 {deal['title']}
💰 Price: {deal['price']}
🔗 Link: {deal['url']}
📍 Store: {self.get_store_name()}
"""
