import logging
import time
import re
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .llm_client import LLMClient
from .agents import (
    HardwareIntentAgent, HardwareKnowledgeAgent, DataCardAgent, 
    BuildAgent, HardwareVerificationAgent, CompletePCParserAgent
)
from .models import CanonicalSpec, ComponentType, ValidationStatus, Build, Listing, VerificationResult
from .scrapers import KleinanzeigenScraper
from .verification import VerificationEngine, AttributeExtractor
from .analysis import SimilarityEngine, CombinationEngine, DatabaseManager, GapAnalyzer
from .catalog import HardwareCatalog
from .logging_session import SessionLogger
from .completer import BuildCompleter, detect_partial_intent, BuildProposal

logger = logging.getLogger(__name__)

class HardwareOrchestrator:
    """
    Central brain of the Hardware Agent.
    Orchestrates: 
    Intent -> Catalog Fast-Path -> Parallel Search -> 3-Tier Verification (Script + Active LLM Edit)
    -> Dual-Track Complete PC BOM & Arbitrage -> Alternatives -> Virtual/Complete PC Optimization.
    """
    def __init__(self, api_key: str = None):
        # Session audit trail & Telemetry profiling
        self.session_logger = SessionLogger()
        self.traffic_monitor = self.session_logger.traffic_monitor
        self.perf_timer = self.session_logger.performance_timer

        self.client = LLMClient(api_key=api_key, traffic_monitor=self.traffic_monitor)
        self.intent_agent = HardwareIntentAgent(self.client)
        self.knowledge_agent = HardwareKnowledgeAgent(self.client)
        self.data_card_agent = DataCardAgent(self.client)
        self.verification_agent = HardwareVerificationAgent(self.client)
        self.pc_parser_agent = CompletePCParserAgent(self.client)
        self.build_agent = BuildAgent(self.client)
        
        self.catalog = HardwareCatalog()
        self.completer = BuildCompleter(self.catalog)
        self.scraper = KleinanzeigenScraper(traffic_monitor=self.traffic_monitor)
        self.db_manager = DatabaseManager()
        self.similarity_engine = SimilarityEngine(self.db_manager)
        
        # State
        self.specs: List[CanonicalSpec] = []
        self.listings_map: Dict[str, List[Listing]] = {}
        self.build_listings: List[Listing] = []
        self.latest_build: Optional[Build] = None
        self.is_partial_intent: bool = False
        self.build_proposals: List[BuildProposal] = []

    GERMAN_SEARCH_ALIASES = {
        "water cooling": ["Wasserkühlung", "AIO Kühler", "AIO 360"],
        "fan": ["Lüfter"],
        "case": ["Gehäuse"],
        "power supply": ["Netzteil"],
        "cooler": ["Kühler", "CPU Kühler"],
    }
    
    BRAND_PREFIXES = {
        "NVIDIA", "GEFORCE", "AMD", "RADEON", "INTEL", "ASUS", "MSI", 
        "GIGABYTE", "ZOTAC", "EVGA", "SAPPHIRE", "POWERCOLOR", "ASROCK", 
        "CORSAIR", "NZXT", "KINGSTON"
    }

    def process_user_intent(self, user_input: str) -> List[str]:
        """
        Parses user input, checks HardwareCatalog fast-path (0 ms),
        creates CanonicalSpecs, enriches with specs, and logs to session.
        """
        self.session_logger.log_session_start(user_input)
        
        with self.perf_timer.measure("Intent Parsing & Katalog-Lookup"):
            t_start = time.perf_counter()
            from .deal_checker import detect_deal_check_intent
            is_deal, det_price, is_vb, conf, mode = detect_deal_check_intent(user_input)
            
            raw_components = self.intent_agent.parse_input(user_input)
            latency_ms = (time.perf_counter() - t_start) * 1000.0

            # Log intent detection event
            line_count = len([l for l in (user_input or "").splitlines() if l.strip()])
            self.session_logger.log_intent_type_detected(
                raw_input_preview=user_input,
                line_count=line_count,
                detected_mode=mode,
                mode_confidence=conf,
                detected_seller_price=det_price,
                is_vb=is_vb,
                extracted_components_count=len(raw_components),
                unrecognized_lines=[],
                latency_ms=latency_ms
            )

            added_names = []
            unresolved_for_cards = []

            for comp in raw_components:
                name = comp.get("normalized_name") or comp.get("raw_name")
                if not name or not isinstance(name, str) or not name.strip():
                    continue
                name = name.strip()
                c_type_str = comp.get("type", "UNKNOWN")
                try:
                    c_type = ComponentType(c_type_str)
                except Exception:
                    c_type = ComponentType.UNKNOWN
                
                # Skip non-hardware / UNKNOWN components
                if c_type == ComponentType.UNKNOWN:
                    continue
                
                queries = self._build_search_queries(name, comp.get("raw_name", name))
                must_tokens = [t for t in name.split() if t.upper() not in self.BRAND_PREFIXES]
                
                spec = CanonicalSpec(
                    name=name,
                    type=c_type,
                    must_contain_tokens=must_tokens,
                    must_exclude_tokens=comp.get("constraints", []),
                    expected_attributes={},
                    search_queries=queries
                )
                
                # Catalog fast-path lookup
                catalog_item = self.catalog.find_item(name)
                if catalog_item:
                    self.traffic_monitor.record_cache_hit()
                    spec.name = catalog_item.canonical_name
                    spec.type = ComponentType(catalog_item.category)
                    spec.data_card = {
                        "specs": {
                            "tdp": f"{catalog_item.tdp_w}W",
                            "rec_psu": f"{catalog_item.rec_psu_w}W",
                            "gaming_score": catalog_item.gaming_score,
                            "tier": catalog_item.tier,
                            "socket": catalog_item.socket,
                            "memory_types": catalog_item.memory_types,
                            "used_price_fair": catalog_item.used_price_fair
                        },
                        "description": f"{catalog_item.canonical_name} ({catalog_item.tier})"
                    }
                    if catalog_item.vram_gb:
                        spec.expected_attributes["vram"] = [catalog_item.vram_gb]
                else:
                    unresolved_for_cards.append(name)
                
                # Dedup
                if not any(s.name == spec.name for s in self.specs):
                    added_names.append(spec.name)
                    self.specs.append(spec)
                    
            # Batch LLM Enrichment for items not in local catalog
            if unresolved_for_cards:
                logger.info(f"Generating Data Cards for {len(unresolved_for_cards)} items via LLM batch...")
                data_cards = self.data_card_agent.enrich_components_batch(unresolved_for_cards)
                for spec in self.specs:
                    if spec.name in data_cards:
                        spec.data_card = data_cards[spec.name]
                        
        self.session_logger.log_intent(user_input, [{"name": s.name, "type": s.type.value, "queries": s.search_queries} for s in self.specs])

        # Detect partial hardware input intent (e.g., single CPU or GPU without full build)
        self.is_partial_intent = detect_partial_intent(self.specs, user_input)
        if self.is_partial_intent:
            self.build_proposals = self.completer.complete_builds(self.specs)
            logger.info(f"Detected partial hardware intent. Generated {len(self.build_proposals)} build proposals.")
        else:
            self.build_proposals = []

        return added_names

    def apply_build_proposal(self, proposal: BuildProposal):
        """Applies a build proposal's target specs as the active search specs."""
        self.specs = list(proposal.target_specs)
        self.is_partial_intent = False
        self.session_logger.log_intent(
            f"Build Proposal Applied: {proposal.tier_name}",
            [{"name": s.name, "type": s.type.value, "queries": s.search_queries} for s in self.specs]
        )

    def _build_search_queries(self, name: str, raw_name: str) -> List[str]:
        queries = []
        queries.append(name)
        if raw_name and raw_name != name:
            queries.append(raw_name)
        
        tokens = name.split()
        if len(tokens) >= 4:
            key_tokens = [t for t in tokens if t.upper() not in self.BRAND_PREFIXES]
            if len(key_tokens) >= 3:
                queries.append(" ".join(key_tokens[:3]))
        
        name_lower = name.lower()
        for english, german_variants in self.GERMAN_SEARCH_ALIASES.items():
            if english in name_lower:
                queries.extend(german_variants)
                break
        
        seen = set()
        unique = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique.append(q)
        return unique

    def run_market_scan(self, progress_callback=None) -> Dict[str, Any]:
        """
        Executes parallel search, 3-tier verification, complete PC dual-track search,
        BOM arbitrage calculations, and build optimization.
        """
        with self.perf_timer.measure("Gesamtdauer des Scans"):
            results = {}
            report = {
                "alternatives_found": {},
                "complete_pc_deals": []
            }
            
            # 0. Fast-path Alternatives via Catalog, fallback to LLM
            # Focus alternative searches on primary compute hardware (GPU, CPU, Motherboard)
            alt_specs = []
            primary_alt_types = {ComponentType.GPU, ComponentType.CPU, ComponentType.MOTHERBOARD}
            spec_names = [s.name for s in self.specs if s.type in primary_alt_types]
            
            for s in self.specs:
                if s.type not in primary_alt_types:
                    continue
                cat_alts = self.catalog.get_alternatives(s.name, max_results=2)
                if cat_alts:
                    report["alternatives_found"][s.name] = [a.canonical_name for a in cat_alts]
                    for a in cat_alts:
                        alt_spec = CanonicalSpec(
                            name=a.canonical_name,
                            type=ComponentType(a.category),
                            must_contain_tokens=[t for t in a.canonical_name.split() if t.upper() not in self.BRAND_PREFIXES],
                            must_exclude_tokens=[],
                            expected_attributes={"vram": [a.vram_gb]} if a.vram_gb else {},
                            search_queries=[a.canonical_name]
                        )
                        alt_specs.append((s.name, alt_spec))

            # Check remaining core parts needing LLM alternatives
            unresolved_alts = [name for name in spec_names if name not in report["alternatives_found"]]
            if unresolved_alts:
                logger.info(f"Finding alternatives for {len(unresolved_alts)} parts via LLM batch...")
                alts_map = self.knowledge_agent.find_alternatives_batch(unresolved_alts)
                for original_name, alts_str in alts_map.items():
                    if alts_str:
                        report["alternatives_found"][original_name] = alts_str
                        for alt_name in alts_str:
                            from .canonicalization import CanonicalSpecFactory
                            alt_spec = CanonicalSpecFactory.from_text_input(alt_name)
                            alt_specs.append((original_name, alt_spec))

            all_tasks = [(None, s) for s in self.specs] + alt_specs

            # 1. Parallel Search & 3-Tier Funnel (max_workers=2 to avoid TCP RST)
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_to_spec = {executor.submit(self._search_and_verify, task_spec): (parent_name, task_spec) for parent_name, task_spec in all_tasks}
                
                completed = 0
            for future in as_completed(future_to_spec):
                parent_name, task_spec = future_to_spec[future]
                _, listings = future.result()
                
                target_key = parent_name if parent_name else task_spec.name
                if target_key not in results:
                    results[target_key] = []
                    
                if parent_name:
                    for l in listings:
                        setattr(l, 'is_alternative', True)
                        setattr(l, 'alternative_for', parent_name)
                        
                results[target_key].extend(listings)
                
                completed += 1
                if progress_callback:
                    progress_callback(completed / len(all_tasks), task_spec.name)

        self.listings_map.update(results)
        
        # 2. Dual-Track Complete PC Search & BOM Arbitrage
        self._search_and_evaluate_complete_pcs()
        if self.build_listings:
            report["complete_pc_deals"] = [
                {
                    "title": pc.title,
                    "price": pc.price,
                    "is_vb": pc.is_vb,
                    "url": pc.url,
                    "arbitrage_savings": pc.arbitrage_savings,
                    "has_buyer_protection": pc.has_buyer_protection,
                    "shipping_available": pc.shipping_available,
                    "bom": pc.bom
                }
                for pc in sorted([p for p in self.build_listings if not p.is_scam_suspected], key=lambda x: x.arbitrage_savings, reverse=True)[:5]
            ]
        
        # 3. Optimize Virtual Build from Loose Parts
        if self.listings_map:
            self.latest_build = CombinationEngine.create_best_build(
                self.specs, self.listings_map, session_logger=self.session_logger
            )
            
            if self.latest_build:
                current_parts = [c.product_match.name for c in self.latest_build.components if c.product_match]
                if not current_parts:
                    current_parts = [s.name for s in self.specs]
                    
                report["ai_build_plan"] = self.build_agent.create_build_plan(current_parts)
                logger.info(f"AI Build Plan: {report['ai_build_plan']}")
                
                self.session_logger.log_build_generated({
                    "total_price": self.latest_build.total_price,
                    "component_count": len(self.latest_build.components),
                    "components": [c.title for c in self.latest_build.components],
                    "compatibility_warnings": self.latest_build.compatibility_warnings
                })

            # Telemetry compilation
            telemetry_data = {
                "traffic": self.traffic_monitor.get_summary(),
                "performance": self.perf_timer.get_summary()
            }
            report["telemetry"] = telemetry_data

            # Final session log completion
            self.session_logger.log_session_complete({
                "status": "success",
                "total_specs": len(self.specs),
                "listings_found": sum(len(v) for v in self.listings_map.values()),
                "complete_pcs_found": len(self.build_listings),
                "best_virtual_build_price": self.latest_build.total_price if self.latest_build else None,
                "telemetry": telemetry_data
            })

            return report

    def _search_and_verify(self, spec: CanonicalSpec):
        """
        3-Tier Funnel Worker:
        Tier 1: Heuristic Filter & VB-Handling
        Tier 2: Batch LLM Active Verification & Edit for Uncertain/Flagged items
        """
        with self.perf_timer.measure("Kleinanzeigen Markt-Scraping"):
            raw_listings = self.scraper.search_for_spec(spec)
        self.session_logger.log_raw_scrape(
            spec.name,
            spec.search_queries[0] if spec.search_queries else spec.name,
            len(raw_listings),
            [{"title": l.title, "price": l.price, "is_vb": l.is_vb} for l in raw_listings[:5]]
        )

        with self.perf_timer.measure("Verifikation & Scam-Filterung"):
            verified = []
            escalation_candidates = []
            rejection_breakdown = {}
            passed_count = 0
            rejected_count = 0

            # Tier 1: Script Filter
            for l in raw_listings:
                res = VerificationEngine.verify(l, spec)
                l.verification = res
                
                if res.status == ValidationStatus.SCAM_SUSPECT:
                    # Do NOT drop or delete: preserve in verified to keep in listings_map
                    verified.append(l)
                    self.session_logger.log_scam_suspect(
                        spec.name, l.title, l.price, l.url, getattr(l, 'scam_reason', 'Scam Verdacht')
                    )
                elif res.status == ValidationStatus.REJECT and not VerificationEngine.should_escalate_to_llm(res):
                    rejected_count += 1
                    reason = res.rejection_reasons[0] if res.rejection_reasons else "Rejected"
                    rejection_breakdown[reason] = rejection_breakdown.get(reason, 0) + 1
                elif VerificationEngine.should_escalate_to_llm(res):
                    escalation_candidates.append(l)
                else:
                    passed_count += 1
                    verified.append(l)


        # Tier 2: LLM Batch Active Verification & Edit
        if escalation_candidates:
            logger.info(f"[{spec.name}] Escalating {len(escalation_candidates)} listings to LLM batch verification & edit...")
            batch_payload = [
                {"id": str(i), "title": l.title, "description": l.description} 
                for i, l in enumerate(escalation_candidates)
            ]
            batch_results = self.verification_agent.verify_listings_batch(spec.name, batch_payload)
            corrections = []
            rejections = []

            for i, l in enumerate(escalation_candidates):
                ai_data = batch_results.get(str(i))
                if ai_data and ai_data.get("is_valid", False):
                    l.verification.status = ValidationStatus.PASS
                    l.verification.confidence_score = ai_data.get("confidence", 0.95)
                    l.verification.review_flags.append("AI Verified: True")
                    
                    # Active Edits
                    if ai_data.get("corrected_name"):
                        l.raw_attributes["corrected_name"] = ai_data["corrected_name"]
                        l.title = f"{l.title} [{ai_data['corrected_name']}]"
                        corrections.append({"id": i, "field": "name", "new_val": ai_data["corrected_name"]})
                        
                    if ai_data.get("corrected_vram"):
                        l.raw_attributes["vram"] = ai_data["corrected_vram"]
                        corrections.append({"id": i, "field": "vram", "new_val": ai_data["corrected_vram"]})
                        
                    if ai_data.get("listing_type") == "COMPLETE_PC":
                        l.raw_attributes["is_complete_pc"] = True
                        
                    passed_count += 1
                    verified.append(l)
                elif ai_data is None:
                    # Graceful fallback: LLM was unavailable / failed to return results
                    # Preserve candidate if heuristic filter didn't explicitly reject with 0 confidence
                    if l.verification and l.verification.status != ValidationStatus.REJECT:
                        l.verification.review_flags.append("LLM_UNAVAILABLE: Heuristic Fallback")
                        passed_count += 1
                        verified.append(l)
                    elif l.verification and l.verification.confidence_score >= 0.50:
                        l.verification.status = ValidationStatus.REVIEW
                        l.verification.review_flags.append("LLM_UNAVAILABLE: Heuristic Fallback")
                        passed_count += 1
                        verified.append(l)
                    else:
                        l.verification.status = ValidationStatus.REJECT
                        l.verification.rejection_reasons = ["LLM unavailable and heuristic rejection"]
                        rejected_count += 1
                else:
                    reason = ai_data.get("reason", "AI Rejection")
                    l.verification.status = ValidationStatus.REJECT
                    l.verification.rejection_reasons = [f"AI: {reason}"]
                    l.verification.confidence_score = 0.0
                    rejected_count += 1
                    rejection_breakdown[f"AI: {reason}"] = rejection_breakdown.get(f"AI: {reason}", 0) + 1
                    rejections.append({"id": i, "reason": reason})

            self.session_logger.log_llm_verification(
                spec.name, len(escalation_candidates), corrections, rejections
            )

        self.session_logger.log_tier1_filter(
            spec.name,
            total_checked=len(raw_listings),
            passed=passed_count,
            reviewed=len(escalation_candidates),
            rejected=rejected_count,
            rejection_breakdown=rejection_breakdown
        )
        
        logger.info(f"[{spec.name}] Verified {len(raw_listings)} listings. Passed: {passed_count}, Rejected: {rejected_count}.")
        return spec.name, verified

    def _search_and_evaluate_complete_pcs(self):
        """
        Searches for Complete Gaming PCs featuring the user's primary GPU or CPU,
        decomposes them into a structured BOM, and calculates Arbitrage vs loose parts.
        """
        with self.perf_timer.measure("LLM-Aufrufe & BOM-Extraktion"):
            # Find anchor component (GPU preferred, CPU secondary)
            anchor_comp = next((s for s in self.specs if s.type == ComponentType.GPU), None)
            if not anchor_comp:
                anchor_comp = next((s for s in self.specs if s.type == ComponentType.CPU), None)
            if not anchor_comp:
                return

            # Strip brand prefixes for realistic marketplace titles (e.g. 'Gaming PC RTX 3070')
            clean_anchor = " ".join([t for t in anchor_comp.name.split() if t.upper() not in self.BRAND_PREFIXES])
            pc_queries = [f"Gaming PC {clean_anchor}"]
            logger.info(f"Executing Dual-Track Search for Complete PCs with queries: {pc_queries}")
            
            raw_pcs = []
            seen_urls = set()
            for q in pc_queries:
                for p in self.scraper.search(q):
                    if p.url not in seen_urls:
                        seen_urls.add(p.url)
                        raw_pcs.append(p)
            
            # Identify defect / scam characteristics or intent mismatches
            valid_pcs = []
            for p in raw_pcs:
                title_upper = (p.title or "").upper()
                
                # 1. Reine Intent-Mismatches (SUCHE, TAUSCH, KAUFE) - skip
                if any(re.search(rf'\b{kw}\b', title_upper) for kw in ["SUCHE", "GESUCH", "KAUFE", "TAUSCH", "TAUSCHE"]):
                    continue

                # 2. Defect Detection - do not drop silently, tag with is_scam_suspected
                attrs = AttributeExtractor.extract_attributes(p.title, p.description)
                if attrs.get('defect') or any(kw in title_upper for kw in ["DEFEKT", "BASTLER", "ERSATZTEIL"]):
                    p.is_scam_suspected = True
                    p.scam_reason = "Defekt / Bastlerware / Ersatzteilspender"
                    if p not in self.build_listings:
                        self.build_listings.append(p)
                    self.session_logger.log_scam_suspect("COMPLETE_PC", p.title, p.price, p.url, p.scam_reason)
                    continue

                # 3. Box / Missing core components
                if attrs.get('box_or_parts_only'):
                    p.is_scam_suspected = True
                    p.scam_reason = "Verdacht auf OVP / Leerkarton / Fehlende Kernkomponente"
                    if p not in self.build_listings:
                        self.build_listings.append(p)
                    self.session_logger.log_scam_suspect("COMPLETE_PC", p.title, p.price, p.url, p.scam_reason)
                    continue

                # 4. Fake placeholder <= 5€
                if p.is_fake_placeholder or (p.price is not None and 0.0 < p.price <= 5.0):
                    p.is_scam_suspected = True
                    p.scam_reason = "Scheinpreis / Fake-Platzhalter (<= 5€)"
                    if p not in self.build_listings:
                        self.build_listings.append(p)
                    self.session_logger.log_scam_suspect("COMPLETE_PC", p.title, p.price, p.url, p.scam_reason)
                    continue

                # Plausible PC prices for full BOM evaluation
                if p.price and p.price > 100.0:
                    valid_pcs.append(p)
            
            def _pc_teaser_score(pc_item):
                score = 100.0
                t_lower = (pc_item.title or "").lower()
                anchor_tokens = [tok.lower() for tok in anchor_comp.name.split() if tok.upper() not in self.BRAND_PREFIXES]
                match_count = sum(1 for tok in anchor_tokens if tok in t_lower)
                score += match_count * 20.0
                if getattr(pc_item, 'has_buyer_protection', False):
                    score += 15.0
                if getattr(pc_item, 'shipping_available', False):
                    score += 10.0
                if getattr(pc_item, 'is_vb', False):
                    score += 5.0
                if pc_item.price:
                    if 250.0 <= pc_item.price <= 900.0:
                        score += 25.0
                    elif pc_item.price > 1800.0:
                        score -= 20.0
                return score

            # Pre-select Top-3 to Top-4 most promising complete PCs to conserve traffic & prevent sequential hangs
            promising_pcs = sorted(valid_pcs, key=_pc_teaser_score, reverse=True)[:3]
            
            for pc in promising_pcs:
                try:
                    # Enrich with full multi-paragraph description and trust flags from detail page
                    self.scraper.fetch_detail_page(pc)

                    # Check if enriched description reveals defect or box-only
                    full_attrs = AttributeExtractor.extract_attributes(pc.title, pc.description)
                    if full_attrs.get('defect'):
                        pc.is_scam_suspected = True
                        pc.scam_reason = "Defekt / Bastlerware / Ersatzteilspender"
                        if pc not in self.build_listings:
                            self.build_listings.append(pc)
                        self.session_logger.log_scam_suspect("COMPLETE_PC", pc.title, pc.price, pc.url, pc.scam_reason)
                        continue
                    if full_attrs.get('box_or_parts_only'):
                        pc.is_scam_suspected = True
                        pc.scam_reason = "Verdacht auf OVP / Leerkarton / Fehlende Kernkomponente"
                        if pc not in self.build_listings:
                            self.build_listings.append(pc)
                        self.session_logger.log_scam_suspect("COMPLETE_PC", pc.title, pc.price, pc.url, pc.scam_reason)
                        continue

                    bom_res = self.pc_parser_agent.extract_bom(pc.title, pc.description)
                    if not bom_res.get("is_complete_pc", False):
                        continue
                        
                    components = bom_res.get("components", {})
                    
                    # If searching for a GPU PC, ensure a GPU is actually present in the BOM
                    if anchor_comp.type == ComponentType.GPU:
                        gpu_val = components.get("GPU") or components.get("gpu")
                        if not gpu_val or any(neg in str(gpu_val).lower() for neg in ["none", "null", "keine", "ohne", "nicht", "beispiel", "separat", "fehlt"]):
                            logger.info(f"Skipping PC '{pc.title}': No valid GPU present in BOM for GPU search.")
                            pc.is_scam_suspected = True
                            pc.scam_reason = "Verdacht auf OVP / Leerkarton / Fehlende Kernkomponente"
                            if pc not in self.build_listings:
                                self.build_listings.append(pc)
                            self.session_logger.log_scam_suspect("COMPLETE_PC", pc.title, pc.price, pc.url, pc.scam_reason)
                            continue

                    component_value = 0.0
                    
                    # Estimate individual part value from catalog or market baselines
                    for comp_type, part_name in components.items():
                        if not part_name:
                            continue
                        part_str = str(part_name).strip()
                        part_lower = part_str.lower()
                        if part_lower in ["none", "null", "keine", "ohne", "nicht enthalten", "fehlt", "n/a", "entfällt"]:
                            continue
                        if any(neg in part_lower for neg in ["keine", "ohne", "nicht im lieferumfang", "beispielbild", "nur beispiel", "nicht enthalten", "separat verkauft"]):
                            continue

                        cat_item = self.catalog.find_item(part_str)
                        if cat_item:
                            component_value += cat_item.used_price_fair
                        else:
                            # Baseline fallback estimates
                            ctype_upper = str(comp_type).upper()
                            if "GPU" in ctype_upper: component_value += 200.0
                            elif "CPU" in ctype_upper: component_value += 120.0
                            elif "RAM" in ctype_upper: component_value += 40.0
                            elif "MOTHERBOARD" in ctype_upper or "MAINBOARD" in ctype_upper: component_value += 65.0
                            elif "STORAGE" in ctype_upper or "SSD" in ctype_upper: component_value += 45.0
                            elif "PSU" in ctype_upper: component_value += 40.0
                            else: component_value += 30.0

                    # Single-shipment savings: 5 shipments avoided * 7€ = 35€
                    shipping_savings = 35.0
                    total_loose_parts_cost = component_value + shipping_savings
                    arbitrage_savings = round(total_loose_parts_cost - pc.price, 2)
                    
                    pc.bom = bom_res
                    pc.arbitrage_savings = arbitrage_savings
                    self.build_listings.append(pc)
                    
                    self.session_logger.log_bom_extraction(
                        pc.title, pc.price, pc.is_vb, bom_res, component_value, arbitrage_savings
                    )
                    logger.info(f"Complete PC Evaluated: '{pc.title[:40]}' - Price: {pc.price}€, Arbitrage Savings: {arbitrage_savings}€")
                    
                except Exception as e:
                    logger.error(f"Error evaluating complete PC '{pc.title}': {e}")


    def run_scenario(self, user_input: str) -> Dict[str, Any]:
        """Convenience method for CLI & testing."""
        self.process_user_intent(user_input)
        report = self.run_market_scan()
        return {
            "success": True,
            "session_id": self.session_logger.session_id,
            "session_log_file": str(self.session_logger.log_file),
            "results": {k: len(v) for k, v in self.listings_map.items()},
            "alternatives": report.get("alternatives_found", {}),
            "complete_pc_deals": report.get("complete_pc_deals", []),
            "ai_build_plan": report.get("ai_build_plan", {})
        }

if __name__ == "__main__":
    orch = HardwareOrchestrator()
    print("Testing Orchestrator...")
    res = orch.run_scenario("Ryzen 5 3600")
    print("Result:", res)
