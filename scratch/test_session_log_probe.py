import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from hardware_crawler.logging_session import SessionLogger

def test_corrupt_session_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_session.jsonl"
        
        # Write test lines:
        lines = [
            '{"session_id": "s1", "timestamp": "2026-11-08T07:00:00.000000", "event_type": "valid_event", "data": {"key": "val"}}\n',
            'CORRUPT_NOT_JSON{{{\n', # Syntax error
            '{"session_id": "s1", "timestamp": null, "event_type": "null_timestamp", "data": {}}\n', # timestamp is None!
            '{"session_id": "s1", "timestamp": 12345678, "event_type": "numeric_timestamp", "data": {}}\n', # timestamp is int!
            '{"session_id": "s1", "timestamp": "short", "event_type": "short_timestamp", "data": {}}\n', # timestamp too short (<19 chars)!
            'null\n', # json.loads("null") -> None
            '{"session_id": "s1", "timestamp": "2026-11-08T07:05:00.000000", "event_type": "missing_data"}\n', # missing "data"
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        print("Reading session events with SessionLogger.read_session_events:")
        events = SessionLogger.read_session_events(log_file)
        print(f"Read {len(events)} events out of {len(lines)} lines.")
        
        # Now simulate how app.py lines 120-123 render them:
        print("\nSimulating app.py rendering loop:")
        for idx, ev in enumerate(events):
            print(f"Rendering event {idx}: {ev}")
            try:
                # This is what app.py line 121 does:
                expander_title = f"⏱️ {ev.get('timestamp', '')[11:19]} — {ev.get('event_type')}"
                event_data = ev.get("data", {})
                print(f"  Expander title: {expander_title!r}")
            except Exception as e:
                print(f"  CRASH in app.py render loop at event {idx}: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_corrupt_session_log()
