import re
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
        Enforces socket matching for CPUs to prevent cross-socket suggestions.
        """
        # 1. Resolve Spec to Reference Hardware (e.g. "RTX 3070" -> Score: 22000)
        reference_items = self.db.get_reference_hardware(spec.name.replace("GPU: ", "").replace("CPU: ", "").replace("NVIDIA ", "").strip())
        
        if not reference_items:
            return []
            
        base_product = reference_items[0]
        base_score = base_product.get('score')
        base_socket = base_product.get('socket') or CompatibilityEngine.identify_socket(base_product['name'])
        
        if not base_score:
            return []
            
        # 2. Query DB for similar scores
        similar_dicts = self.db.get_similar_hardware(base_score, base_product['type'], threshold)
        
        alternatives = []
        for d in similar_dicts:
            if d['name'] == base_product['name']:
                continue
            
            item_socket = d.get('socket') or CompatibilityEngine.identify_socket(d['name'])
            # Enforce socket compatibility for CPUs
            if base_product['type'] == 'CPU':
                if base_socket and item_socket and item_socket != base_socket:
                    continue
                
            alternatives.append(Product(
                id=d['id'],
                name=d['name'],
                type=ComponentType(d['type']),
                performance_score=d['score'],
                attributes={"socket": d.get('socket') or item_socket, "memory": d.get('memory_type')}
            ))
            
        return alternatives

class CompatibilityEngine:
    """Checks compatibility between components (CPU <-> MB <-> RAM <-> PSU)."""
    
    # Knowledge Base (Comprehensive for Modern Gaming)
    SOCKET_MAP = {
        "AM4": [
            "B450", "B550", "X570", "A320", "X470", "B350", "X370", "A520",
            "Ryzen 5000", "Ryzen 3000", "Ryzen 2000", "Ryzen 1000",
            "5800", "5600", "5700", "3700", "3600", "2600", "1600", "5500"
        ],
        "AM5": [
            "B650", "X670", "A620", "X870", "B850",
            "Ryzen 7000", "Ryzen 8000", "Ryzen 9000",
            "7500", "7600", "7700", "7800", "7900", "7950", "9600", "9700", "9800", "9900", "9950"
        ],
        "LGA1700": [
            "Z690", "Z790", "B660", "B760", "H610", "H670", "H770",
            "Core i-12", "Core i-13", "Core i-14",
            "12400", "12600", "12700", "12900", "13400", "13600", "13700", "13900", "14400", "14600", "14700", "14900"
        ],
        "LGA1200": [
            "Z490", "Z590", "B560", "B460", "H410", "H510",
            "Core i-10", "Core i-11",
            "10400", "10600", "10700", "10900", "11400", "11600", "11700", "11900"
        ],
        "LGA1151": [
            "Z390", "Z370", "B365", "B360", "H370", "H310",
            "Core i-8", "Core i-9",
            "8400", "8600", "8700", "9100", "9400", "9600", "9700", "9900"
        ]
    }
    
    MEMORY_MAP = {
        "DDR4": ["AM4", "LGA1200", "LGA1700", "LGA1151", "B550", "Z690", "B450", "B350", "A320", "X570", "Z390", "B360", "Z370"],
        "DDR5": ["AM5", "LGA1700", "B650", "Z790", "X670", "B760", "X870"]
    }

    @staticmethod
    def identify_socket(text: str) -> Optional[str]:
        if not text:
            return None
        text_upper = text.upper()
        
        # 1. Direct explicit socket mentions
        if "AM5" in text_upper: return "AM5"
        if "AM4" in text_upper: return "AM4"
        if "LGA1700" in text_upper or "LGA 1700" in text_upper: return "LGA1700"
        if "LGA1200" in text_upper or "LGA 1200" in text_upper: return "LGA1200"
        if "LGA1151" in text_upper or "LGA 1151" in text_upper: return "LGA1151"
        
        # 2. Check platform context
        is_intel = bool(re.search(r'\b(INTEL|CORE|I3|I5|I7|I9|LGA)\b', text_upper))
        is_amd = bool(re.search(r'\b(AMD|RYZEN|R3|R5|R7|R9)\b', text_upper))
        
        # 3. Specific Motherboard Chipset Regex
        if re.search(r'\b(B650|X670|X870|B850|A620)\w*\b', text_upper):
            return "AM5"
        if re.search(r'\b(B450|B550|X570|A520|X470|B350|A320|X370)\w*\b', text_upper):
            return "AM4"
        if re.search(r'\b(Z690|Z790|B660|B760|H610|H670|H770)\w*\b', text_upper):
            return "LGA1700"
        if re.search(r'\b(Z490|Z590|B560|B460|H410|H510)\w*\b', text_upper):
            return "LGA1200"
        if re.search(r'\b(Z390|Z370|B365|B360|H370|H310)\w*\b', text_upper):
            return "LGA1151"
            
        # 4. Intel CPU Generation Matching (Strict word boundaries to prevent AM4 collisions!)
        # 12th, 13th, 14th Gen Intel -> LGA1700
        if re.search(r'\b(12[1-9]00|13[1-9]00|14[1-9]00)\w*\b', text_upper) or re.search(r'\bCORE\s+I[3579]-1[234]\b', text_upper):
            return "LGA1700"
        # 10th, 11th Gen Intel -> LGA1200
        if re.search(r'\b(10[1-9]00|11[1-9]00)\w*\b', text_upper) or re.search(r'\bCORE\s+I[3579]-1[01]\b', text_upper):
            return "LGA1200"
        # 8th, 9th Gen Intel -> LGA1151
        if is_intel and (re.search(r'\b(8[1-9]00|9[1-9]00)\w*\b', text_upper) or re.search(r'\bCORE\s+I[3579]-[89]\b', text_upper)):
            return "LGA1151"
            
        # 5. AMD Ryzen CPU Model Matching (Word boundaries)
        # AM5: Ryzen 7000, 8000, 9000
        if re.search(r'\b(7[5-9]00|8[5-9]00|9[6-9]00)\w*\b', text_upper):
            if not is_intel:
                return "AM5"
        if re.search(r'\bRYZEN\s+[3579]?\s*(7000|8000|9000)\b', text_upper):
            return "AM5"
            
        # AM4: Ryzen 1000, 2000, 3000, 5000
        if not is_intel:
            if re.search(r'\b(1[6-8]00|2[6-8]00|3[6-9]00|5[5-9]00)\w*\b', text_upper):
                return "AM4"
            if re.search(r'\bRYZEN\s+[3579]?\s*(1000|2000|3000|5000)\b', text_upper):
                return "AM4"
            
        return None

    @staticmethod
    def check_compatibility(specs: List[CanonicalSpec]) -> Tuple[bool, List[str]]:
        """
        Returns (True/False, List of Warnings).
        """
        warnings = []
        
        cpu_spec = next((s for s in specs if s.type == ComponentType.CPU), None)
        mb_spec = next((s for s in specs if s.type == ComponentType.MOTHERBOARD), None)
        ram_spec = next((s for s in specs if s.type == ComponentType.RAM), None)
        psu_spec = next((s for s in specs if s.type == ComponentType.PSU), None)
        
        cpu_socket = CompatibilityEngine.identify_socket(cpu_spec.name) if cpu_spec else None
        mb_socket = CompatibilityEngine.identify_socket(mb_spec.name) if mb_spec else None
        
        if cpu_spec and mb_spec:
            if cpu_socket and mb_socket and cpu_socket != mb_socket:
                warnings.append(f"Incompatible Sockets: CPU is {cpu_socket}, MB is {mb_socket}.")
            elif cpu_socket and not mb_socket:
                warnings.append(f"Could not identify socket for Motherboard: {mb_spec.name}")
            elif mb_socket and not cpu_socket:
                warnings.append(f"Could not identify socket for CPU: {cpu_spec.name}")

        # RAM compatibility check
        if ram_spec:
            active_socket = mb_socket or cpu_socket
            ram_upper = ram_spec.name.upper()
            if active_socket == "AM5" and "DDR4" in ram_upper:
                warnings.append("Incompatible RAM: AM5 platform requires DDR5, but DDR4 was selected.")
            elif active_socket == "AM4" and "DDR5" in ram_upper:
                warnings.append("Incompatible RAM: AM4 platform requires DDR4, but DDR5 was selected.")
            elif active_socket == "LGA1200" and "DDR5" in ram_upper:
                warnings.append("Incompatible RAM: LGA1200 platform only supports DDR4, but DDR5 was selected.")

        # Power Supply (PSU) Wattage Check
        if psu_spec:
            psu_watt_match = re.search(r'(\d{3,4})\s*W', psu_spec.name, re.I)
            if psu_watt_match:
                psu_wattage = int(psu_watt_match.group(1))
                required_wattage = GapAnalyzer.estimate_psu_wattage(specs)
                if psu_wattage < required_wattage:
                    warnings.append(
                        f"Insufficient Power Supply: {psu_spec.name} ({psu_wattage}W) is below estimated required wattage ({required_wattage}W)."
                    )
        
        return (len(warnings) == 0, warnings)

class CombinationEngine:
    """Combines individual component listings into a complete Build."""

    @staticmethod
    def create_best_build(specs: List[CanonicalSpec], listings_map: Dict[str, List[Listing]]) -> Optional[Build]:
        """
        Picks the cheapest 'PASS' verified item for each spec with scam filtering.
        """
        from .models import BuildType, ValidationStatus

        selected_components = []
        
        for spec in specs:
            raw_candidates = listings_map.get(spec.name, [])
            # Exclude any listing suspected of scam or with SCAM_SUSPECT status
            listings = [
                l for l in raw_candidates
                if not getattr(l, 'is_scam_suspected', False)
                and (not l.verification or l.verification.status != ValidationStatus.SCAM_SUSPECT)
            ]
            # Priority 1: Verified PASS with price > 5.0
            valid = [
                l for l in listings
                if l.price is not None and l.price > 5.0
                and l.verification and l.verification.status == ValidationStatus.PASS
            ]
            # Priority 2: Verified REVIEW with price > 5.0
            if not valid:
                valid = [
                    l for l in listings
                    if l.price is not None and l.price > 5.0
                    and l.verification and l.verification.status == ValidationStatus.REVIEW
                ]
            # Priority 3: Fallback to any verified PASS listing (including pure VB or None price)
            if not valid:
                valid = [
                    l for l in listings
                    if l.verification and l.verification.status == ValidationStatus.PASS
                ]
            # Priority 4: Fallback to any verified REVIEW listing
            if not valid:
                valid = [
                    l for l in listings
                    if l.verification and l.verification.status == ValidationStatus.REVIEW
                ]
            
            if valid:
                valid.sort(key=lambda x: (x.price is None or x.price <= 0.0, x.price if (x.price is not None and x.price > 0.0) else float('inf')))
                
                # Scam/Outlier Detection on priced candidates
                priced_candidates = [l for l in valid if l.price is not None and l.price > 5.0]
                if len(priced_candidates) >= 3:
                    prices = [l.price for l in priced_candidates]
                    mid = len(prices) // 2
                    median_price = (prices[mid] + prices[~mid]) / 2.0
                    
                    best_match = None
                    for candidate in priced_candidates:
                        if candidate.price >= (median_price * 0.40):
                            best_match = candidate
                            break
                    if not best_match:
                        best_match = priced_candidates[0]
                else:
                    best_match = valid[0]
                    
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
                
        return missing

    @staticmethod
    def estimate_psu_wattage(specs: List[CanonicalSpec]) -> int:
        """
        Estimation of required PSU wattage.
        Uses deterministic HardwareCatalog TDP when available with formula:
        (CPU_TDP + GPU_TDP + 80W) * 1.15
        Falls back to keyword heuristics if not present in catalog.
        """
        cpu_tdp = None
        gpu_tdp = None

        # 1. Deterministic catalog lookup
        try:
            from .catalog import HardwareCatalog
            catalog = HardwareCatalog()
            for s in specs:
                item = catalog.find_item(s.name)
                if item:
                    if item.type == "CPU" and cpu_tdp is None:
                        cpu_tdp = item.tdp_w
                    elif item.type == "GPU" and gpu_tdp is None:
                        gpu_tdp = item.tdp_w
        except Exception:
            pass

        # 2. Heuristic fallback for CPU/GPU TDP if not resolved
        if cpu_tdp is None:
            for s in specs:
                if s.type == ComponentType.CPU:
                    name = s.name.upper()
                    if "9" in name or "THREADRIPPER" in name: cpu_tdp = 170
                    elif "7" in name or "K" in name: cpu_tdp = 105
                    else: cpu_tdp = 65
                    break

        if gpu_tdp is None:
            for s in specs:
                if s.type == ComponentType.GPU:
                    name = s.name.upper()
                    if "4090" in name: gpu_tdp = 450
                    elif "4080" in name or "7900 XTX" in name: gpu_tdp = 320
                    elif "3080" in name or "6800 XT" in name: gpu_tdp = 300
                    elif "3070" in name or "6700" in name or "4070" in name: gpu_tdp = 220
                    elif "6600" in name or "3060" in name or "4060" in name: gpu_tdp = 135
                    else: gpu_tdp = 180
                    break

        actual_cpu = cpu_tdp if cpu_tdp is not None else 65
        actual_gpu = gpu_tdp if gpu_tdp is not None else 0

        # System base: Motherboard, RAM, NVMe SSD, Fans ~ 80W
        # 1.15 headroom factor for transient spikes
        return int((actual_cpu + actual_gpu + 80) * 1.15)

