import json
import os
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

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
    """
    
    DEFAULT_LOG_DIR = Path("logs/sessions")

    def __init__(self, session_id: Optional[str] = None, log_dir: Optional[Path] = None):
        self.session_id = session_id or f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{self.session_id}.jsonl"
        self.events: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

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

    def log_session_complete(self, summary: Dict[str, Any]):
        self.log_event("session_complete", summary)

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
