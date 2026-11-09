"""
deal_checker.py: 0ms Deterministic Deal-Checker & Multi-Line Listing Parser.
Evaluates pasted Kleinanzeigen ad descriptions against the 241-component HardwareCatalog
and market pricing. Provides arbitrage savings, assessment tier, and German negotiation templates.
"""
import re
import html
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from .models import ComponentType
from .catalog import HardwareCatalog, CatalogItem
from .logging_session import SessionLogger

logger = logging.getLogger(__name__)

class PriceAssessment(Enum):
    TOP_DEAL = "TOP_DEAL"        # Savings >= 150€ or >= 20%
    FAIR_DEAL = "FAIR_DEAL"      # -50€ <= Savings < 150€
    OVERPRICED = "OVERPRICED"    # Savings < -50€ (asking price is too high)
    UNKNOWN = "UNKNOWN"

@dataclass
class EvaluatedComponent:
    category: str  # "GPU", "CPU", "MOTHERBOARD", "RAM", "PSU", "STORAGE", "CASE", "COOLER"
    raw_name: str
    canonical_name: str
    catalog_id: Optional[str]
    market_value_min: float
    market_value_max: float
    market_value_fair: float
    is_catalog_match: bool
    confidence: float
    specs_summary: str = ""

@dataclass
class NegotiationStrategy:
    target_offer_price: float
    suggested_discount_pct: float
    rationale: str
    chat_message_german: str

@dataclass
class DealCheckResult:
    seller_asking_price: float
    is_vb: bool
    total_market_value: float
    arbitrage_savings: float       # total_market_value - seller_asking_price
    savings_percent: float         # (arbitrage_savings / total_market_value) * 100
    assessment: PriceAssessment
    assessment_headline: str
    assessment_description: str
    components: List[EvaluatedComponent]
    unrecognized_lines: List[str]
    missing_essential_parts: List[str]
    ready_to_play_additional_cost: float
    ready_to_play_total_cost: float
    negotiation: Optional[NegotiationStrategy] = None
    raw_ad_text: str = ""

# Regex patterns for ad boilerplate & pricing indicators
AD_BOILERPLATE_PATTERN = re.compile(
    r"\b(verkaufe|abzugeben|tierfreier\s*nichtraucherhaushalt|nur\s*abholung|funktioniert\s*einwandfrei|"
    r"zustand\s*wie\s*neu|ovp\s*vorhanden|kein\s*versand|festpreis|abholung\s*in|barzahlung)\b",
    re.IGNORECASE
)

AD_DISCLAIMER_PATTERN = re.compile(
    r"(?i)\b(3dmark|furmark|timespy|time\s*spy|cinebench|benchmark|auslastung|temperatur|last\s*:|funktionstest|"
    r"impressum|agb|widerruf|datenschutz|rechtliche\s*angaben|muster-widerrufsformular|kundeninformationen)\b"
)

PRICE_PATTERN = re.compile(
    r"(?i)(?:preis\s*:?\s*|für\s+|abzugeben\s+für\s+|kostet\s+)?(\d{2,4})\s*(?:€|euro)\s*(vb|vhb|festpreis)?",
    re.IGNORECASE
)

# Component category regex patterns for zero-shot detection
REGEX_GPU = re.compile(r"(?i)\b(RTX|GTX|RX|RADEON|GEFORCE)\s*(\d{3,4}(?:\s*(?:TI|SUPER|XT|XTX|GRE))?)\b")
REGEX_CPU = re.compile(r"(?i)\b(RYZEN\s*[3579]?\s*\d{4}[A-Z3D]*|CORE\s*I[3579]-\d{4,5}[A-Z]*|I[3579]\s*\d{4,5}[A-Z]*)\b")
REGEX_MB = re.compile(r"(?i)\b(B450|B550|X570|B650|X670|B760|Z690|Z790|A520|A620|B360|Z390|B460|B560|Z490|Z590|H610)\b")
REGEX_RAM = re.compile(r"(?i)\b(\d{1,3})\s*GB\s*(?:(?:DDR[345])|(?:RAM)|(?:KIT))\b|\b(DDR[345])\b")
REGEX_STORAGE = re.compile(r"(?i)\b(\d{1,2})\s*(?:TB|GB)\s*(?:NVME|SSD|M\.2|HDD)\b|\b(?:NVME|SSD|M\.2)\b")
REGEX_PSU = re.compile(r"(?i)\b(\d{3,4})\s*W\b|\b(?:NETZTEIL|POWER\s*SUPPLY|SEASONIC|BE\s*QUIET|CORSAIR\s*RM)\b")
REGEX_CASE = re.compile(r"(?i)\b(PURE\s*BASE|SHADOW\s*BASE|FRACTAL|NZXT|CORSAIR\s*4000D|GEHÄUSE|CASE)\b")
REGEX_COOLER = re.compile(r"(?i)\b(DARK\s*ROCK|PEERLESS\s*ASSASSIN|AIO|WAKÜ|KÜHLER|NOCTUA|ARCTIC|WASSERKÜHLUNG)\b")

def detect_deal_check_intent(user_input: str) -> Tuple[bool, Optional[float], bool, float, str]:
    """
    0ms Heuristic Classifier:
    Detects whether user input is an ad text paste for valuation (DEAL_CHECK_PASTE)
    or a standard hardware component search query.

    Returns:
        (is_deal_check, detected_price, is_vb, confidence, mode_string)
    """
    if not user_input or not user_input.strip():
        return False, None, False, 0.0, "UNKNOWN"

    text = user_input.strip()
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    line_count = len(raw_lines)

    # Check for embedded price
    detected_price = None
    is_vb = False
    price_match = PRICE_PATTERN.search(text)
    if price_match:
        try:
            detected_price = float(price_match.group(1))
            modifier = (price_match.group(2) or "").lower()
            is_vb = bool(modifier in ["vb", "vhb"])
            # Fallback check for VB word in text
            if not is_vb and re.search(r"\b(vb|vhb|verhandlungsbasis)\b", text, re.IGNORECASE):
                is_vb = True
        except Exception:
            pass

    # Count bullet markers
    bullet_lines = sum(1 for l in raw_lines if re.match(r"^[\s\-\*\•\d\.\(\)\[\]\:\>]+", l))
    has_boilerplate = bool(AD_BOILERPLATE_PATTERN.search(text))

    # Fast hardware category scan
    matched_categories = 0
    if REGEX_GPU.search(text): matched_categories += 1
    if REGEX_CPU.search(text): matched_categories += 1
    if REGEX_MB.search(text): matched_categories += 1
    if REGEX_RAM.search(text): matched_categories += 1
    if REGEX_PSU.search(text): matched_categories += 1
    if REGEX_STORAGE.search(text): matched_categories += 1
    if REGEX_CASE.search(text): matched_categories += 1
    if REGEX_COOLER.search(text): matched_categories += 1

    # Heuristic criteria
    if line_count >= 3 and matched_categories >= 2:
        conf = 0.98 if (bullet_lines >= 2 or has_boilerplate or detected_price) else 0.90
        return True, detected_price, is_vb, conf, "DEAL_CHECK_PASTE"

    if (bullet_lines >= 3 and matched_categories >= 1) or (has_boilerplate and matched_categories >= 2):
        return True, detected_price, is_vb, 0.95, "DEAL_CHECK_PASTE"

    if detected_price and matched_categories >= 3:
        return True, detected_price, is_vb, 0.92, "DEAL_CHECK_PASTE"

    # Single or partial search query
    mode = "PARTIAL_SEARCH" if matched_categories <= 2 else "SINGLE_SEARCH"
    return False, detected_price, is_vb, 0.10, mode

class MultiLineAdParser:
    """
    Parses multi-line Kleinanzeigen ad dumps cleanly into individual components:
    - Strips bullet points, emojis, and seller floskeln/annotations
    - 0ms deterministic catalog lookup & category regex matching
    - Avoids query-stitching and preserves motherboard, RAM, storage, case, cooler
    """
    def __init__(self, catalog: Optional[HardwareCatalog] = None):
        self.catalog = catalog or HardwareCatalog()

    def parse_ad_text(self, text: str) -> Tuple[List[EvaluatedComponent], List[str], Optional[float], bool]:
        """
        Parses ad text lines into evaluated components.
        Returns:
            (evaluated_components, unrecognized_lines, detected_price, is_vb)
        """
        if not text:
            return [], [], None, False

        # Split lines
        raw_lines = text.splitlines()
        if len(raw_lines) <= 1 and (" - " in text or " • " in text or "\n" in text):
            # Split on bullets if pasted as a single line
            raw_lines = re.split(r"(?:(?:\s*-\s+)|(?:\s*•\s+)|(?:\s*\*\s+))", text)

        components: List[EvaluatedComponent] = []
        unrecognized: List[str] = []
        detected_price: Optional[float] = None
        is_vb: bool = False

        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line:
                continue

            # Check if this line is purely a price tag
            price_m = re.match(r"^(?:preis\s*:?\s*)?(\d{2,4})\s*(?:€|euro)\s*(vb|vhb|festpreis)?\s*$", line, re.I)
            if price_m:
                try:
                    detected_price = float(price_m.group(1))
                    is_vb = bool((price_m.group(2) or "").lower() in ["vb", "vhb"])
                except Exception:
                    pass
                continue

            # Also check for embedded price in line if not yet found
            if detected_price is None:
                sub_pm = PRICE_PATTERN.search(line)
                if sub_pm and any(kw in line.lower() for kw in ["preis", "vb", "festpreis", "abzugeben für"]):
                    try:
                        detected_price = float(sub_pm.group(1))
                        is_vb = bool((sub_pm.group(2) or "").lower() in ["vb", "vhb"])
                    except Exception:
                        pass

            # Skip disclaimers / benchmark / legal notes unless explicitly prefixed with component label
            if AD_DISCLAIMER_PATTERN.search(line) and not re.match(r"(?i)^[\s\-\*\•\d\.\(\)\[\]\:\>]*(?:prozessor|cpu|grafikkarte|gpu|mainboard|motherboard|ram|arbeitsspeicher|ssd|festplatte|gehäuse|netzteil|wasserkühlung|kühler)\b", line):
                unrecognized.append(line)
                continue

            comp = self._parse_single_line(line)
            if comp:
                # Deduplicate if duplicate singular category (CPU, GPU, MB, PSU, Cooler, Case) or exact name
                SINGULAR_CATS = {"CPU", "GPU", "MOTHERBOARD", "CASE", "PSU", "COOLER"}
                existing_idx = None
                for idx, existing in enumerate(components):
                    if existing.category == comp.category and comp.category in SINGULAR_CATS:
                        existing_idx = idx
                        break
                    elif existing.canonical_name.strip().lower() == comp.canonical_name.strip().lower():
                        existing_idx = idx
                        break

                if existing_idx is not None:
                    existing = components[existing_idx]
                    # If existing is catalog match and new is not, keep existing
                    if existing.is_catalog_match and not comp.is_catalog_match:
                        pass
                    # If new is catalog match and existing is not, upgrade to catalog match
                    elif not existing.is_catalog_match and comp.is_catalog_match:
                        components[existing_idx] = comp
                    # If both are catalog matches, keep the more specific one or higher confidence
                    elif comp.confidence > existing.confidence:
                        components[existing_idx] = comp
                else:
                    components.append(comp)
            else:
                # Non-hardware line (boilerplate or unrecognized)
                if not AD_BOILERPLATE_PATTERN.search(line) and len(line) > 3:
                    unrecognized.append(line)

        return components, unrecognized, detected_price, is_vb

    def _parse_single_line(self, line: str) -> Optional[EvaluatedComponent]:
        """Sanitizes and evaluates a single spec line against catalog and heuristics."""
        clean = line.strip()
        # 1. Strip leading bullets, numbers, emojis
        clean = re.sub(r"^[\s\-\*\•\d\.\(\)\[\]\:\>]+", "", clean).strip()

        # 2. Detect category prefix (e.g. "Mainboard Asus ...", "CPU Kühler ...", "GPU ASUS ...")
        detected_category = self._detect_category_prefix(clean)
        # Strip the prefix for cleaner catalog matching
        stripped_prefix = self._strip_category_prefix(clean)

        # 3. Clean seller annotations, prose, and parenthetical fluff
        sanitized = self._clean_annotations(stripped_prefix)

        # 4. Catalog Fast-Path Lookup (0ms)
        cat_match = None
        if detected_category:
            try:
                comp_type = ComponentType(detected_category)
                cat_match = self.catalog.find_item(sanitized, comp_type)
                if not cat_match:
                    cat_match = self.catalog.find_item(stripped_prefix, comp_type)
            except Exception:
                pass

        if not cat_match:
            cat_match = self.catalog.find_item(sanitized)
        if not cat_match:
            cat_match = self.catalog.find_item(stripped_prefix)

        if cat_match:
            return EvaluatedComponent(
                category=cat_match.category if hasattr(cat_match, 'category') else cat_match.type,
                raw_name=line,
                canonical_name=cat_match.canonical_name,
                catalog_id=cat_match.id,
                market_value_min=cat_match.used_price_min or round(cat_match.used_price_fair * 0.85, 2),
                market_value_max=cat_match.used_price_max or round(cat_match.used_price_fair * 1.15, 2),
                market_value_fair=cat_match.used_price_fair,
                is_catalog_match=True,
                confidence=1.0,
                specs_summary=f"{cat_match.canonical_name} ({cat_match.tier})"
            )

        # 5. Regex-based Heuristics for non-catalog components (Cooler, Storage, Case, Custom Mobo/RAM/PSU)
        return self._heuristic_component_match(clean, sanitized, detected_category)

    def _detect_category_prefix(self, text: str) -> Optional[str]:
        t_upper = text.upper()
        if re.match(r"^(?:CPU\s*KÜHLER|CPU\s*COOLER|KÜHLER|COOLER|WAKÜ|AIO)\b", t_upper):
            return "COOLER"
        if re.match(r"^(?:CPU|PROZESSOR)\b", t_upper):
            return "CPU"
        if re.match(r"^(?:GPU|GRAFIKKARTE|GRAFIK)\b", t_upper):
            return "GPU"
        if re.match(r"^(?:MAINBOARD|MOTHERBOARD|BOARD)\b", t_upper):
            return "MOTHERBOARD"
        if re.match(r"^(?:RAM|ARBEITSSPEICHER|SPEICHERRIEGEL)\b", t_upper):
            return "RAM"
        if re.match(r"^(?:SSD|NVME|M\.2|FESTPLATTE|STORAGE)\b", t_upper):
            return "STORAGE"
        if re.match(r"^(?:GEHÄUSE|CASE|TOWER)\b", t_upper):
            return "CASE"
        if re.match(r"^(?:NETZTEIL|PSU|POWER\s*SUPPLY)\b", t_upper):
            return "PSU"
        return None

    def _strip_category_prefix(self, text: str) -> str:
        pattern = r"^(?:CPU\s*KÜHLER|CPU\s*COOLER|KÜHLER|COOLER|WAKÜ|AIO|CPU|PROZESSOR|GPU|GRAFIKKARTE|GRAFIK|MAINBOARD|MOTHERBOARD|BOARD|RAM|ARBEITSSPEICHER|SSD|NVME|M\.2|FESTPLATTE|STORAGE|GEHÄUSE|CASE|TOWER|NETZTEIL|PSU|POWER\s*SUPPLY)\s*[:\-]?\s*"
        return re.sub(pattern, "", text, flags=re.I).strip()

    def _clean_annotations(self, text: str) -> str:
        """Removes modification details, paste descriptions, and fluffy parentheticals."""
        t = text
        # Remove parenthetical fluff: (Top Performance...), (Rechnung vorhanden...), etc.
        t = re.sub(r"\([^)]*(?:performance|wärmeleitpaste|ptm|leise|jahre|garantie|rechnung|neuwertig|shroud|l[üu]fter)[^)]*\)", "", t, flags=re.I)
        # Split on dashes or phrases describing mods
        t = re.split(r"(?:\s*-\s+PTM|\s*-\s+W[äa]rmeleitpaste|\s*mit\s+PTM|\s*mit\s+W[äa]rmeleitpaste|\s*3D\s*gedruckt|\s*Das\s+originale)", t, flags=re.I)[0]
        return t.strip()

    def _heuristic_component_match(self, raw_line: str, sanitized: str, detected_category: Optional[str]) -> Optional[EvaluatedComponent]:
        """Matches categories not explicitly defined in the 241-component catalog (Cooler, Storage, Case)."""
        text_to_check = f"{sanitized} {raw_line}"
        t_upper = text_to_check.upper()

        # 1. CPU COOLER
        if detected_category == "COOLER" or REGEX_COOLER.search(t_upper):
            name = sanitized or "Tower CPU-Kühler"
            fair_price = 30.0
            if "DARK ROCK PRO" in t_upper or "NH-D15" in t_upper or "360" in t_upper:
                fair_price = 45.0
            elif "AIO" in t_upper or "WASSERKÜHLUNG" in t_upper:
                fair_price = 55.0
            return EvaluatedComponent(
                category="COOLER",
                raw_name=raw_line,
                canonical_name=name,
                catalog_id=None,
                market_value_min=round(fair_price * 0.8, 2),
                market_value_max=round(fair_price * 1.2, 2),
                market_value_fair=fair_price,
                is_catalog_match=False,
                confidence=0.90,
                specs_summary="CPU-Kühler (Luft / AIO)"
            )

        # 2. STORAGE (SSD / NVMe / HDD)
        if detected_category == "STORAGE" or REGEX_STORAGE.search(t_upper):
            fair_price = 55.0
            name = "1TB NVMe M.2 SSD"
            if re.search(r"\b(?:4\s*TB|4000\s*GB)\b", t_upper):
                fair_price = 190.0
                name = "4TB NVMe M.2 SSD"
            elif re.search(r"\b(?:2\s*TB|2000\s*GB)\b", t_upper):
                fair_price = 100.0
                name = "2TB NVMe M.2 SSD"
            elif re.search(r"\b(?:1\s*TB|1000\s*GB)\b", t_upper):
                fair_price = 55.0
                name = "1TB NVMe M.2 SSD"
            elif re.search(r"\b(?:500\s*GB|512\s*GB)\b", t_upper):
                fair_price = 28.0
                name = "512GB NVMe M.2 SSD"
            elif re.search(r"\b(?:250\s*GB|256\s*GB)\b", t_upper):
                fair_price = 18.0
                name = "256GB SSD"
            return EvaluatedComponent(
                category="STORAGE",
                raw_name=raw_line,
                canonical_name=sanitized or name,
                catalog_id=None,
                market_value_min=round(fair_price * 0.85, 2),
                market_value_max=round(fair_price * 1.15, 2),
                market_value_fair=fair_price,
                is_catalog_match=False,
                confidence=0.92,
                specs_summary=f"M.2 PCIe NVMe SSD (~{fair_price:.0f}€)"
            )

        # 3. CASE (Gehäuse)
        if detected_category == "CASE" or REGEX_CASE.search(t_upper):
            fair_price = 50.0
            if "PURE BASE 500" in t_upper or "SHADOW BASE" in t_upper or "FRACTAL" in t_upper:
                fair_price = 55.0
            return EvaluatedComponent(
                category="CASE",
                raw_name=raw_line,
                canonical_name=sanitized or "Airflow ATX Gehäuse",
                catalog_id=None,
                market_value_min=round(fair_price * 0.80, 2),
                market_value_max=round(fair_price * 1.20, 2),
                market_value_fair=fair_price,
                is_catalog_match=False,
                confidence=0.88,
                specs_summary="Gaming-Gehäuse mit Glas/Airflow"
            )

        # 4. Fallback checks for CPU/GPU/MB/RAM/PSU if catalog missed custom branding
        if detected_category == "GPU" or REGEX_GPU.search(t_upper):
            m = REGEX_GPU.search(t_upper)
            gpu_str = m.group(0) if m else "GPU"
            cat_gpu = self.catalog.find_item(gpu_str, ComponentType.GPU)
            fair = cat_gpu.used_price_fair if cat_gpu else 250.0
            return EvaluatedComponent(
                category="GPU",
                raw_name=raw_line,
                canonical_name=cat_gpu.canonical_name if cat_gpu else gpu_str,
                catalog_id=cat_gpu.id if cat_gpu else None,
                market_value_min=round(fair * 0.85, 2),
                market_value_max=round(fair * 1.15, 2),
                market_value_fair=fair,
                is_catalog_match=bool(cat_gpu),
                confidence=0.85,
                specs_summary="Grafikkarte"
            )

        if detected_category == "CPU" or REGEX_CPU.search(t_upper):
            m = REGEX_CPU.search(t_upper)
            cpu_str = m.group(0) if m else "CPU"
            cat_cpu = self.catalog.find_item(cpu_str, ComponentType.CPU)
            fair = cat_cpu.used_price_fair if cat_cpu else 150.0
            return EvaluatedComponent(
                category="CPU",
                raw_name=raw_line,
                canonical_name=cat_cpu.canonical_name if cat_cpu else cpu_str,
                catalog_id=cat_cpu.id if cat_cpu else None,
                market_value_min=round(fair * 0.85, 2),
                market_value_max=round(fair * 1.15, 2),
                market_value_fair=fair,
                is_catalog_match=bool(cat_cpu),
                confidence=0.85,
                specs_summary="Prozessor"
            )

        if detected_category == "MOTHERBOARD" or REGEX_MB.search(t_upper):
            m = REGEX_MB.search(t_upper)
            chipset = m.group(1).upper() if m else "B550"
            fair = 80.0
            if chipset in ["B450", "A320", "A520", "H410", "H510", "H610"]: fair = 60.0
            elif chipset in ["X570", "Z690", "Z790", "X670"]: fair = 130.0
            return EvaluatedComponent(
                category="MOTHERBOARD",
                raw_name=raw_line,
                canonical_name=f"{chipset} Motherboard",
                catalog_id=None,
                market_value_min=round(fair * 0.85, 2),
                market_value_max=round(fair * 1.15, 2),
                market_value_fair=fair,
                is_catalog_match=False,
                confidence=0.85,
                specs_summary=f"{chipset} Mainboard"
            )

        if detected_category == "RAM" or REGEX_RAM.search(t_upper):
            is_ddr5 = "DDR5" in t_upper
            is_32gb = "32" in t_upper
            is_64gb = "64" in t_upper
            fair = 60.0 if not is_ddr5 else 90.0
            if not is_32gb and not is_64gb: fair = 35.0 if not is_ddr5 else 45.0
            ram_name = f"{'32GB' if is_32gb else ('64GB' if is_64gb else '16GB')} {'DDR5' if is_ddr5 else 'DDR4'} RAM"
            return EvaluatedComponent(
                category="RAM",
                raw_name=raw_line,
                canonical_name=ram_name,
                catalog_id=None,
                market_value_min=round(fair * 0.85, 2),
                market_value_max=round(fair * 1.15, 2),
                market_value_fair=fair,
                is_catalog_match=False,
                confidence=0.85,
                specs_summary=ram_name
            )

        if detected_category == "PSU" or REGEX_PSU.search(t_upper):
            watt_m = re.search(r"(\d{3,4})\s*W", t_upper)
            watts = int(watt_m.group(1)) if watt_m else 650
            fair = 50.0 if watts <= 550 else (65.0 if watts <= 750 else 85.0)
            return EvaluatedComponent(
                category="PSU",
                raw_name=raw_line,
                canonical_name=f"{watts}W Power Supply",
                catalog_id=None,
                market_value_min=round(fair * 0.85, 2),
                market_value_max=round(fair * 1.15, 2),
                market_value_fair=fair,
                is_catalog_match=False,
                confidence=0.85,
                specs_summary=f"{watts}W Netzteil"
            )

        return None

class DealChecker:
    """
    Evaluates pasted ad listings against individual component market values.
    Calculates arbitrage savings, price assessment, gap fillers, and negotiation advice.
    """
    def __init__(self, catalog: Optional[HardwareCatalog] = None):
        self.catalog = catalog or HardwareCatalog()
        self.parser = MultiLineAdParser(self.catalog)

    def evaluate_ad(
        self,
        ad_text: str,
        seller_asking_price: Optional[float] = None,
        is_vb: bool = False,
        session_logger: Optional[SessionLogger] = None
    ) -> DealCheckResult:
        """
        Main valuation entry point.
        """
        components, unrecognized, parsed_price, parsed_vb = self.parser.parse_ad_text(ad_text)

        final_price = seller_asking_price if seller_asking_price is not None else (parsed_price or 0.0)
        final_vb = is_vb or parsed_vb

        total_market_value = sum(c.market_value_fair for c in components)
        arbitrage_savings = round(total_market_value - final_price, 2) if final_price > 0 else 0.0
        savings_pct = round((arbitrage_savings / total_market_value) * 100, 1) if total_market_value > 0 and final_price > 0 else 0.0

        # Assessment classification
        if final_price <= 0:
            assessment = PriceAssessment.UNKNOWN
            headline = "ℹ️ Preis unvollständig"
            desc = "Der Verkäufer hat keinen Preis genannt. Bitte trage den Angebotspreis ein, um den Deal zu bewerten."
        elif arbitrage_savings >= 150.0 or savings_pct >= 20.0:
            assessment = PriceAssessment.TOP_DEAL
            headline = "🔥 Top Deal - Sehr gutes Schnäppchen!"
            desc = f"Die verbauten Einzelteile haben einen fairen Marktwert von ~{total_market_value:.0f} €. Du sparst rund {arbitrage_savings:.0f} € ({savings_pct:.0f}%). Schnell zuschlagen und vor Ort testen!"
        elif arbitrage_savings >= -50.0:
            assessment = PriceAssessment.FAIR_DEAL
            headline = "⚖️ Fairer Gebrauchtpreis"
            desc = f"Die verbauten Komponenten entsprechen weitgehend dem Angebotspreis (Marktwert ~{total_market_value:.0f} €). Eine moderate Verhandlung um 8–12% ist marktüblich."
        else:
            assessment = PriceAssessment.OVERPRICED
            headline = "❌ Zu teuer - Einzelkauf oder Alternativen günstiger"
            desc = f"Der Angebotspreis ({final_price:.0f} €) liegt {abs(arbitrage_savings):.0f} € über dem fairen Gebrauchtmarktwert (~{total_market_value:.0f} €). Nicht zum Festpreis kaufen!"

        # Missing essential parts for Ready-to-Play operation
        present_categories = {c.category for c in components}
        missing_parts = []
        ready_to_play_extra = 0.0

        ESSENTIAL_SLOTS = [
            ("MOTHERBOARD", "Mainboard (passender Chipsatz: +80 €)", 80.0),
            ("PSU", "Netzteil (650W 80+ Standard: +65 €)", 65.0),
            ("COOLER", "CPU-Kühler (120mm Tower: +30 €)", 30.0),
            ("CASE", "Gehäuse (Standard Airflow ATX: +50 €)", 50.0),
            ("STORAGE", "SSD (1TB M.2 NVMe: +55 €)", 55.0),
            ("RAM", "Arbeitsspeicher (16GB RAM Kit: +45 €)", 45.0),
            ("CPU", "Prozessor (passende Gaming-CPU: +150 €)", 150.0),
            ("GPU", "Grafikkarte (Dedizierte Gaming-GPU: +250 €)", 250.0),
        ]

        for cat, label, cost in ESSENTIAL_SLOTS:
            if cat not in present_categories:
                missing_parts.append(label)
                ready_to_play_extra += cost

        if final_price > 0:
            ready_to_play_total = round(final_price + ready_to_play_extra, 2)
        else:
            ready_to_play_total = round(total_market_value + ready_to_play_extra, 2)

        # Negotiation Strategy
        negotiation = None
        if final_price > 0:
            negotiation = self._generate_negotiation_strategy(
                final_price, final_vb, total_market_value, assessment, components
            )

        result = DealCheckResult(
            seller_asking_price=final_price,
            is_vb=final_vb,
            total_market_value=round(total_market_value, 2),
            arbitrage_savings=arbitrage_savings,
            savings_percent=savings_pct,
            assessment=assessment,
            assessment_headline=headline,
            assessment_description=desc,
            components=components,
            unrecognized_lines=unrecognized,
            missing_essential_parts=missing_parts,
            ready_to_play_additional_cost=round(ready_to_play_extra, 2),
            ready_to_play_total_cost=round(ready_to_play_total, 2),
            negotiation=negotiation,
            raw_ad_text=ad_text
        )

        # Pre-Implementation Telemetry Logging
        if session_logger:
            session_logger.log_deal_check_evaluated(
                seller_asking_price=final_price,
                is_vb=final_vb,
                total_part_market_value=total_market_value,
                arbitrage_savings=arbitrage_savings,
                savings_percent=savings_pct,
                price_assessment=assessment.value,
                components=[
                    {
                        "category": c.category,
                        "raw_name": c.raw_name,
                        "canonical_name": c.canonical_name,
                        "catalog_match_id": c.catalog_id,
                        "market_value_fair": c.market_value_fair,
                        "is_catalog_match": c.is_catalog_match,
                        "confidence": c.confidence
                    } for c in components
                ],
                negotiation_target_price=negotiation.target_offer_price if negotiation else None
            )

        return result

    def _generate_negotiation_strategy(
        self,
        asking_price: float,
        is_vb: bool,
        market_value: float,
        assessment: PriceAssessment,
        components: List[EvaluatedComponent]
    ) -> NegotiationStrategy:
        """Generates realistic German negotiation template for Kleinanzeigen."""
        # Highlight top 2 key components (GPU, CPU preferred)
        key_parts = []
        for c in components:
            if c.category in ["GPU", "CPU"] and c.canonical_name not in key_parts:
                key_parts.append(c.canonical_name)
        if not key_parts and components:
            key_parts = [components[0].canonical_name]

        key_parts_str = ", ".join(key_parts[:2])

        if assessment == PriceAssessment.OVERPRICED:
            # Anchor strongly towards market value
            target_price = round(min(asking_price * 0.85, market_value * 0.92) / 10.0) * 10.0
            rationale = "Angebot liegt über Marktwert. Verhandlung orientiert sich am fairen Marktwert der Komponenten."
        elif is_vb:
            # 10-14% discount for standard VB
            target_price = round((asking_price * 0.88) / 10.0) * 10.0
            rationale = "Verhandlungsbasis (VB) aktiv: 12% Nachlass für schnelle Abholung und Barzahlung."
        else:
            # Moderate 5-8% discount for Festpreis
            target_price = round((asking_price * 0.92) / 10.0) * 10.0
            rationale = "Festpreis-Angebot: Höflicher Vorstoß mit 8% Nachlass für sofortige unkomplizierte Abholung."

        target_price = max(10.0, target_price)
        discount_pct = round(((asking_price - target_price) / asking_price) * 100, 1)

        msg = (
            f"Hallo, ich habe Interesse an deinem Gaming-PC.\n"
            f"Aufgrund der verbauten Komponenten ({key_parts_str}) und der aktuellen Marktlage "
            f"könnte ich dir faire {target_price:.0f} € anbieten.\n"
            f"Ich könnte das System zeitnah vor Ort abholen, kurz testen und bar bezahlen. "
            f"Würde das für dich passen? Viele Grüße!"
        )

        return NegotiationStrategy(
            target_offer_price=target_price,
            suggested_discount_pct=discount_pct,
            rationale=rationale,
            chat_message_german=msg
        )
