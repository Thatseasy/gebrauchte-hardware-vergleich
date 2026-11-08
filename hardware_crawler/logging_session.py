import json
import os
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

class TrafficMonitor:
    """
    Thread-safe network traffic & telemetry monitor:
    - Counts HTTP requests & data volume (KB)
    - Records HTTP status codes (200, 429, 403, 504, ConnectionReset)
    - Records cache hits (e.g. 0ms catalog lookup)
    - Records LLM calls & estimated token consumption
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.total_requests = 0
        self.bytes_transferred = 0
        self.status_codes: Dict[str, int] = {}
        self.cache_hits = 0
        self.llm_calls = 0
        self.llm_tokens_estimated = 0
        self.request_latencies: List[float] = []

    def record_request(self, url: str, status_code: int, response_size_bytes: int = 0, latency_s: float = 0.0):
        with self.lock:
            self.total_requests += 1
            self.bytes_transferred += max(0, response_size_bytes)
            code_key = str(status_code)
            self.status_codes[code_key] = self.status_codes.get(code_key, 0) + 1
            if latency_s > 0:
                self.request_latencies.append(latency_s)

    def record_connection_error(self, error_type: str = "ConnectionReset"):
        with self.lock:
            self.total_requests += 1
            self.status_codes[error_type] = self.status_codes.get(error_type, 0) + 1

    def record_cache_hit(self):
        with self.lock:
            self.cache_hits += 1

    def record_llm_call(self, tokens: int = 0):
        with self.lock:
            self.llm_calls += 1
            self.llm_tokens_estimated += tokens

    def get_summary(self) -> Dict[str, Any]:
        with self.lock:
            kb = round(self.bytes_transferred / 1024.0, 2)
            avg_latency = round(sum(self.request_latencies) / len(self.request_latencies), 3) if self.request_latencies else 0.0
            return {
                "total_requests": self.total_requests,
                "data_volume_kb": kb,
                "status_codes": dict(self.status_codes),
                "cache_hits": self.cache_hits,
                "llm_calls": self.llm_calls,
                "llm_tokens_estimated": self.llm_tokens_estimated,
                "avg_latency_s": avg_latency
            }

    def reset(self):
        with self.lock:
            self.total_requests = 0
            self.bytes_transferred = 0
            self.status_codes.clear()
            self.cache_hits = 0
            self.llm_calls = 0
            self.llm_tokens_estimated = 0
            self.request_latencies.clear()

class PerformanceTimer:
    """
    Precise performance timer for tracking durations across pipeline phases:
    - Intent Parsing & Katalog-Lookup
    - Kleinanzeigen Markt-Scraping (Einzelteile + Komplett-PCs)
    - Verifikation & Scam-Filterung
    - LLM-Aufrufe & BOM-Extraktion
    - Gesamtdauer des Scans
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.phase_starts: Dict[str, float] = {}
        self.durations: Dict[str, float] = {}
        self.start_time: float = time.time()

    def start_phase(self, phase_name: str):
        with self.lock:
            self.phase_starts[phase_name] = time.perf_counter()

    def stop_phase(self, phase_name: str) -> float:
        with self.lock:
            start = self.phase_starts.pop(phase_name, None)
            if start is not None:
                duration = time.perf_counter() - start
                self.durations[phase_name] = self.durations.get(phase_name, 0.0) + duration
                return duration
            return 0.0

    @contextmanager
    def measure(self, phase_name: str):
        self.start_phase(phase_name)
        try:
            yield
        finally:
            self.stop_phase(phase_name)

    def get_summary(self) -> Dict[str, Any]:
        with self.lock:
            total_elapsed = time.time() - self.start_time
            durations_ms = {k: round(v * 1000, 1) for k, v in self.durations.items()}
            durations_s = {k: round(v, 2) for k, v in self.durations.items()}
            return {
                "total_duration_s": round(total_elapsed, 2),
                "durations_s": durations_s,
                "durations_ms": durations_ms
            }

    def reset(self):
        with self.lock:
            self.phase_starts.clear()
            self.durations.clear()
            self.start_time = time.time()

class SessionLogger:
    """
    Structured JSONL session logger for the Kleinanzeigen Gaming-PC Crawler.
    Provides complete audit trails for:
    - Raw scraped listings
    - 4-tier VB pricing classifications
    - Script heuristic filtering (Tier 1)
    - Active LLM verification & edits (Tier 2)
    - Complete PC BOM extractions and Arbitrage calculations
    - Final suggested builds
    - Telemetry & performance metrics
    """
    
    DEFAULT_LOG_DIR = Path("logs/sessions")

    def __init__(self, session_id: Optional[str] = None, log_dir: Optional[Path] = None):
        self.session_id = session_id or f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{self.session_id}.jsonl"
        self.events: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.traffic_monitor = TrafficMonitor()
        self.performance_timer = PerformanceTimer()

    def log_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Appends a structured event to the session JSONL log."""
        record = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        with self.lock:
            self.events.append(record)
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as e:
                # Fallback print if file writing fails
                print(f"[SessionLogger Error] Could not write event {event_type}: {e}")
        return record

    def log_session_start(self, user_query: str, config: Optional[Dict[str, Any]] = None):
        self.log_event("session_start", {
            "user_query": user_query,
            "config": config or {}
        })

    def log_intent(self, user_query: str, parsed_specs: List[Dict[str, Any]]):
        self.log_event("intent_parsed", {
            "user_query": user_query,
            "spec_count": len(parsed_specs),
            "specs": parsed_specs
        })

    def log_raw_scrape(self, target: str, query: str, raw_count: int, listings_sample: List[Dict[str, Any]]):
        self.log_event("raw_scrape", {
            "target": target,
            "query": query,
            "raw_count": raw_count,
            "sample": listings_sample[:5]
        })

    def log_tier1_filter(self, target: str, total_checked: int, passed: int, reviewed: int, rejected: int, rejection_breakdown: Dict[str, int]):
        self.log_event("tier1_filter", {
            "target": target,
            "total_checked": total_checked,
            "passed": passed,
            "reviewed": reviewed,
            "rejected": rejected,
            "rejection_breakdown": rejection_breakdown
        })

    def log_llm_verification(self, target: str, batch_size: int, corrections: List[Dict[str, Any]], rejections: List[Dict[str, Any]]):
        self.log_event("llm_verification", {
            "target": target,
            "batch_size": batch_size,
            "corrected_count": len(corrections),
            "rejected_count": len(rejections),
            "corrections": corrections,
            "rejections": rejections
        })

    def log_bom_extraction(self, listing_title: str, price: float, is_vb: bool, bom: Dict[str, Any], component_value: float, arbitrage_savings: float):
        self.log_event("bom_extraction", {
            "listing_title": listing_title,
            "price": price,
            "is_vb": is_vb,
            "bom": bom,
            "component_value": component_value,
            "arbitrage_savings": arbitrage_savings
        })

    def log_scam_suspect(self, target: str, title: str, price: Optional[float], url: str, reason: Optional[str]):
        self.log_event("scam_suspect_detected", {
            "target": target,
            "title": title,
            "price": price,
            "url": url,
            "scam_reason": reason
        })

    def log_build_generated(self, build_data: Dict[str, Any]):
        self.log_event("build_generated", build_data)

    def log_intent_type_detected(
        self,
        raw_input_preview: str,
        line_count: int,
        detected_mode: str,
        mode_confidence: float,
        detected_seller_price: Optional[float],
        is_vb: bool,
        extracted_components_count: int,
        unrecognized_lines: List[str],
        latency_ms: float
    ):
        """Logs classification of user input into search vs paste-to-evaluate deal-check."""
        return self.log_event("intent_type_detected", {
            "raw_input_preview": (raw_input_preview or "")[:150],
            "line_count": line_count,
            "detected_mode": detected_mode,
            "mode_confidence": round(mode_confidence, 2),
            "detected_seller_price": detected_seller_price,
            "is_vb": is_vb,
            "extracted_components_count": extracted_components_count,
            "unrecognized_lines": unrecognized_lines,
            "latency_ms": round(latency_ms, 2)
        })

    def log_deal_check_evaluated(
        self,
        seller_asking_price: float,
        is_vb: bool,
        total_part_market_value: float,
        arbitrage_savings: float,
        savings_percent: float,
        price_assessment: str,
        components: List[Dict[str, Any]],
        negotiation_target_price: Optional[float] = None
    ):
        """Logs valuation of a complete pasted ad against catalog market prices."""
        return self.log_event("deal_check_evaluated", {
            "seller_asking_price": seller_asking_price,
            "is_vb": is_vb,
            "total_part_market_value": round(total_part_market_value, 2),
            "arbitrage_savings": round(arbitrage_savings, 2),
            "savings_percent": round(savings_percent, 1),
            "price_assessment": price_assessment,
            "components": components,
            "negotiation_target_price": negotiation_target_price
        })

    def log_hardware_plausibility_rejected(
        self,
        rejected_listing_title: str,
        component_type: str,
        listing_price: Optional[float],
        rule_violated: str,
        actual_wattage: Optional[int],
        required_wattage: int,
        rejection_reason: str,
        build_context: Optional[Dict[str, Any]] = None,
        recommended_wattage: Optional[int] = None
    ):
        """Logs strict rejection of an underpowered or hazardous component prior to price sorting."""
        return self.log_event("hardware_plausibility_rejected", {
            "rejected_listing_title": rejected_listing_title,
            "component_type": component_type,
            "listing_price": listing_price,
            "rule_violated": rule_violated,
            "actual_wattage": actual_wattage,
            "required_wattage": required_wattage,
            "recommended_wattage": recommended_wattage or int(required_wattage * 1.15),
            "build_context": build_context or {},
            "rejection_reason": rejection_reason
        })

    def log_bundle_slot_satisfied(
        self,
        bundle_listing_id: str,
        bundle_title: str,
        bundle_price: float,
        satisfied_slots: List[str],
        separate_slots_cost: float,
        bundle_savings: float
    ):
        """Logs multi-slot fulfillment by a hardware bundle to prevent redundant part purchases."""
        return self.log_event("bundle_slot_satisfied", {
            "bundle_listing_id": bundle_listing_id,
            "bundle_title": bundle_title,
            "bundle_price": bundle_price,
            "satisfied_slots": satisfied_slots,
            "separate_slots_cost": round(separate_slots_cost, 2),
            "bundle_savings": round(bundle_savings, 2)
        })

    def log_ready_to_play_gap_filled(
        self,
        base_components_price: float,
        shipping_cost_total: float,
        missing_slots: List[str],
        standard_fillers: List[Dict[str, Any]],
        gap_fillers_total: float,
        true_ready_to_play_price: float
    ):
        """Logs standard pricing for missing case, cooler, or storage plus shipping overhead."""
        return self.log_event("ready_to_play_gap_filled", {
            "base_components_price": round(base_components_price, 2),
            "shipping_cost_total": round(shipping_cost_total, 2),
            "missing_slots": missing_slots,
            "standard_fillers": standard_fillers,
            "gap_fillers_total": round(gap_fillers_total, 2),
            "true_ready_to_play_price": round(true_ready_to_play_price, 2)
        })

    def log_telemetry_summary(self, summary_data: Optional[Dict[str, Any]] = None):
        """Logs summary telemetry at the conclusion of a session."""
        data = summary_data or {
            "traffic": self.traffic_monitor.get_summary(),
            "performance": self.performance_timer.get_summary()
        }
        return self.log_event("telemetry_summary", data)

    def log_session_complete(self, summary: Dict[str, Any]):
        if "telemetry" not in summary:
            summary["telemetry"] = {
                "traffic": self.traffic_monitor.get_summary(),
                "performance": self.performance_timer.get_summary()
            }
        return self.log_event("session_complete", summary)

    @classmethod
    def get_latest_session_log(cls, log_dir: Optional[Path] = None) -> Optional[Path]:
        """Returns the most recent session log file if available."""
        target_dir = log_dir or cls.DEFAULT_LOG_DIR
        if not target_dir.exists():
            return None
        logs = list(target_dir.glob("*.jsonl"))
        if not logs:
            return None
        return max(logs, key=os.path.getmtime)

    @classmethod
    def read_session_events(cls, log_path: Path) -> List[Dict[str, Any]]:
        """Reads all JSONL records from a given log file."""
        events = []
        if not log_path.exists():
            return events
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass
        return events
