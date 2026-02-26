from typing import List, Dict, Optional, Tuple
from .models import CanonicalSpec, ComponentType, Product, Listing, Build
from .database import DatabaseManager

class SimilarityEngine:
    """Finds alternative products with similar performance."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def find_alternatives(self, spec: CanonicalSpec, threshold: float = 0.15) -> List[Product]:
        """
        Finds products that are within +/- threshold% performance.
        Requires the 'original' spec to resolve to a known product first.
        """
        # 1. Resolve Spec to Reference Hardware (e.g. "RTX 3070" -> Score: 22000)
        reference_items = self.db.get_reference_hardware(spec.name.replace("GPU: ", "").replace("CPU: ", "").replace("NVIDIA ", "").strip())
        
        if not reference_items:
            # Fallback: Try token matching if direct name fails
            # This is a bit weak in MVP without a robust fuzzy matcher
            return []
            
        base_product = reference_items[0] # Pick best match
        base_score = base_product['score']
        
        if not base_score:
            return []
            
        # 2. Query DB for similar scores
        similar_dicts = self.db.get_similar_hardware(base_score, base_product['type'], threshold)
        
        alternatives = []
        for d in similar_dicts:
            if d['name'] == base_product['name']:
                continue # Skip self
                
            alternatives.append(Product(
                id=d['id'],
                name=d['name'],
                type=ComponentType(d['type']),
                performance_score=d['score'],
                attributes={"socket": d['socket'], "memory": d['memory_type']}
            ))
            
        return alternatives

class CompatibilityEngine:
    """Checks compatibility between components (CPU <-> MB <-> RAM)."""
    
    # Knowledge Base (Simplified for MVP)
    SOCKET_MAP = {
        "AM4": ["B450", "B550", "X570", "A320", "X470", "Ryzen 5000", "Ryzen 3000", "Ryzen 2000"],
        "AM5": ["B650", "X670", "Ryzen 7000", "Ryzen 8000"],
        "LGA1700": ["Z690", "Z790", "B660", "B760", "Core i-12", "Core i-13", "Core i-14"],
        "LGA1200": ["Z490", "Z590", "B560", "B460", "Core i-10", "Core i-11"]
    }
    
    MEMORY_MAP = {
        "DDR4": ["AM4", "LGA1200", "LGA1700", "B550", "Z690", "B450"], # Z690 supports both, simplifying here
        "DDR5": ["AM5", "LGA1700", "B650", "Z790", "X670"]
    }

    @staticmethod
    def identify_socket(text: str) -> Optional[str]:
        text = text.upper()
        # Direct Socket Match
        if "AM4" in text: return "AM4"
        if "AM5" in text: return "AM5"
        if "LGA1700" in text: return "LGA1700"
        if "LGA1200" in text: return "LGA1200"
        
        # Infer from Series/Model
        if "RYZEN 5" in text or "RYZEN 7" in text or "RYZEN 9" in text:
             if "5800" in text or "5600" in text or "3700" in text or "3600" in text: return "AM4"
             if "7600" in text or "7800" in text or "7900" in text or "7950" in text: return "AM5"
        
        if "B550" in text or "X570" in text: return "AM4"
        if "B650" in text or "X670" in text: return "AM5"
        if "Z690" in text or "Z790" in text: return "LGA1700"
        
        return None

    @staticmethod
    def check_compatibility(specs: List[CanonicalSpec]) -> Tuple[bool, List[str]]:
        """
        Returns (True/False, List of Warnings).
        """
        warnings = []
        sockets_found = set()
        
        cpu_spec = next((s for s in specs if s.type == ComponentType.CPU), None)
        mb_spec = next((s for s in specs if s.type == ComponentType.MOTHERBOARD), None)
        
        if cpu_spec and mb_spec:
             cpu_socket = CompatibilityEngine.identify_socket(cpu_spec.name)
             mb_socket = CompatibilityEngine.identify_socket(mb_spec.name)
             
             if cpu_socket and mb_socket and cpu_socket != mb_socket:
                 # Special case: LGA1700 allows 12/13/14 gen. 
                 # But if we strictly mapped them to "LGA1700" key, they should match.
                 warnings.append(f"Incompatible Sockets: CPU is {cpu_socket}, MB is {mb_socket}.")
             elif cpu_socket and not mb_socket:
                 warnings.append(f"Could not identify socket for Motherboard: {mb_spec.name}")
        
        return (len(warnings) == 0, warnings)

class CombinationEngine:
    """Combines individual component listings into a complete Build."""

    @staticmethod
    def create_best_build(specs: List[CanonicalSpec], listings_map: Dict[str, List[Listing]]) -> Optional[Build]:
        """
        Naive implementation: Picks the cheapest 'PASS' verified item for each spec.
        """
        from .models import BuildType, ValidationStatus # Import locally to avoid circular dep if any

        selected_components = []
        
        for spec in specs:
            listings = listings_map.get(spec.name, [])
            # Filter for PASS
            valid = [l for l in listings if l.verification and l.verification.status == ValidationStatus.PASS]
            if not valid:
                 # Fallback to REVIEW?
                 valid = [l for l in listings if l.verification and l.verification.status == ValidationStatus.REVIEW]
            
            if valid:
                # Sort by price ascending
                valid.sort(key=lambda x: x.price)
                
                # --- Scam/Outlier Detection ---
                # Find the median price of all valid listings
                if len(valid) >= 3:
                    prices = [l.price for l in valid]
                    mid = len(prices) // 2
                    median_price = (prices[mid] + prices[~mid]) / 2.0
                    
                    # Reject listings that are more than 60% cheaper than the median (< 40%)
                    best_match = None
                    for candidate in valid:
                        if candidate.price >= (median_price * 0.40):
                            best_match = candidate
                            break
                    if not best_match:
                        best_match = valid[0] # Fallback
                else:
                    best_match = valid[0]
                    
                # Link product match
                # Use ComponentType from spec
                best_match.product_match = Product(id=spec.name, name=spec.name, type=spec.type) 
                selected_components.append(best_match)
        
        if not selected_components:
            return None
            
        build = Build(
            components=selected_components,
            build_type=BuildType.VIRTUAL
        )
        build.calculate_totals()
        
        # Check compatibility
        is_compat, warnings = CompatibilityEngine.check_compatibility(specs)
        build.compatibility_warnings = warnings
        
        # Check gaps
        build.missing_components = GapAnalyzer.analyze_completeness(specs)
        
        return build

class GapAnalyzer:
    """Analyzes a list of components to find what is missing for a complete build."""
    
    REQUIRED_TYPES = [
        ComponentType.CPU,
        ComponentType.GPU,
        ComponentType.MOTHERBOARD,
        ComponentType.RAM,
        ComponentType.PSU,
        ComponentType.CASE
    ]
    
    @staticmethod
    def analyze_completeness(present_specs: List[CanonicalSpec]) -> List[str]:
        """
        Returns a list of missing component types (as strings).
        """
        present_types = {s.type for s in present_specs}
        missing = []
        
        for req in GapAnalyzer.REQUIRED_TYPES:
            if req not in present_types:
                missing.append(req.value)
                
        # Basic heuristic for CPU Cooler
        # If CPU is high-end (e.g. "K" series or Ryzen X), assume cooler needed if not present
        # For simplicity in MVP, just check if ANY cooler implies present.
        # We don't have a COOLER type in ComponentType yet? Let's check. 
        # If not, we might skipped it. Let's stick to the main types first.
        
        return missing

    @staticmethod
    def estimate_psu_wattage(specs: List[CanonicalSpec]) -> int:
        """
        Very rough estimation of required PSU wattage.
        """
        base_wattage = 150 # System overhead (Fans, Drives, etc.)
        
        # Heuristics
        for s in specs:
            name = s.name.upper()
            if s.type == ComponentType.GPU:
                if "4090" in name: base_wattage += 450
                elif "4080" in name or "7900 XTX" in name: base_wattage += 320
                elif "3080" in name or "6800 XT" in name: base_wattage += 320
                elif "3070" in name or "6700" in name: base_wattage += 220
                else: base_wattage += 180 # Generic mid-range
                
            if s.type == ComponentType.CPU:
                if "9" in name or "THREADRIPPER" in name: base_wattage += 180
                elif "7" in name: base_wattage += 120
                else: base_wattage += 65
                
        # Buffer
        return int(base_wattage * 1.2)
