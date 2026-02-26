import statistics
from typing import List, Tuple
from .models import Listing, PriceAnalysis, ValidationStatus

class PriceAnalyzer:
    """Analyzes price distribution and detects outliers using MAD (Median Absolute Deviation)."""
    
    @staticmethod
    def analyze_prices(listings: List[Listing]) -> None:
        """
        Calculates stats for a group of Listings (presumed to be Verified Matches).
        Updates listings in-place with PriceAnalysis objects.
        """
        valid_prices = [
            l.price for l in listings 
            if l.verification and l.verification.status == ValidationStatus.PASS and l.price > 0
        ]
        
        if len(valid_prices) < 3:
            # Not enough data for robust analysis
            return
            
        median = statistics.median(valid_prices)
        
        # Calculate MAD: median(|Yi - median|)
        deviations = [abs(p - median) for p in valid_prices]
        mad = statistics.median(deviations)
        
        # Avoid division by zero if all prices are identical
        if mad == 0:
            mad = 1.0 # arbitrary small buffer or skip
            
        # Standard threshold: 2.5 or 3 * MAD (akin to 2-3 Sigma)
        # Hampel filter often uses 3 * MAD_scale_factor (1.4826)
        # Let's use a simpler heuristic for scam detection:
        # Lower bound = Median - 2 * MAD. Anything below is suspicious.
        
        lower_bound = median - (2.5 * mad)
        upper_bound = median + (2.5 * mad)
        
        for l in listings:
            if not l.verification or l.verification.status != ValidationStatus.PASS:
                continue
                
            is_outlier = False
            if l.price < lower_bound:
                is_outlier = True # Too cheap!
                l.is_scam_suspected = True
                if l.verification:
                     l.verification.review_flags.append("Price outlier (too low)")
            elif l.price > upper_bound:
                is_outlier = True # Too expensive
                
            l.price_analysis = PriceAnalysis(
                median_price_market=median,
                mad_score=mad,
                is_outlier=is_outlier,
                predicted_fair_price_range=(max(0, median - mad), median + mad)
            )

class RankingEngine:
    """Ranks and selects top candidates."""
    
    @staticmethod
    def rank_listings(listings: List[Listing]) -> List[Listing]:
        """
        Returns sorted best options:
        Criteria:
        1. Status == PASS
        2. Not outlier (too cheap often scam)
        3. Price (asc)
        4. Confidence (desc)
        """
        candidates = [
            l for l in listings 
            if l.verification and l.verification.status == ValidationStatus.PASS
        ]
        
        # Sort by Price first
        # But push suspected scams to bottom? Or filter them out?
        # Let's filter strict outliers first for "Top Picks"
        
        safe_picks = [c for c in candidates if not c.is_scam_suspected]
        risky_picks = [c for c in candidates if c.is_scam_suspected]
        
        # Sort safe picks by price ascending
        safe_picks.sort(key=lambda x: x.price)
        
        return safe_picks + risky_picks
