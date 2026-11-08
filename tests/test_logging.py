import json
from pathlib import Path
from hardware_crawler.logging_session import SessionLogger

def test_session_logger_lifecycle(tmp_path):
    logger = SessionLogger(session_id="test_session_123", log_dir=tmp_path)
    
    logger.log_session_start("Gaming PC RTX 3070")
    logger.log_tier1_filter("RTX 3070", total_checked=10, passed=7, reviewed=2, rejected=1, rejection_breakdown={"fake_vb": 1})
    logger.log_llm_verification("RTX 3070", batch_size=2, corrections=[{"id": 0, "corrected_vram": 8}], rejections=[])
    logger.log_bom_extraction(
        listing_title="Gaming PC RTX 3070",
        price=650.0,
        is_vb=True,
        bom={"cpu": "Ryzen 5 5600X", "gpu": "RTX 3070", "ram": "16GB DDR4"},
        component_value=820.0,
        arbitrage_savings=170.0
    )
    logger.log_session_complete({"status": "success", "deals_found": 5})

    assert logger.log_file.exists()
    events = SessionLogger.read_session_events(logger.log_file)
    assert len(events) == 5
    assert events[0]["event_type"] == "session_start"
    assert events[1]["event_type"] == "tier1_filter"
    assert events[2]["event_type"] == "llm_verification"
    assert events[3]["event_type"] == "bom_extraction"
    assert events[3]["data"]["arbitrage_savings"] == 170.0
    assert events[4]["event_type"] == "session_complete"
