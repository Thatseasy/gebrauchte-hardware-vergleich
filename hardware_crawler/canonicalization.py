import re
from typing import List, Dict, Optional, Any
from .models import CanonicalSpec, ComponentType

class PartNormalizer:
    """Normalizes raw input strings into structured hardware tokens."""
    
    @staticmethod
    def normalize_manufacturer(text: str) -> Optional[str]:
        text = text.lower()
        if "nvidia" in text or "geforce" in text: return "NVIDIA"
        if "amd" in text or "radeon" in text: return "AMD"
        if "intel" in text or "arc " in text: return "INTEL"
        # Board partners
        if "msi" in text: return "MSI"
        if "asus" in text: return "ASUS"
        if "gigabyte" in text: return "GIGABYTE"
        if "zotac" in text: return "ZOTAC"
        if "evga" in text: return "EVGA"
        if "sapphire" in text: return "SAPPHIRE"
        if "powercolor" in text: return "POWERCOLOR"
        if "asrock" in text: return "ASROCK"
        return None

    @staticmethod
    def normalize_model_token(text: str) -> str:
        """
        Standardizes model numbers (e.g. '3070ti' -> '3070_TI').
        """
        # Remove common spaces/separators for easier matching
        clean = text.upper().replace(" ", "").replace("-", "")
        
        # GPU Suffixes
        if "TI" in clean:
            base = clean.replace("TI", "")
            return f"{base}_TI"
        if "SUPER" in clean:
            base = clean.replace("SUPER", "")
            return f"{base}_SUPER"
        if "XTX" in clean:
            base = clean.replace("XTX", "")
            return f"{base}_XTX"
        if "XT" in clean: # Handle XT after XTX to avoid partial match
            base = clean.replace("XT", "")
            return f"{base}_XT"
            
        return clean

class CanonicalSpecFactory:
    """Creates CanonicalSpecs from user input or defined presets."""
    
    COMMON_EXCLUSIONS = [
        "Suche", "Defekt", "Tausch", "Verleih", "OVP leer", "Leerkarton",
        "Sticker", "Aufkleber", "Nur OVP", "Verpackung", "Ohne Karte", "Ohne CPU",
        "Wasserkühler", "Wasserblock", "Waterblock", "Kühler", "Ersatzteil",
        "Karton", "Schachtel", "Blende"
    ]
    
    @staticmethod
    def get_category_exclusions(ctype: ComponentType) -> List[str]:
        base = CanonicalSpecFactory.COMMON_EXCLUSIONS.copy()
        
        # for components, exclude whole systems
        if ctype in [ComponentType.GPU, ComponentType.CPU, ComponentType.RAM, 
                     ComponentType.MOTHERBOARD, ComponentType.PSU, ComponentType.COOLER, 
                     ComponentType.STORAGE, ComponentType.CASE]:
            base.extend(["Laptop", "Notebook", "Macbook", "Ultrabook", "Tablet", "Komplett PC", "Gaming PC"])
            
        return base

    @staticmethod
    def create_gpu_spec(model: str) -> CanonicalSpec:
        """
        model: e.g. "RTX 3070 Ti"
        """
        normalized_model = PartNormalizer.normalize_model_token(model)
        
        # Default Logic for constructing search queries and tokens
        tokens = []
        name_parts = model.split()
        for part in name_parts:
            if part.lower() not in ["rtx", "geforce", "rx", "radeon", "gpu", "img"]:
                tokens.append(part)
        
        # Hardcoded examples for robust start (in a real app, load from DB/JSON)
        # This acts as the "Knowledge Base"
        
        # 3070 Ti
        if "3070" in normalized_model and "TI" in normalized_model:
            return CanonicalSpec(
                type=ComponentType.GPU,
                name="NVIDIA GeForce RTX 3070 Ti",
                must_contain_tokens=["3070", "Ti"],
                must_exclude_tokens=["Super", "3080", "3060"], # Basic exclusion
                expected_attributes={"vram": [8]},
                search_queries=["RTX 3070 Ti", "GeForce 3070 Ti"]
            )
            
        # 3070
        if "3070" in normalized_model and "TI" not in normalized_model:
            return CanonicalSpec(
                type=ComponentType.GPU,
                name="NVIDIA GeForce RTX 3070",
                must_contain_tokens=["3070"],
                must_exclude_tokens=["Ti", "Super", "3080", "3060"],
                expected_attributes={"vram": [8]},
                search_queries=["RTX 3070 -Ti"] # Minus syntax might work on some platforms, or handle in verifying
            )
            
        # Default generic fallback
        return CanonicalSpec(
            type=ComponentType.GPU,
            name=f"Generic GPU {model}",
            must_contain_tokens=tokens,
            must_exclude_tokens=[],
            expected_attributes={},
            search_queries=[model]
        )

    @staticmethod
    def from_text_input(text: str) -> CanonicalSpec:
        """
        Main entry point. Uses Hybrid AI Approach:
        1. Try LLM Intent Parser
        2. Fallback to Regex Heuristics
        """
        # 1. Try AI Intent Agent
        try:
            from .llm_client import LLMClient
            from .agents import HardwareIntentAgent
            
            client = LLMClient()
            if client.api_key or client.provider == "ollama":
                agent = HardwareIntentAgent(client)
                parsed_list = agent.parse_input(text)
                
                if parsed_list:
                    # Take the first component if multiple returned (legacy support)
                    data = parsed_list[0] 
                    
                    # Map string type to Enum
                    ctype = ComponentType.UNKNOWN
                    try:
                        # Try exact match first
                        ctype = ComponentType(data['type'].upper())
                    except:
                        # Fallback for subsets e.g. "CONTROLLER" -> ACCESSORY if needed, 
                        # but for now we trust the LLM matches the Enum or we treat as UNKNOWN
                        # The generic fallback below handles UNKNOWN gracefully now.
                        pass
                        
                    exclusions = data.get('constraints', [])
                    exclusions.extend(CanonicalSpecFactory.get_category_exclusions(ctype))

                    return CanonicalSpec(
                        type=ctype,
                        name=data['normalized_name'],
                        must_contain_tokens=[t for t in data['normalized_name'].split() if t.upper() not in ["NVIDIA", "GEFORCE", "AMD", "RADEON", "INTEL"]],
                        must_exclude_tokens=exclusions,
                        expected_attributes={},
                        search_queries=[data['normalized_name'], data['raw_name']]
                    )
        except Exception as e:
            # Fallback silently or log
            print(f"AI Intent Parsing failed (using fallback): {e}")

        # 2. Regex / Heuristic Fallback
        text_upper = text.upper()
        
        if any(x in text_upper for x in ["RTX", "GTX", "RADEON", "RX ", "ARC "]):
            return CanonicalSpecFactory.create_gpu_spec(text)
        
        # CPU Detection
        if any(x in text_upper for x in ["RYZEN", "CORE I", "INTEL I", "ATHLON"]):
             # Placeholder for CPU Spec Creator (Can be expanded)
             return CanonicalSpec(
                type=ComponentType.CPU,
                name=f"CPU: {text}",
                must_contain_tokens=text.split(),
                must_exclude_tokens=CanonicalSpecFactory.get_category_exclusions(ComponentType.CPU),
                expected_attributes={},
                search_queries=[text]
             )
        
        # MB Detection
        if any(x in text_upper for x in ["B550", "X570", "Z690", "Z790", "B650", "B450", "MAINBOARD", "MOTHERBOARD"]):
             return CanonicalSpec(
                type=ComponentType.MOTHERBOARD,
                name=f"MB: {text}",
                must_contain_tokens=text.split(),
                must_exclude_tokens=["Defekt"],
                expected_attributes={},
                search_queries=[text]
             )

        # Generic Fallback for other hardware (CPU, Case, etc.)
        # This allows the MVP to work for "Ryzen 5800X" even if not explicitly coded
        return CanonicalSpec(
            type=ComponentType.UNKNOWN,
            name=f"Generic: {text}",
            must_contain_tokens=text.split(), # Naive: all words must be present
            must_exclude_tokens=["Suche", "Defekt"], # Basic filters
            expected_attributes={},
            search_queries=[text]
        )

    @staticmethod
    def create_build_spec(text: str) -> CanonicalSpec:
        """
        Creates a spec for a complete build or bundle.
        """
        # Cleanup input: remove commas for cleaner search queries
        tokens = [t.strip() for t in text.split(",") if t.strip()]
        base_query = " ".join(tokens)
        
        search_query = base_query
        if "Gaming PC" not in search_query.upper() and "BUNDLE" not in search_query.upper():
            search_query += " Gaming PC" # Heuristic: search for PC builds

        return CanonicalSpec(
            type=ComponentType.BUILD,
            name=f"Build: {', '.join(tokens)}",
            must_contain_tokens=tokens,
            must_exclude_tokens=["Defekt", "Einzelverkauf"],
            expected_attributes={},
            search_queries=[search_query, base_query] # Try both variants
        )

    @staticmethod
    def from_input_list(text_list: str) -> List[CanonicalSpec]:
        """
        Parses a list of components. Uses AI for the entire block if available.
        """
        if not text_list.strip():
            return []

        # 1. Try AI parsing for the WHOLE list (efficient)
        try:
            from .llm_client import LLMClient
            from .agents import HardwareIntentAgent
            
            client = LLMClient()
            if client.api_key or client.provider == "ollama":
                agent = HardwareIntentAgent(client)
                parsed_list = agent.parse_input(text_list)
                
                if parsed_list:
                    specs = []
                    for data in parsed_list:
                         ctype = ComponentType.UNKNOWN
                         try:
                             ctype = ComponentType(data['type'].upper())
                         except:
                             pass
                             
                         specs.append(CanonicalSpec(
                            type=ctype,
                            name=data['normalized_name'],
                            must_contain_tokens=[t for t in data['normalized_name'].split() if t.upper() not in ["NVIDIA", "GEFORCE", "AMD", "RADEON", "INTEL"]],
                            must_exclude_tokens=data.get('constraints', []),
                            expected_attributes={},
                            search_queries=[data['normalized_name'], data['raw_name']]
                         ))
                    return specs
        except Exception as e:
            print(f"AI List Parsing failed: {e}")

        # 2. Fallback: Split by comma and parse individually
        raw_items = [x.strip() for x in text_list.split(",") if x.strip()]
        specs = []
        for item in raw_items:
            specs.append(CanonicalSpecFactory.from_text_input(item))
        return specs
