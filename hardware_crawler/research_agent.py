from typing import Optional
from .models import Product, ComponentType

class ResearchAgent:
    """
    Agent responsible for identifying products that are not in the benchmark database.
    Can be extended to perform real web search to classify products.
    """
    
    def research(self, query: str) -> Optional[Product]:
        """
        Attempts to identify a product from a search query.
        For now, this assumes any query not found in the DB is a valid 'Other' product
        that the user wants to search for on marketplaces.
        """
        # Simple fallback logic: Create a generic product
        # In a real 'Web Research' scenario, this would:
        # 1. Search Google/Bing for the query.
        # 2. Extract category (Fan, Case, Cable, etc.).
        # 3. Return a more structured product.
        
        return Product(
            id=f"research_{query.replace(' ', '_').lower()}",
            name=query,     # Use the user's query as the name
            type=ComponentType.OTHER,
            performance_score=None # No benchmark data
        )
