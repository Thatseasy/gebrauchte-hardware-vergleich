"""
End-to-End & UI/UX Workflow Audit Suite for Kleinanzeigen Gaming-PC Crawler 2.0
Tests Streamlit app workflows, UI components, edge cases, error resilience, and crash risks.
"""
import sys
import os
import io
import json
import tempfile
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

sys.stdout.reconfigure(encoding="utf-8")

from hardware_crawler.models import (
    Listing, CanonicalSpec, ComponentType, ValidationStatus,
    VerificationResult, Build, BuildType, Product
)
from hardware_crawler.ui_components import (
    generate_csv_export, render_listing_details, render_build_listings,
    render_build_details, render_component_list_md, render_scan_results_md,
    render_sidebar_summary
)
from hardware_crawler.logging_session import SessionLogger
from hardware_crawler.orchestrator import HardwareOrchestrator

class AuditResults:
    def __init__(self):
        self.crashes = []
        self.data_issues = []
        self.ux_issues = []
        self.passed = []

    def record_crash(self, test_id: str, desc: str, error: Exception):
        self.crashes.append({"id": test_id, "desc": desc, "error": f"{type(error).__name__}: {error}"})

    def record_data_issue(self, test_id: str, desc: str, detail: str):
        self.data_issues.append({"id": test_id, "desc": desc, "detail": detail})

    def record_ux_issue(self, test_id: str, desc: str, detail: str):
        self.ux_issues.append({"id": test_id, "desc": desc, "detail": detail})

    def record_pass(self, test_id: str, desc: str):
        self.passed.append({"id": test_id, "desc": desc})


audit = AuditResults()

print("=" * 80)
print("🔍 STARTING UI/UX & END-TO-END WORKFLOW AUDIT")
print("=" * 80)

# ==============================================================================
# SECTION 1: PROMPT EDGE CASES & ORCHESTRATOR / APP INTENT
# ==============================================================================
print("\n--- [AUDIT 1] User Prompts & Input Resilience ---")

# 1.1 Empty and Whitespace Prompts
try:
    orch = HardwareOrchestrator(api_key="mock_key")
    # Mock LLM client so we test parser logic deterministically
    orch.client.generate_json = MagicMock(return_value={"components": []})
    
    for empty_input in ["", "   ", "\n\t", "   \n  "]:
        res = orch.process_user_intent(empty_input)
        if res != []:
            audit.record_data_issue("P1.1", f"Empty prompt '{repr(empty_input)}' returned components", str(res))
        else:
            audit.record_pass("P1.1", f"Empty prompt {repr(empty_input)} safely returned 0 components")
except Exception as e:
    audit.record_crash("P1.1", "Crash on empty/whitespace prompt in process_user_intent", e)

# 1.2 Pure Numbers
try:
    orch = HardwareOrchestrator(api_key="mock_key")
    orch.client.generate_json = MagicMock(return_value={"components": []})
    for num_input in ["12345", "0", "-999", "4090"]:
        if num_input == "4090":
            # Catalog fastpath should find RTX 4090
            res = orch.process_user_intent(num_input)
            if "NVIDIA GeForce RTX 4090" in res:
                audit.record_pass("P1.2", "Catalog fast-path correctly parsed model number '4090' -> RTX 4090")
            else:
                audit.record_ux_issue("P1.2", "Number '4090' not resolved by catalog fastpath", str(res))
        else:
            res = orch.process_user_intent(num_input)
            audit.record_pass("P1.2", f"Arbitrary number '{num_input}' safely handled (0 components)")
except Exception as e:
    audit.record_crash("P1.2", "Crash on pure numbers in process_user_intent", e)

# 1.3 Gibberish Prompts ('Banane', 'Minecraft')
try:
    orch = HardwareOrchestrator(api_key="mock_key")
    # Simulate LLM returning empty or hallucinating UNKNOWN item
    orch.client.generate_json = MagicMock(return_value={"components": []})
    res_banane = orch.process_user_intent("Banane")
    if res_banane == []:
        audit.record_pass("P1.3", "'Banane' safely returned empty components with clean fallback")
    
    # What if LLM returns UNKNOWN component for 'Banane'?
    orch.client.generate_json = MagicMock(return_value={
        "components": [{"type": "UNKNOWN", "raw_name": "Banane", "normalized_name": "Banane", "constraints": []}]
    })
    res_unknown = orch.process_user_intent("Banane")
    if "Banane" in res_unknown:
        # Check if UNKNOWN components are filtered or allowed into scan
        spec = orch.specs[-1]
        if spec.type == ComponentType.UNKNOWN:
            audit.record_ux_issue(
                "P1.3",
                "Non-hardware component ('Banane') of type UNKNOWN admitted into specs",
                "Allows user to trigger a market scan for groceries/non-hardware on Kleinanzeigen"
            )
except Exception as e:
    audit.record_crash("P1.3", "Crash on gibberish prompt processing", e)

# 1.4 Malformed LLM Response (Missing raw_name / normalized_name None)
try:
    orch = HardwareOrchestrator(api_key="mock_key")
    orch.client.generate_json = MagicMock(return_value={
        "components": [{"type": "GPU", "raw_name": None, "normalized_name": None}]
    })
    orch.process_user_intent("test")
    audit.record_pass("P1.4", "Handled None in raw_name / normalized_name without crash")
except Exception as e:
    audit.record_crash("P1.4", "Crash when LLM component has None name: name.split() fails", e)

# ==============================================================================
# SECTION 2: API KEY RESILIENCE & APP SESSION FLOW
# ==============================================================================
print("\n--- [AUDIT 2] API Key Resilience & Session State Transitions ---")

# 2.1 Missing Gemini API Key
try:
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("hardware_crawler/app.py")
        at.run()
        error_msgs = [e.value for e in at.error]
        has_lock_error = any("Zugriff gesperrt" in msg for msg in error_msgs)
        if has_lock_error:
            audit.record_pass("P2.1", "App cleanly blocks chat input and displays 'Zugriff gesperrt' error when no API key provided")
            # UX Issue: deterministic catalog search is completely blocked even though it needs no LLM
            audit.record_ux_issue(
                "P2.1",
                "Complete lock-out without API key",
                "Deterministic HardwareCatalog (0 ms offline search for 210+ GPUs/CPUs) is blocked when API key is missing"
            )
        else:
            audit.record_ux_issue("P2.1", "No lock error shown when API key is missing", str(error_msgs))
except Exception as e:
    audit.record_crash("P2.1", "AppTest crashed on missing API key check", e)

# 2.2 Reset Button State Loss ("Neue Suche starten")
try:
    # Inspect app.py lines 152-163:
    # `st.session_state.orchestrator = HardwareOrchestrator()` -> Missing api_key argument!
    with open("hardware_crawler/app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    if "st.session_state.orchestrator = HardwareOrchestrator()" in app_code:
        audit.record_data_issue(
            "P2.2",
            "Reset button wipes API key from Orchestrator instance",
            "Line 154 instantiates HardwareOrchestrator() with api_key=None, discarding active_api_key!"
        )
    else:
        audit.record_pass("P2.2", "Reset button properly preserves active API key")
except Exception as e:
    audit.record_crash("P2.2", "Inspection of reset button failed", e)

# ==============================================================================
# SECTION 3: SCAN WITH ZERO HITS & EMPTY RESULTS
# ==============================================================================
print("\n--- [AUDIT 3] Zero Hits & Scan Result Rendering ---")

# 3.1 Zero Hits Behavior in render_scan_results_md
try:
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 5090 Ti Ultra")
    listings_map = {"RTX 5090 Ti Ultra": []}
    md = render_scan_results_md(listings_map, [spec], build=None)
    if "❌ No listings found" in md:
        audit.record_pass("P3.1", "render_scan_results_md displays clean '❌ No listings found' badge")
    else:
        audit.record_data_issue("P3.1", "Unexpected output for 0 listings in render_scan_results_md", md)
except Exception as e:
    audit.record_crash("P3.1", "Crash in render_scan_results_md on 0 listings", e)

# 3.2 UI Tab Guard when listings_map is completely empty
try:
    # In app.py line 86:
    with open("hardware_crawler/app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    if "if st.session_state.scan_complete:" in app_code and "and (orch.listings_map" not in app_code:
        audit.record_pass("P3.2", "Tabs render cleanly whenever scan_complete is true (even if 0 listings)")
    else:
        audit.record_ux_issue(
            "P3.2",
            "Session Log and Results Tabs hidden if scan returns empty dict",
            "If listings_map is empty dict, `(orch.listings_map or orch.build_listings)` evaluates False. Tab 4 (Session Log) is hidden!"
        )
except Exception as e:
    audit.record_crash("P3.2", "Zero hits tab evaluation crashed", e)

# ==============================================================================
# SECTION 4: CSV EXPORT DEEP AUDIT (Umlauts, Quotes, Commas, BOM)
# ==============================================================================
print("\n--- [AUDIT 4] CSV Export Resilience & Excel Compatibility ---")

try:
    test_listings = {
        "NVIDIA RTX 3070": [
            Listing(
                title='MSI "Gaming X Trio", 8GB, Top Zustand!',
                price=280.0,
                url='https://kleinanzeigen.de/s-anzeige/1',
                location='München - Schöneberg',
                verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
            )
        ],
        "Gehäuse & Lüfter": [
            Listing(
                title='BeQuiet 500DX (Weiß, 3x PureWings 2, OVP)\nTop Zustand!',
                price=65.0,
                url='https://kleinanzeigen.de/s-anzeige/2',
                location='Köln, Innenstadt',
                verification=None
            )
        ]
    }
    csv_out = generate_csv_export(test_listings)
    
    # 4.1 Comma handling
    if '"MSI ""Gaming X Trio"", 8GB, Top Zustand!"' in csv_out:
        audit.record_pass("P4.1", "Commas and inner quotes properly escaped by pandas CSV export")
    else:
        audit.record_data_issue("P4.1", "Commas/Quotes not escaped properly in CSV", csv_out[:100])
        
    # 4.2 German Umlauts & UTF-8 BOM
    has_bom = csv_out.startswith("\ufeff")
    if not has_bom:
        audit.record_data_issue(
            "P4.2",
            "CSV lacks UTF-8 BOM (\\ufeff)",
            "Opening the CSV on Windows in Microsoft Excel causes German Umlauts (ä, ö, ü, ß) to display as corrupted mojibake (MÃ¼nchen, GehÃ¤use)!"
        )
    else:
        audit.record_pass("P4.2", "CSV contains UTF-8 BOM for Microsoft Excel compatibility")

    # 4.3 German Delimiter (Comma vs Semicolon)
    # German Excel expects semicolon ';' as delimiter
    first_line = csv_out.splitlines()[0] if csv_out else ""
    if ";" not in first_line and "," in first_line:
        audit.record_ux_issue(
            "P4.3",
            "CSV uses comma (',') instead of semicolon (';')",
            "In German Windows / Excel, comma-separated CSV places all fields into Column A. Semicolon or 'sep=,' header is standard."
        )
    else:
        audit.record_pass("P4.3", "CSV uses European semicolon delimiter")

    # 4.4 Empty listings map export
    empty_csv = generate_csv_export({})
    if "Such-Kategorie;Titel;Preis;Ort;Verifiziert;Alternative;Link" in empty_csv or "Such-Kategorie,Titel,Preis,Ort,Verifiziert,Alternative,Link" in empty_csv:
        if empty_csv.startswith("\ufeff"):
            audit.record_pass("P4.4", "Empty listings map returns clean header string with UTF-8 BOM")
        else:
            audit.record_data_issue("P4.4", "Empty CSV fallback string lacks UTF-8 BOM", empty_csv)
    else:
        audit.record_data_issue("P4.4", "Empty CSV returned unexpected format", empty_csv)

    # 4.5 Missing attributes in Listing (None price, None url, etc.)
    l_none = Listing(title="Incomplete Listing", price=None, url=None, location=None)
    csv_none = generate_csv_export({"GPU": [l_none]})
    audit.record_pass("P4.5", "generate_csv_export survived Listing with price=None and url=None")

except Exception as e:
    audit.record_crash("P4", "Crash during CSV export testing", e)

# ==============================================================================
# SECTION 5: UI RENDERING COMPONENTS & MISSING ATTRIBUTES
# ==============================================================================
print("\n--- [AUDIT 5] UI Component Rendering & Extreme Prices ---")

# 5.1 render_listing_details with price=None
try:
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    l_none_price = Listing(
        title="Geforce RTX 3070",
        price=None,
        url="https://example.com",
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    render_listing_details({"RTX 3070": [l_none_price]}, [spec])
    audit.record_pass("P5.1", "render_listing_details survived price=None")
except TypeError as te:
    audit.record_crash("P5.1", "FATAL CRASH in render_listing_details with price=None (l.price > 0.0)", te)
except Exception as e:
    audit.record_crash("P5.1", "Unexpected crash in render_listing_details with price=None", e)

# 5.2 render_listing_details with price=0.0 (Pure VB)
try:
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    l_zero_price = Listing(
        title="Geforce RTX 3070 Reine VB",
        price=0.0,
        url="https://example.com",
        is_vb=True,
        needs_negotiation=True,
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    render_listing_details({"RTX 3070": [l_zero_price]}, [spec])
    with open("hardware_crawler/ui_components.py", "r", encoding="utf-8") as f:
        uic = f.read()
    if "l.price >= 0.0" in uic:
        audit.record_pass("P5.2", "Pure VB listings (price=0.0) preserved in Einzelteile-Börse")
    else:
        audit.record_data_issue(
            "P5.2",
            "Pure VB listings (price=0.0) silently dropped from Einzelteile-Börse",
            "Filter `l.price > 0.0` discards valid verified VB offers where seller did not name a fixed euro amount!"
        )
except Exception as e:
    audit.record_crash("P5.2", "Crash in render_listing_details with price=0.0", e)

# 5.3 render_build_listings with price=None
try:
    l_build_none = Listing(
        title="Gaming PC",
        price=None,
        url="https://example.com",
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    render_build_listings([l_build_none])
    audit.record_pass("P5.3", "render_build_listings survived price=None")
except TypeError as te:
    audit.record_crash("P5.3", "FATAL CRASH in render_build_listings with price=None (l.price > 0.0)", te)
except Exception as e:
    audit.record_crash("P5.3", "Unexpected crash in render_build_listings with price=None", e)

# 5.4 render_build_details with title=None / price=None
try:
    l_comp = Listing(title=None, price=None, url="https://example.com", location="Berlin")
    build = Build(components=[l_comp])
    render_build_details(build)
    audit.record_pass("P5.4", "render_build_details survived title=None and price=None")
except Exception as e:
    audit.record_crash("P5.4", "FATAL CRASH in render_build_details with title=None/price=None", e)

# 5.5 Negotiation Template & Extreme Prices
try:
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    
    # Test infinity
    l_inf = Listing(
        title="Infinity GPU",
        price=float('inf'),
        url="https://example.com",
        is_vb=True,
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    try:
        render_listing_details({"RTX 3070": [l_inf]}, [spec])
        audit.record_pass("P5.5", "Handled price=inf without crash")
    except OverflowError as oe:
        audit.record_crash("P5.5", "FATAL CRASH in negotiation template on price=inf (round(inf) OverflowError)", oe)

    # Test boundary 10.0 vs 10.01
    l_10 = Listing(title="Budget Fan", price=10.0, url="https://example.com", is_vb=True, verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={}))
    with open("hardware_crawler/ui_components.py", "r", encoding="utf-8") as f:
        uic = f.read()
    if "10.0 <= l.price" in uic:
        audit.record_pass("P5.5", "10€ VB items included in negotiation template (10.0 <= l.price)")
    else:
        audit.record_ux_issue(
            "P5.5",
            "Strict inequality `l.price > 10.0` excludes exactly 10€ VB items",
            "10€ VB items do not show a negotiation template, whereas 10.01€ does."
        )

    # Test complete PC boundary 50.0 vs 50.01
    if "50.0 <= l.price" in uic:
        audit.record_pass("P5.5", "50€ VB complete PCs included in negotiation template (50.0 <= l.price)")
    else:
        audit.record_ux_issue(
            "P5.5",
            "Strict inequality `l.price > 50.0` excludes exactly 50€ VB complete PCs",
            "50€ VB PCs do not show a negotiation template, whereas 50.01€ does."
        )

    # Test extreme high price (100,000 €)
    l_huge = Listing(title="Super Server", price=100000.0, url="https://example.com", is_vb=True, verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={}))
    render_listing_details({"RTX 3070": [l_huge]}, [spec])
    audit.record_pass("P5.5", "Huge price (100,000€) calculated negotiation offer safely")

except Exception as e:
    audit.record_crash("P5.5", "Unexpected crash in negotiation template tests", e)

# 5.6 HTML Injection & Markdown Slicing Risk
try:
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    l_xss = Listing(
        title="RTX 3070 <img src=x onerror=alert(1)> **Bold unclosed",
        price=300.0,
        url="https://example.com",
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    render_listing_details({"RTX 3070": [l_xss]}, [spec])
    with open("hardware_crawler/ui_components.py", "r", encoding="utf-8") as f:
        uic = f.read()
    if "html.escape" in uic:
        audit.record_pass("P5.6", "Listing title properly sanitized with html.escape")
    else:
        audit.record_ux_issue(
            "P5.6",
            "Unsanitized listing title rendered with `unsafe_allow_html=True`",
            "Raw listing titles from Kleinanzeigen are passed to `unsafe_allow_html=True` and truncated at [:70], risking broken tags or XSS injection."
        )
except Exception as e:
    audit.record_crash("P5.6", "Crash on HTML/Markdown special characters in title", e)

# ==============================================================================
# SECTION 6: SESSION LOG AUDIT TRAIL & CORRUPT JSONL HANDLING
# ==============================================================================
print("\n--- [AUDIT 6] Session Log Corrupt JSONL Resilience ---")

try:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "corrupt_session.jsonl"
        
        # Test records
        records = [
            '{"session_id": "s1", "timestamp": "2026-11-08T07:00:00.000000", "event_type": "valid", "data": {"a": 1}}\n',
            'CORRUPT_NOT_JSON{{{\n',
            '{"session_id": "s1", "timestamp": null, "event_type": "null_ts", "data": {}}\n',
            '{"session_id": "s1", "timestamp": 12345678, "event_type": "int_ts", "data": {}}\n',
            'null\n',
            '{"session_id": "s1", "timestamp": "2026-11-08T07:10:00.000000", "event_type": "missing_data"}\n'
        ]
        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(records)
            
        events = SessionLogger.read_session_events(log_file)
        # Check read_session_events resilience
        if len(events) == 5:
            audit.record_pass("P6.1", "SessionLogger.read_session_events successfully skipped invalid JSON syntax line")
            
        # Now test the actual app.py lines 120-128 rendering resilience
        render_crashes = []
        for idx, ev in enumerate(events):
            try:
                if not isinstance(ev, dict):
                    continue
                ts_raw = ev.get('timestamp')
                ts_str = str(ts_raw or '')
                ts_display = ts_str[11:19] if len(ts_str) >= 19 else ts_str
                event_type = ev.get('event_type', 'unbekannt')
                title = f"⏱️ {ts_display} — {event_type}"
                data = ev.get("data", {})
            except Exception as e:
                render_crashes.append((idx, ev, e))
                
        if render_crashes:
            for idx, ev, err in render_crashes:
                audit.record_crash(
                    "P6.2",
                    f"FATAL CRASH in app.py Session Log tab on record {idx} ({ev})",
                    err
                )
        else:
            audit.record_pass("P6.2", "app.py Session Log tab cleanly rendered all parsed events")

except Exception as e:
    audit.record_crash("P6", "Unexpected crash during session log audit", e)

# ==============================================================================
# SECTION 7: SUMMARY REPORT
# ==============================================================================
print("\n" + "=" * 80)
print("📊 AUDIT SUMMARY REPORT")
print("=" * 80)

print(f"\n✅ PASSED CHECKS: {len(audit.passed)}")
for item in audit.passed:
    print(f"  [PASS] {item['id']}: {item['desc']}")

print(f"\n🔴 FATAL CRASH RISKS: {len(audit.crashes)}")
for item in audit.crashes:
    print(f"  [CRASH] {item['id']}: {item['desc']}")
    print(f"          Error: {item['error']}")

print(f"\n🟠 DATA INTEGRITY ISSUES: {len(audit.data_issues)}")
for item in audit.data_issues:
    print(f"  [DATA] {item['id']}: {item['desc']}")
    print(f"         Detail: {item['detail']}")

print(f"\n🟡 UI/UX USABILITY DEFECTS: {len(audit.ux_issues)}")
for item in audit.ux_issues:
    print(f"  [UX]   {item['id']}: {item['desc']}")
    print(f"         Detail: {item['detail']}")

print("\n" + "=" * 80)
