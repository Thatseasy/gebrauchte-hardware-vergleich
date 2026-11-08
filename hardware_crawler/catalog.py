"""
Hardware Catalog: Deterministic Knowledge Base for PC Gaming Components.
Contains pre-compiled data for CPUs, GPUs, Motherboards, RAM, and PSUs:
- Gaming Performance Indices (TechPowerUp 1080p/1440p Rasterization Index & CPU Gaming Index)
- Sockets, Supported RAM Types, TDP, and Recommended PSU Wattage
- Typical Used Market Fair Price Ranges
"""
import os
import re
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "data", "hardware_catalog.json")

# Brand Token Regular Expressions (with word boundaries / lookarounds)
INTEL_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(INTEL|CORE\s*I[3579]|I[3579]|LGA\s*1700|LGA\s*1200|LGA\s*1151|ARC)(?![A-Za-z0-9])",
    re.IGNORECASE
)
AMD_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(AMD|RYZEN|R[3579]|RADEON|THREADRIPPER|AM4|AM5)(?![A-Za-z0-9])",
    re.IGNORECASE
)
COMPARISON_PATTERN = re.compile(
    r"\b(VS|VERGLEICH|STATT|ODER|COMPARED|BETTER\s+THAN|BESSER\s+ALS)\b",
    re.IGNORECASE
)

@dataclass
class CatalogItem:
    id: str
    canonical_name: str
    type: str  # "GPU", "CPU", "MOTHERBOARD", "RAM", "PSU"
    brand: str
    aliases: List[str] = field(default_factory=list)
    gaming_score: int = 50  # 0 to 100 relative gaming index
    tier: str = "1080p_budget"
    tdp_w: int = 65
    rec_psu_w: int = 500
    socket: Optional[str] = None
    memory_types: List[str] = field(default_factory=list)
    vram_gb: Optional[int] = None
    used_price_min: float = 0.0
    used_price_max: float = 0.0

    @property
    def used_price_fair(self) -> float:
        if self.used_price_min and self.used_price_max:
            return round((self.used_price_min + self.used_price_max) / 2.0, 2)
        return self.used_price_max or self.used_price_min or 0.0

    @property
    def category(self) -> str:
        return self.type

def _alias_specificity_key(entry: Tuple[str, str]) -> Tuple[int, int, int]:
    alias, _ = entry
    l = len(alias)
    separators = alias.count(" ") + alias.count("-")
    has_modifier = 1 if any(mod in alias for mod in ["SUPER", "TI", "XTX", "XT", "GRE", "X3D", "KF", "OC", "GB"]) else 0
    return (l, has_modifier, separators)

class HardwareCatalog:
    """Singleton catalog manager providing 0ms deterministic hardware queries."""
    
    _instance = None
    
    def __new__(cls, catalog_file: str = CATALOG_PATH):
        if cls._instance is None:
            cls._instance = super(HardwareCatalog, cls).__new__(cls)
            cls._instance._load(catalog_file)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing or reloading)."""
        cls._instance = None

    @classmethod
    def reload(cls, catalog_file: str = CATALOG_PATH) -> "HardwareCatalog":
        """Forces a clean reload of the catalog singleton."""
        cls.reset_instance()
        return cls(catalog_file)

    def _load(self, catalog_file: str):
        self.items: Dict[str, CatalogItem] = {}
        self.alias_map: Dict[str, str] = {}
        self.alias_map_by_type: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.sorted_aliases: List[Tuple[str, str]] = []
        self.sorted_aliases_by_type: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        
        if not os.path.exists(catalog_file):
            logger.warning(f"Hardware catalog file not found at {catalog_file}. Creating default.")
            os.makedirs(os.path.dirname(catalog_file), exist_ok=True)
            self._save_defaults(catalog_file)

        try:
            with open(catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("components", []):
                    item = CatalogItem(**entry)
                    self.items[item.id] = item
                    ctype = item.type.upper().strip()

                    def register_alias(alias_str: str):
                        clean_a = alias_str.strip().upper()
                        if not clean_a:
                            return
                        # Guard: Reject bare numeric aliases of 4 or fewer digits
                        if clean_a.isdigit() and len(clean_a) <= 4:
                            logger.debug(f"Ignoring bare numeric alias '{clean_a}' for {item.id}")
                            return

                        self.alias_map[clean_a] = item.id
                        self.alias_map_by_type[ctype][clean_a] = item.id

                        # Also register variant without spaces
                        no_space = clean_a.replace(" ", "")
                        if not (no_space.isdigit() and len(no_space) <= 4):
                            self.alias_map[no_space] = item.id
                            self.alias_map_by_type[ctype][no_space] = item.id

                        # Also register hyphen-to-space variant
                        no_hyphen = clean_a.replace("-", " ")
                        if not (no_hyphen.isdigit() and len(no_hyphen) <= 4):
                            self.alias_map[no_hyphen] = item.id
                            self.alias_map_by_type[ctype][no_hyphen] = item.id
                    
                    # Register canonical name
                    register_alias(item.canonical_name)
                    
                    # Register aliases
                    for a in item.aliases:
                        register_alias(a)
                        
            # Pre-sort aliases by specificity & length descending
            self.sorted_aliases = sorted(
                self.alias_map.items(),
                key=_alias_specificity_key,
                reverse=True
            )
            for ctype, amap in self.alias_map_by_type.items():
                self.sorted_aliases_by_type[ctype] = sorted(
                    amap.items(),
                    key=_alias_specificity_key,
                    reverse=True
                )

            logger.info(f"Loaded {len(self.items)} components into HardwareCatalog.")
        except Exception as e:
            logger.error(f"Failed to load hardware catalog: {e}")

    def find_item(self, text: str, component_type: Optional[Any] = None) -> Optional[CatalogItem]:
        """Finds a catalog item using alias matching or substring search with lookaround boundaries."""
        if not text:
            return None
            
        clean = text.upper().strip()
        clean_no_space = clean.replace(" ", "").replace("-", "")

        target_type = None
        if component_type is not None:
            if hasattr(component_type, "value"):
                target_type = str(component_type.value).upper().strip()
            else:
                target_type = str(component_type).upper().strip()

        # Brand conflict detection
        is_comparison = bool(COMPARISON_PATTERN.search(clean))
        has_intel = bool(INTEL_TOKEN_PATTERN.search(clean))
        has_amd = bool(AMD_TOKEN_PATTERN.search(clean))
        allow_all_brands = is_comparison or (has_intel and has_amd)

        def brand_allowed(candidate: CatalogItem) -> bool:
            if allow_all_brands:
                return True
            cand_brand = candidate.brand.upper()
            if has_intel and not has_amd and cand_brand == "AMD":
                return False
            if has_amd and not has_intel and cand_brand == "INTEL":
                return False
            return True

        # Candidate partition selection
        if target_type and target_type in self.alias_map_by_type:
            exact_map = self.alias_map_by_type[target_type]
            alias_list = self.sorted_aliases_by_type[target_type]
        else:
            exact_map = self.alias_map
            alias_list = self.sorted_aliases

        # 1. Exact match (0ms dict lookup)
        if clean in exact_map:
            cand = self.items[exact_map[clean]]
            if brand_allowed(cand):
                return cand
        if clean_no_space in exact_map:
            cand = self.items[exact_map[clean_no_space]]
            if brand_allowed(cand):
                return cand

        # 2. Token match with lookarounds (sorted by length/specificity descending)
        for alias, item_id in alias_list:
            if len(alias) < 3:
                continue
            cand = self.items[item_id]
            if not brand_allowed(cand):
                continue

            pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
            if re.search(pattern, clean):
                return cand
                
        return None

    def get_alternatives(self, item_or_name: Any, threshold_pct: float = 0.15, max_results: Optional[int] = None) -> List[CatalogItem]:
        """
        Finds drop-in hardware alternatives with similar gaming performance.
        - GPUs: +/- threshold_pct rasterization gaming score.
        - CPUs: +/- threshold_pct score AND strictly matching socket!
        """
        if isinstance(item_or_name, str):
            item = self.find_item(item_or_name)
            if not item:
                return []
        else:
            item = item_or_name
            
        score = item.gaming_score
        min_score = score * (1.0 - threshold_pct)
        max_score = score * (1.0 + threshold_pct)
        
        results = []
        for other in self.items.values():
            if other.id == item.id or other.type != item.type:
                continue
                
            # CPUs must share the exact same socket for drop-in upgrade!
            if item.type == "CPU" and other.socket != item.socket:
                continue
                
            if min_score <= other.gaming_score <= max_score:
                results.append(other)
                
        # Sort by gaming score descending
        results.sort(key=lambda x: x.gaming_score, reverse=True)
        if max_results is not None:
            return results[:max_results]
        return results

    def _save_defaults(self, catalog_file: str):
        """Initial catalog dataset creation."""
        pass
