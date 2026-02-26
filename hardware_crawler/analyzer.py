from typing import List, Optional
from .models import Product

class HardwareAnalyzer:
    """Analyzes hardware components and prices."""
    
    def __init__(self, product_database: List[Product]):
        self.db = product_database
        
    def find_comparable_products(self, target_product: Product, tolerance_percent: float = 0.1) -> List[Product]:
        """Finds products within +/- tolerance percentage of performance."""
        target_score = target_product.performance_score
        
        if target_score is None:
            return []

        min_score = target_score * (1 - tolerance_percent)
        max_score = target_score * (1 + tolerance_percent)
        
        matches = [
            p for p in self.db 
            if p.type == target_product.type 
            and p.performance_score is not None
            and min_score <= p.performance_score <= max_score
        ]
        # Sort by performance desc
        matches.sort(key=lambda x: x.performance_score, reverse=True)
        return matches

    def find_product_by_name(self, name_query: str) -> Optional[Product]:
        """Simple fuzzy search for product by name."""
        name_query = name_query.lower()
        # Exactish match first
        for p in self.db:
            if name_query == p.name.lower():
                return p
        
        # Contains match
        for p in self.db:
            if name_query in p.name.lower():
                return p
                
        return None
