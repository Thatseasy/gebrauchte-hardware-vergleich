from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

class ComponentType(Enum):
    CPU = "CPU"
    GPU = "GPU"
    RAM = "RAM"
    MOTHERBOARD = "MOTHERBOARD"
    PSU = "PSU"
    CASE = "CASE"
    COOLER = "COOLER"
    TUBE = "TUBE" # AIO/Watercooling parts
    FAN = "FAN"
    CABLE = "CABLE"
    PERIPHERAL = "PERIPHERAL" # Mouse, Keyboard
    STORAGE = "STORAGE"
    ACCESSORY = "ACCESSORY"
    BUNDLE = "BUNDLE"
    BUILD = "BUILD"
    UNKNOWN = "UNKNOWN"

@dataclass
class Product:
    """Represents a standardized product (from benchmarks or manual catalog)."""
    id: str
    name: str # The 'canonical' name
    type: ComponentType
    performance_score: int = 0
    # New fields for Entity Resolution
    manufacturer: Optional[str] = None
    model_family: Optional[str] = None # e.g. "RTX 3070"
    attributes: Dict[str, Any] = field(default_factory=dict) # e.g. {"vram": 8, "submodel": "Ti"}

@dataclass
class CanonicalSpec:
    """Defines the 'Search Target' with mandatory and optional specs."""
    type: ComponentType
    name: str  # Display Name: "NVIDIA RTX 3070 Ti"
    
    # Matching Rules
    must_contain_tokens: List[str] = field(default_factory=list) # e.g. ["3070", "Ti"]
    must_exclude_tokens: List[str] = field(default_factory=list) # e.g. ["3070" (if searching for Ti?), "Super"] - wait, logic needs to be robust
    
    # Specific Attributes to validate
    # e.g. {"vram": [8], "series": ["3000"]}
    expected_attributes: Dict[str, List[Any]] = field(default_factory=dict)
    
    # Search Keywords
    search_queries: List[str] = field(default_factory=list) # e.g. ["RTX 3070 Ti", "GeForce 3070 Ti"]

    # AI-Enriched Data
    data_card: Optional[Dict[str, Any]] = None


class ValidationStatus(Enum):
    PASS = "PASS" # High confidence match
    REVIEW = "REVIEW" # Potential match, but suspicious/unclear
    REJECT = "REJECT" # Definitely not a match

class BuildType(Enum):
    VIRTUAL = "VIRTUAL" # Assembled from individual listings
    COMPLETE_LISTING = "COMPLETE_LISTING" # A single listing selling a whole PC

@dataclass
class VerificationResult:
    """Output of the ListingVerification Agent."""
    status: ValidationStatus
    confidence_score: float # 0.0 to 1.0
    matched_attributes: Dict[str, Any]
    rejection_reasons: List[str] = field(default_factory=list)
    review_flags: List[str] = field(default_factory=list)

@dataclass
class PriceAnalysis:
    """Pricing context for a listing."""
    median_price_market: float = 0.0
    mad_score: float = 0.0 # Deviation from median
    is_outlier: bool = False
    predicted_fair_price_range: tuple = (0.0, 0.0)

@dataclass
class Listing:
    """Represents a specific sell offer (New or Used)."""
    title: str
    price: float
    url: str
    platform: str = "Kleinanzeigen"
    
    # Extraction & Raw Data
    description: str = ""
    location: str = ""
    date_posted: Optional[str] = None
    
    # Verification & Analysis (Filled by Agents)
    raw_attributes: Dict[str, Any] = field(default_factory=dict) # Extracted from text
    normalized_attributes: Dict[str, Any] = field(default_factory=dict)
    
    verification: Optional[VerificationResult] = None
    price_analysis: Optional[PriceAnalysis] = None
    
    is_scam_suspected: bool = False
    
    # Legacy/Compat
    condition: str = "Used"
    
    # Linked product matching
    product_match: Optional[Product] = None
    match_confidence: float = 0.0

@dataclass
class Build:
    """Represents a combination of parts or a complete PC listing."""
    components: List[Listing] = field(default_factory=list)
    build_type: BuildType = BuildType.VIRTUAL 
    
    # Financials
    total_price: float = 0.0
    
    # Analysis
    total_performance_score: int = 0
    missing_components: List[str] = field(default_factory=list) # e.g. ["PSU", "Case"]
    compatibility_warnings: List[str] = field(default_factory=list)
    
    # For Complete Listings
    source_listing: Optional[Listing] = None # The main listing if Type == COMPLETE_LISTING

    def calculate_totals(self):
        if self.build_type == BuildType.VIRTUAL:
            self.total_price = sum(c.price for c in self.components)
        elif self.build_type == BuildType.COMPLETE_LISTING and self.source_listing:
            self.total_price = self.source_listing.price
            
        # Simplified performance aggregation
        self.total_performance_score = sum(
            getattr(c.product_match, 'performance_score', 0) 
            for c in self.components 
            if c.product_match
        )
