import logging
from typing import List, Dict, Any
from .llm_client import LLMClient
from .models import ComponentType

logger = logging.getLogger(__name__)

class HardwareIntentAgent:
    """
    Uses LLM to parse unstructured user input into structured hardware specs.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def parse_input(self, text: str) -> List[Dict[str, Any]]:
        system_prompt = """
        You are an expert PC Hardware Parser.
        Your task is to extract hardware components from the user's search string. The input might be a comma-separated list OR a raw copy-paste dump (multi-line).
        
        Rules:
        1. Identify the Component Type.
           - MAIN: CPU, GPU, MOTHERBOARD, RAM, PSU, CASE, COOLER, STORAGE.
           - ACCESSORIES: FAN, CABLE (extensions/sleeved), PERIPHERAL (Mouse/Keyboard), CONTROLLER (Fan Hubs), TUBE (Watercooling).
        2. Normalize the Model Name (e.g. "3070ti" -> "RTX 3070 Ti").
        3. Extract constraints (e.g. "defekt", "ovp").
        4. If input is a raw list, return ALL items as separate objects.
        
        Output JSON Schema:
        {
            "components": [
                {
                    "type": "CPU",
                    "raw_name": "Ryzen 5800X",
                    "normalized_name": "AMD Ryzen 7 5800X",
                    "constraints": []
                }
            ]
        }
        """
        
        prompt = f"Parse this search query: '{text}'"
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result.get("components", [])
        except Exception as e:
            logger.error(f"Intent Parsing Failed: {e}")
            return []

class HardwareKnowledgeAgent:
    """
    Uses LLM to provide hardware knowledge (compat, alternatives).
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def find_alternatives(self, model_name: str, range_percent: int = 10) -> List[str]:
        system_prompt = """
        You are a top-tier PC Hardware Expert specializing in GAMING performance.
        List 3-5 alternative hardware models that offer identical or slightly better GAMING performance compared to the requested part.
        RULES:
        1. Do NOT include the part itself.
        2. For CPUs: Only suggest CPUs from the same socket OR the direct modern equivalent. Do not suggest older high-core-count workstation CPUs (e.g. do not suggest 5900X for a 7800X3D).
        3. For GPUs: Focus on rasterization gaming performance +/- 15%.
        
        Output JSON Schema:
        {
            "alternatives": ["Model A", "Model B"]
        }
        """
        
        prompt = f"Find alternatives for: {model_name}. Tolerance: {range_percent}%"
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result.get("alternatives", [])
        except Exception as e:
            logger.error(f"Alternative Search Failed: {e}")
            return []

    def recommend_missing(self, current_parts: List[str]) -> Dict[str, str]:
        system_prompt = """
        You are a System Builder AI.
        Given a list of owned parts, recommend the best budget-to-mid-range MISSING parts to complete the build.
        Focus on value for money (used market).
        
        Output JSON Schema:
        {
            "recommendations": {
                "MOTHERBOARD": "B550 Dataset",
                "PSU": "650W Gold",
                ...
            }
        }
        """
        
        prompt = f"Current parts: {', '.join(current_parts)}. specific recommendations for missing critical parts?"
         
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result.get("recommendations", {})
        except Exception as e:
            logger.error(f"Recommendation Failed: {e}")
            return {}

class HardwareVerificationAgent:
    """
    Uses LLM to verify if a listing matches the user's search intent.
    Checks for: Correct Category (e.g. not a laptop for a GPU search), correct model, and valid sell offer.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def verify_listing(self, search_spec_name: str, listing_title: str, listing_description: str) -> Dict[str, Any]:
        """
        Returns JSON: { "is_valid": bool, "confidence": float, "reason": str }
        """
        system_prompt = """
        You are a strict Listing Verification Agent for a Hardware Marketplace.
        Your job is to determine if a specific listing is a VALID BUYING OPTION for the user's search.

        Verification Rules:
        1. **Category Match**: If user searches for a Component (e.g. 'RTX 3070'), reject Whole Systems (Laptops, PCs) unless user asked for a 'Build'.
        2. **Sell Offer**: Reject inputs that are 'Search Requests' (Suche, Kaufe) or 'Services' (Reparatur).
        3. **Model Match**: Ensure the listing is actually for the requested model (e.g. Reject 'Box only', 'Cooler only' if searching for GPU).
        4. **Scam/Junk**: Reject obviously fake or empty listings.

        Output JSON Schema:
        {
            "is_valid": true/false,
            "confidence": 0.0 to 1.0,
            "reason": "Short explanation of decision"
        }
        """
        
        # Truncate description to save tokens/cost
        desc_short = (listing_description[:500] + '...') if len(listing_description) > 500 else listing_description
        
        prompt = f"""
        User Search: '{search_spec_name}'
        Listing Title: '{listing_title}'
        Listing Description: '{desc_short}'
        
        Is this a valid item to buy?
        """
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            # Fallback defaults if LLM hallucinates structure
            return {
                "is_valid": result.get("is_valid", False),
                "confidence": result.get("confidence", 0.0),
                "reason": result.get("reason", "AI Verification Error")
            }
        except Exception as e:
            logger.error(f"Verification Failed: {e}")
            return {"is_valid": False, "confidence": 0.0, "reason": f"Error: {e}"}

class UnknownResolverAgent:
    """
    Resolves UNKNOWN or vague items into specific search queries.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def resolve_spec(self, original_text: str) -> Dict[str, str]:
        """
        Returns { "type": "FAN", "search_query": "Silent Wings 3 140mm" }
        """
        system_prompt = """
        You are a Hardware Identification Expert.
        The user has provided a vague or unknown hardware string (e.g. "Asia Horse", "Lüfter").
        Your job is to:
        1. Identify what it likely is (Fan, Cable, Peripheral, etc.).
        2. Create a SPECIFIC search query for the used market.
        
        Output JSON:
        {
            "type": "CABLE", 
            "search_query": "Asia Horse Sleeve Kabel Kit"
        }
        """
        prompt = f"Identify and refine this hardware item: '{original_text}'"
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result
        except:
            return {"type": "UNKNOWN", "search_query": original_text}

class DataCardAgent:
    """
    Fetches technical specifications for hardware components to create 'Data Cards'.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def enrich_component(self, component_name: str) -> Dict[str, Any]:
        """
        Returns JSON with technical specs.
        """
        system_prompt = """
        You are a Technical Specification Encyclopedia for PC Hardware.
        Your goal is to provide accurate, technical 'Data Cards' for components.
        
        Focus on:
        - GPU: VRAM, TDP, Approx. 3DMark TimeSpy Score, Recommended PSU.
        - CPU: Cores/Threads, Socket, TDP, Base/Boost Clock, Launch Year.
        - MB: Socket, Chipset, Form Factor, RAM Type.
        - RAM: Type (DDR4/5), Speed (MHz), CAS Latency (typical).
        
        Output JSON Schema (Dynamic based on type):
        {
            "specs": {
                "vram": "8GB GDDR6",
                "tdp": "220W",
                "score_timespy": 13500,
                "release_year": 2021
            },
            "description": "Short 1-sentence technical summary."
        }
        """
        
        prompt = f"Create a Data Card for: '{component_name}'"
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result
        except Exception as e:
            logger.error(f"Data Card Generation Failed: {e}")
            return {}

class BuildAgent:
    """
    Intelligently combines components into a cohesive build and fills in gaps.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def create_build_plan(self, current_components: List[str], budget_mode: str = "Standard") -> Dict[str, Any]:
        """
        Analyzes current components and suggests a complete build configuration.
        """
        system_prompt = """
        You are an Expert PC Builder AI.
        Your task is to take a set of existing/chosen components and propose a COMPLETE, BALANCED build.
        
        1. Identify what is missing (CPU, GPU, MB, RAM, PSU, Case, Storage).
        2. Suggest specific models for the missing parts that are compatible and price-balanced with the existing parts.
        3. Explain your reasoning for the combination.
        
        Output JSON Schema:
        {
            "status": "Incomplete" | "Complete",
            "missing_types": ["PSU", "Case"],
            "suggestions": {
                "PSU": "Corsair RM750x (or similar Gold 750W)",
                "Case": "Fractal Design Meshify C"
            },
            "reasoning": "The RTX 3070 requires at least 650W. The Ryzen 5000 series works best with 3600MHz RAM."
        }
        """
        
        prompt = f"Current Components: {', '.join(current_components)}. Budget/Mode: {budget_mode}. Create a build plan."
        
        try:
            result = self.llm.generate_json(prompt, system_prompt)
            return result
        except Exception as e:
            logger.error(f"Build Planning Failed: {e}")
            return {"status": "Error", "reasoning": str(e)}
