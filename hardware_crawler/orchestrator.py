import logging
import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .llm_client import LLMClient
from .agents import HardwareIntentAgent, HardwareKnowledgeAgent, DataCardAgent, BuildAgent
from .models import CanonicalSpec, ComponentType, ValidationStatus, Build, Listing
from .scrapers import KleinanzeigenScraper
from .verification import VerificationEngine
from .analysis import SimilarityEngine, CombinationEngine, DatabaseManager, GapAnalyzer

logger = logging.getLogger(__name__)

class HardwareOrchestrator:
    """
    Central brain of the Hardware Agent.
    Orchestrates: Intent -> Search -> Verify -> Alternatives -> Optimize.
    """
    def __init__(self, api_key: str = None):
        self.client = LLMClient(api_key=api_key)
        self.intent_agent = HardwareIntentAgent(self.client)
        self.knowledge_agent = HardwareKnowledgeAgent(self.client)
        self.data_card_agent = DataCardAgent(self.client)
        self.build_agent = BuildAgent(self.client)
        self.scraper = KleinanzeigenScraper()
        self.db_manager = DatabaseManager()
        self.similarity_engine = SimilarityEngine(self.db_manager)
        
        # State
        self.specs: List[CanonicalSpec] = []
        self.listings_map: Dict[str, List[Listing]] = {}
        self.build_listings: List[Listing] = []
        self.latest_build: Optional[Build] = None

    # German translations for common English terms
    GERMAN_SEARCH_ALIASES = {
        "water cooling": ["Wasserkühlung", "AIO Kühler", "AIO 360"],
        "fan": ["Lüfter"],
        "case": ["Gehäuse"],
        "power supply": ["Netzteil"],
        "cooler": ["Kühler", "CPU Kühler"],
    }
    
    BRAND_PREFIXES = {"NVIDIA", "GEFORCE", "AMD", "RADEON", "INTEL", "ASUS", "MSI", "GIGABYTE", "ZOTAC", "EVGA", "SAPPHIRE", "POWERCOLOR", "ASROCK", "CORSAIR", "NZXT", "KINGSTON"}

    def process_user_intent(self, user_input: str) -> List[str]:
        """
        Parses user input, creates CanonicalSpecs, and adds them to the state.
        Returns list of added component names.
        """
        raw_components = self.intent_agent.parse_input(user_input)
        added_names = []

        for comp in raw_components:
            name = comp.get("normalized_name") or comp.get("raw_name")
            c_type_str = comp.get("type", "UNKNOWN")
            try:
                c_type = ComponentType(c_type_str)
            except:
                c_type = ComponentType.UNKNOWN
            
            # Build smart search queries
            queries = self._build_search_queries(name, comp.get("raw_name", name))
            
            # Filter brand prefixes from mandatory tokens
            must_tokens = [t for t in name.split() if t.upper() not in self.BRAND_PREFIXES]
            
            spec = CanonicalSpec(
                name=name,
                type=c_type,
                must_contain_tokens=must_tokens,
                must_exclude_tokens=comp.get("constraints", []),
                expected_attributes={},
                search_queries=queries
            )
            
            # AI Enrichment: Data Card
            logger.info(f"Generating Data Card for {name}...")
            spec.data_card = self.data_card_agent.enrich_component(name)
            
            # Dedup
            if not any(s.name == spec.name for s in self.specs):
                self.specs.append(spec)
                added_names.append(name)
                
        return added_names

    def _build_search_queries(self, name: str, raw_name: str) -> List[str]:
        """
        Generates multiple search query variants for better coverage.
        """
        queries = []
        
        # Primary: full name
        queries.append(name)
        
        # Secondary: raw name (if different)
        if raw_name and raw_name != name:
            queries.append(raw_name)
        
        # Tertiary: shortened query for overly specific searches
        tokens = name.split()
        if len(tokens) >= 4:
            # Keep first 3 key tokens (skip brand prefixes)
            key_tokens = [t for t in tokens if t.upper() not in self.BRAND_PREFIXES]
            if len(key_tokens) >= 3:
                queries.append(" ".join(key_tokens[:3]))
        
        # German aliases
        name_lower = name.lower()
        for english, german_variants in self.GERMAN_SEARCH_ALIASES.items():
            if english in name_lower:
                queries.extend(german_variants)
                break
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)
        return unique

    def run_market_scan(self, progress_callback=None) -> Dict[str, Any]:
        """
        Executes the search pipeline for all specs and their alternatives.
        """
        results = {}
        report = {
            "alternatives_found": {}
        }
        
        # 0. Generate Alternatives proactively using LLM instead of just DB
        alt_specs = []
        for spec in self.specs:
            if spec.type in [ComponentType.UNKNOWN, ComponentType.BUILD, ComponentType.ACCESSORY, ComponentType.FAN]:
                continue
            logger.info(f"Finding alternatives for {spec.name} via LLM...")
            alts_str = self.knowledge_agent.find_alternatives(spec.name)
            if alts_str:
                report["alternatives_found"][spec.name] = alts_str
                for alt_name in alts_str:
                    from .canonicalization import CanonicalSpecFactory
                    alt_spec = CanonicalSpecFactory.from_text_input(alt_name)
                    alt_specs.append((spec.name, alt_spec))

        all_tasks = [(None, s) for s in self.specs] + alt_specs

        # 1. Parallel Search & Verify
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_spec = {executor.submit(self._search_and_verify, task_spec): (parent_name, task_spec) for parent_name, task_spec in all_tasks}
            
            completed = 0
            for future in as_completed(future_to_spec):
                parent_name, task_spec = future_to_spec[future]
                _, listings = future.result()
                
                target_key = parent_name if parent_name else task_spec.name
                if target_key not in results:
                    results[target_key] = []
                    
                # Mark alternatives
                if parent_name:
                    for l in listings:
                        setattr(l, 'is_alternative', True)
                        setattr(l, 'alternative_for', parent_name)
                        
                results[target_key].extend(listings)
                
                completed += 1
                if progress_callback:
                    progress_callback(completed / len(all_tasks), task_spec.name)

        self.listings_map.update(results)
        
        # 2. Search for Complete PCs (Builds)
        from .canonicalization import CanonicalSpecFactory
        build_names = [s.name for s in self.specs if s.type in [ComponentType.GPU, ComponentType.CPU]]
        if build_names:
            build_spec = CanonicalSpecFactory.create_build_spec(", ".join(build_names))
            logger.info(f"Searching for complete PCs: {build_spec.name}")
            _, self.build_listings = self._search_and_verify(build_spec)
        
        # 3. Optimize Build (Virtual Build from Parts)
        if self.listings_map:
            self.latest_build = CombinationEngine.create_best_build(self.specs, self.listings_map)
            
            # AI Build Plan
            if self.latest_build:
                # Get current component names from the build
                current_parts = [c.product_match.name for c in self.latest_build.components if c.product_match]
                if not current_parts:
                    # Fallback to specs if build is empty (e.g. price limits)
                    current_parts = [s.name for s in self.specs]
                    
                report["ai_build_plan"] = self.build_agent.create_build_plan(current_parts)
                logger.info(f"AI Build Plan: {report['ai_build_plan']}")

        return report

    def _search_and_verify(self, spec: CanonicalSpec):
        """Worker method."""
        raw_listings = self.scraper.search_for_spec(spec)
        verified = []
        
        filtered_count = 0
        reasons_summary = {}
        
        for l in raw_listings:
             res = VerificationEngine.verify(l, spec)
             l.verification = res
             verified.append(l)
             
             if res.status == ValidationStatus.REJECT:
                 filtered_count += 1
                 reason = res.rejection_reasons[0] if res.rejection_reasons else "Unknown Reason"
                 reasons_summary[reason] = reasons_summary.get(reason, 0) + 1
                 
        if raw_listings:
            summary = ", ".join([f"{k} ({v})" for k,v in reasons_summary.items()])
            logger.info(f"[{spec.name}] Verified {len(raw_listings)} listings. Rejected {filtered_count}. Reasons: {summary}")
             
        return spec.name, verified

    # For CLI/Test Usage
    def run_scenario(self, user_input: str) -> Dict[str, Any]:
        """Legacy method wrapper for backwards compatibility."""
        self.process_user_intent(user_input)
        report = self.run_market_scan()
        return {
            "success": True, 
            "results": {k: len(v) for k,v in self.listings_map.items()},
            "alternatives": report["alternatives_found"]
        }

if __name__ == "__main__":
    # Self-Test
    orch = HardwareOrchestrator()
    print("Testing Orchestrator...")
    orch.run_scenario("Ryzen 5 3600")
