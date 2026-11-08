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
    assert "telemetry" in events[4]["data"]
    assert "traffic" in events[4]["data"]["telemetry"]
    assert "performance" in events[4]["data"]["telemetry"]

def test_traffic_monitor():
    from hardware_crawler.logging_session import TrafficMonitor
    tm = TrafficMonitor()
    
    tm.record_request("https://test.com/api", 200, response_size_bytes=2048, latency_s=0.25)
    tm.record_request("https://test.com/api/alt", 429, response_size_bytes=100, latency_s=0.10)
    tm.record_connection_error("ConnectionReset")
    tm.record_cache_hit()
    tm.record_cache_hit()
    tm.record_llm_call(tokens=150)
    
    summary = tm.get_summary()
    assert summary["total_requests"] == 3
    assert summary["data_volume_kb"] == 2.1
    assert summary["status_codes"]["200"] == 1
    assert summary["status_codes"]["429"] == 1
    assert summary["status_codes"]["ConnectionReset"] == 1
    assert summary["cache_hits"] == 2
    assert summary["llm_calls"] == 1
    assert summary["llm_tokens_estimated"] == 150
    assert summary["avg_latency_s"] > 0

def test_performance_timer():
    import time
    from hardware_crawler.logging_session import PerformanceTimer
    pt = PerformanceTimer()
    
    with pt.measure("Phase_A"):
        time.sleep(0.01)
        
    pt.start_phase("Phase_B")
    time.sleep(0.01)
    dur_b = pt.stop_phase("Phase_B")
    
    summary = pt.get_summary()
    assert summary["total_duration_s"] > 0
    assert "Phase_A" in summary["durations_s"]
    assert "Phase_B" in summary["durations_s"]
    assert summary["durations_ms"]["Phase_A"] > 0
    assert dur_b > 0
