import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from hardware_crawler.orchestrator import HardwareOrchestrator
from hardware_crawler.models import Listing, ValidationStatus
from hardware_crawler.logging_session import SessionLogger

def test_orchestrator_catalog_fastpath():
    orch = HardwareOrchestrator()
    # Process "RTX 3070" - should be found in HardwareCatalog
    names = orch.process_user_intent("RTX 3070")
    assert len(orch.specs) >= 1
    spec = orch.specs[0]
    assert "RTX 3070" in spec.name
    assert spec.data_card is not None
    assert "gaming_score" in spec.data_card["specs"]
    assert spec.data_card["specs"]["gaming_score"] >= 45
    assert spec.expected_attributes.get("vram") == [8]

def test_orchestrator_3tier_funnel_and_logging(tmp_path):
    orch = HardwareOrchestrator()
    orch.session_logger = SessionLogger(session_id="test_funnel_sess", log_dir=tmp_path)
    orch.process_user_intent("RTX 3070")
    spec = orch.specs[0]

    # Mock scraper returning:
    # 1. Clean listing (280€ VB) -> Instant PASS
    # 2. Fake VB listing (1€ VB) -> Tier 1 REJECT
    # 3. Ambiguous listing -> Tier 2 Escalation
    clean_listing = Listing(
        title="MSI RTX 3070 Ventus 8GB",
        price=280.0,
        url="https://kleinanzeigen.de/ad1",
        description="Top Zustand.",
        is_vb=True
    )
    fake_vb_listing = Listing(
        title="RTX 3070",
        price=1.0,
        url="https://kleinanzeigen.de/ad2",
        description="Macht Angebote",
        is_vb=True,
        is_fake_placeholder=True
    )
    ambiguous_listing = Listing(
        title="Gaming PC RTX 3070",
        price=320.0,
        url="https://kleinanzeigen.de/ad3",
        description="Grafikkarte RTX 3070 aus Gaming PC ausgebaut."
    )

    orch.scraper.search_for_spec = MagicMock(return_value=[clean_listing, fake_vb_listing, ambiguous_listing])
    
    # Mock LLM verification agent for ambiguous item (active edit)
    orch.verification_agent.verify_listings_batch = MagicMock(return_value={
        "0": {
            "is_valid": True,
            "confidence": 0.95,
            "reason": "GPU was extracted from PC, card is sold individually",
            "corrected_name": "NVIDIA GeForce RTX 3070",
            "corrected_vram": 8,
            "listing_type": "SINGLE_PART"
        }
    })

    _, verified = orch._search_and_verify(spec)
    
    # Check that clean listing, corrected ambiguous listing, and scam suspect (preserved) are in verified
    assert len(verified) == 3
    assert any(l.url == "https://kleinanzeigen.de/ad1" for l in verified)
    
    # Check that fake VB listing is retained as SCAM_SUSPECT
    scam_item = next(l for l in verified if l.url == "https://kleinanzeigen.de/ad2")
    assert scam_item.verification.status == ValidationStatus.SCAM_SUSPECT
    assert scam_item.is_scam_suspected is True

    # Check active edit on ambiguous listing
    edited = next(l for l in verified if l.url == "https://kleinanzeigen.de/ad3")
    assert edited.raw_attributes.get("corrected_name") == "NVIDIA GeForce RTX 3070"
    assert edited.raw_attributes.get("vram") == 8
    assert "AI Verified: True" in edited.verification.review_flags

    # Check session log file content
    events = SessionLogger.read_session_events(orch.session_logger.log_file)
    event_types = [e["event_type"] for e in events]
    assert "session_start" in event_types
    assert "raw_scrape" in event_types
    assert "scam_suspect_detected" in event_types
    assert "llm_verification" in event_types
    assert "tier1_filter" in event_types

def test_orchestrator_complete_pc_arbitrage(tmp_path):
    orch = HardwareOrchestrator()
    orch.session_logger = SessionLogger(session_id="test_pc_sess", log_dir=tmp_path)
    orch.process_user_intent("RTX 3070")

    mock_pc = Listing(
        title="Gaming PC RTX 3070 Ryzen 5600X",
        price=600.0,
        url="https://kleinanzeigen.de/pc1",
        description="Kompletter PC mit RTX 3070, Ryzen 5 5600X, 16GB DDR4, 1TB SSD, 650W PSU.",
        is_vb=True
    )
    orch.scraper.search = MagicMock(return_value=[mock_pc])
    
    # Mock BOM Parser Agent
    orch.pc_parser_agent.extract_bom = MagicMock(return_value={
        "is_complete_pc": True,
        "components": {
            "GPU": "NVIDIA GeForce RTX 3070",
            "CPU": "AMD Ryzen 5 5600X",
            "RAM": "16GB DDR4",
            "STORAGE": "1TB SSD",
            "PSU": "650W"
        }
    })

    orch._search_and_evaluate_complete_pcs()

    assert len(orch.build_listings) == 1
    evaluated_pc = orch.build_listings[0]
    assert evaluated_pc.bom is not None
    # Component value: RTX 3070 (~290€) + Ryzen 5600X (~105€) + RAM (35€) + SSD (45€) + PSU (40€) + shipping savings (35€) = ~550€
    # Arbitrage savings = component value - 600€
    assert isinstance(evaluated_pc.arbitrage_savings, float)
    
    # Session log check
    events = SessionLogger.read_session_events(orch.session_logger.log_file)
    bom_events = [e for e in events if e["event_type"] == "bom_extraction"]
    assert len(bom_events) == 1
    assert bom_events[0]["data"]["price"] == 600.0
    assert bom_events[0]["data"]["is_vb"] is True
