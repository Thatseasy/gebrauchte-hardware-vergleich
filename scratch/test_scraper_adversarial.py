"""
Adversarial QA Test Suite for Hardware Crawler
Focus: scrapers.py (KleinanzeigenScraper) & verification.py (VerificationEngine, AttributeExtractor)

Run via:
    uv run python scratch/test_scraper_adversarial.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import logging
from typing import Dict, Any, List, Tuple
from unittest.mock import MagicMock
import requests

from hardware_crawler.models import Listing, CanonicalSpec, ComponentType, ValidationStatus
from hardware_crawler.scrapers import KleinanzeigenScraper
from hardware_crawler.verification import VerificationEngine, AttributeExtractor

logging.basicConfig(level=logging.WARNING)

class TestReporter:
    def __init__(self):
        self.results = []
        self.vulnerabilities = []

    def log_case(self, category: str, test_name: str, input_val: Any, expected: Any, actual: Any, is_flaw: bool, severity: str, details: str):
        self.results.append({
            "category": category,
            "test_name": test_name,
            "input": input_val,
            "expected": expected,
            "actual": actual,
            "is_flaw": is_flaw,
            "severity": severity,
            "details": details
        })
        if is_flaw:
            self.vulnerabilities.append({
                "category": category,
                "test_name": test_name,
                "severity": severity,
                "details": details,
                "input": input_val,
                "actual": actual,
                "expected": expected
            })

    def print_summary(self):
        total = len(self.results)
        flaws = len(self.vulnerabilities)
        print("\n" + "=" * 80)
        print(f"ADVERSARIAL QA TEST RESULTS: {total} tests executed, {flaws} flaws/vulnerabilities identified.")
        print("=" * 80)

        by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
        for v in self.vulnerabilities:
            by_severity.get(v["severity"], by_severity["INFO"]).append(v)

        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            items = by_severity[sev]
            if not items:
                continue
            print(f"\n[{sev}] ({len(items)} issues):")
            for item in items:
                print(f"  * [{item['category']}] {item['test_name']}: {item['details']}")
                print(f"      Input:    {repr(item['input'])}")
                print(f"      Actual:   {repr(item['actual'])}")
                print(f"      Expected: {repr(item['expected'])}")

    def generate_markdown_report(self, filepath: str):
        total = len(self.results)
        flaws = len(self.vulnerabilities)
        by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
        for v in self.vulnerabilities:
            by_severity.get(v["severity"], by_severity["INFO"]).append(v)

        lines = [
            "# Adversarial QA Test Report: Scraping, Pricing & Verification",
            "",
            f"**Total Tests Run:** {total}  ",
            f"**Total Flaws / Vulnerabilities Identified:** {flaws}  ",
            f"- **CRITICAL:** {len(by_severity['CRITICAL'])}  ",
            f"- **HIGH:** {len(by_severity['HIGH'])}  ",
            f"- **MEDIUM:** {len(by_severity['MEDIUM'])}  ",
            f"- **LOW:** {len(by_severity['LOW'])}  ",
            "",
            "---",
            ""
        ]

        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            items = by_severity[sev]
            if not items:
                continue
            lines.append(f"## {sev} Severity Issues ({len(items)})")
            lines.append("")
            for idx, item in enumerate(items, 1):
                lines.append(f"### {idx}. [{item['category']}] {item['test_name']}")
                lines.append(f"- **Description:** {item['details']}")
                lines.append(f"- **Input:** `{repr(item['input'])}`")
                lines.append(f"- **Actual Behavior:** `{repr(item['actual'])}`")
                lines.append(f"- **Expected Behavior:** `{repr(item['expected'])}`")
                lines.append("")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nDetailed markdown report written to: {filepath}")



reporter = TestReporter()

# ==============================================================================
# SECTION 1: KleinanzeigenScraper.parse_price_info()
# ==============================================================================
def test_pricing_adversarial():
    print("\n--- Running Section 1: parse_price_info Adversarial Tests ---")

    # 1.1 Cents & Decimal Separators
    cases_decimals = [
        # (input_str, expected_price, expected_vb, expected_neg, expected_fake, desc, severity)
        ("1.250,50 € VB", 1250.50, True, False, False, "German format with thousands dot and decimal comma + VB", "HIGH"),
        ("1250,50 €", 1250.50, False, False, False, "German decimal comma without thousands separator", "HIGH"),
        ("12,50 €", 12.50, False, False, False, "German decimal comma lower amount", "HIGH"),
        ("12.50 €", 12.50, False, False, False, "Dot used as decimal point (English/code style: 12.50 €)", "HIGH"),
        ("1,250.50 €", 1250.50, False, False, False, "US/English format (comma thousands, dot decimal)", "MEDIUM"),
        ("1,250 €", 1250.0, False, False, False, "US comma thousands separator without decimals", "MEDIUM"),
        ("0,50 €", 0.50, False, False, True, "50 cents (low price, should be fake)", "LOW"),
        ("5,01 €", 5.01, False, False, False, "Just above 5.0 threshold", "LOW"),
        ("5,00 €", 5.00, False, False, True, "Exactly at 5.0 threshold", "LOW"),
        ("300,- €", 300.0, False, False, False, "German standard shorthand 300,- €", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_decimals:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p != exp_p or is_vb != exp_vb or needs_neg != exp_neg or is_fake != exp_fake)
            details = desc
            if p != exp_p:
                details += f" -> Numeric mismatch: got {p} instead of {exp_p}"
            reporter.log_case("PRICING_DECIMALS", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_DECIMALS", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "CRITICAL", f"Crashed on input: {e}")

    # 1.2 VB Syntax Variations
    cases_vb = [
        ("Preis: VB 250 €", 250.0, True, False, False, "Prefix VB before price", "MEDIUM"),
        ("250 € (VB)", 250.0, True, False, False, "VB in parentheses", "MEDIUM"),
        ("250 Euro VHB", 250.0, True, False, False, "VHB (Verhandlungsbasis) with 'Euro'", "HIGH"),
        ("VB: 200€", 200.0, True, False, False, "VB with colon prefix, no space before €", "MEDIUM"),
        ("250 € Verhandlungsbasis", 250.0, True, False, False, "Full German word 'Verhandlungsbasis'", "MEDIUM"),
        ("250 € V.B.", 250.0, True, False, False, "Dotted abbreviation 'V.B.'", "MEDIUM"),
        ("Preis VHB", 0.0, True, True, False, "Pure VHB without number", "HIGH"),
        ("VHB", 0.0, True, True, False, "Single word VHB", "HIGH"),
        ("Vb", 0.0, True, True, False, "Mixed case 'Vb' alone", "LOW"),
        ("vb", 0.0, True, True, False, "Lowercase 'vb' alone", "LOW"),
        ("300€ Vb", 300.0, True, False, False, "Mixed case 'Vb' with price", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_vb:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p != exp_p or is_vb != exp_vb or needs_neg != exp_neg or is_fake != exp_fake)
            details = desc
            if is_vb != exp_vb:
                details += f" -> VB flag mismatch: got is_vb={is_vb}"
            if needs_neg != exp_neg:
                details += f" -> needs_negotiation mismatch: got {needs_neg}"
            reporter.log_case("PRICING_VB_SYNTAX", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_VB_SYNTAX", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "CRITICAL", f"Crashed on input: {e}")

    # 1.3 Zero price & Free Giveaways ("Zu verschenken")
    cases_free = [
        ("0 €", 0.0, False, False, False, "0 € free listing (Is it fake or genuine giveaway?)", "HIGH"),
        ("0,00 €", 0.0, False, False, False, "0,00 € free listing", "HIGH"),
        ("Zu verschenken", 0.0, False, False, False, "Official Kleinanzeigen 'Zu verschenken' badge", "HIGH"),
        ("Kostenlos", 0.0, False, False, False, "Word 'Kostenlos'", "MEDIUM"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_free:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            # In current implementation, <= 5 is always is_fake=True. But is 'Zu verschenken' really a fake placeholder scam?
            is_flaw = is_fake  # If marked as fake placeholder, it will be discarded by verification as scam
            details = f"{desc}: parsed as price={p}, is_fake={is_fake} (Discarded by verification engine as scam if is_fake=True)"
            reporter.log_case("PRICING_FREE_ITEMS", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_FREE_ITEMS", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "CRITICAL", f"Crashed on input: {e}")

    # 1.4 Hidden Unicode & HTML Entities
    cases_unicode = [
        ("\u200b250 €", 250.0, False, False, False, "Zero-width space \u200b", "MEDIUM"),
        ("&#8203; 250 €", 250.0, False, False, False, "HTML entity &#8203; with semicolon", "HIGH"),
        ("&nbsp;250 €", 250.0, False, False, False, "Raw HTML entity &nbsp;", "HIGH"),
        ("\u00a0250 €", 250.0, False, False, False, "Non-breaking space \u00a0 prefix", "MEDIUM"),
        ("\u202f250 €", 250.0, False, False, False, "Narrow non-breaking space \u202f prefix", "MEDIUM"),
        ("1\u00a0250 €", 1250.0, False, False, False, "Non-breaking space \u00a0 as thousands separator", "CRITICAL"),
        ("1\u202f250 €", 1250.0, False, False, False, "Narrow non-breaking space \u202f as thousands separator", "CRITICAL"),
        ("1 250 €", 1250.0, False, False, False, "Regular space as thousands separator", "CRITICAL"),
        ("1&nbsp;250 €", 1250.0, False, False, False, "Raw &nbsp; as thousands separator", "CRITICAL"),
        ("\ufeff250 €", 250.0, False, False, False, "BOM / zero-width no-break space \ufeff", "LOW"),
        ("\u200e250 €", 250.0, False, False, False, "Left-to-right mark \u200e", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_unicode:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p != exp_p or is_fake != exp_fake)
            details = f"{desc}: parsed as {actual}"
            reporter.log_case("PRICING_UNICODE", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_UNICODE", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "HIGH", f"Crashed on input: {e}")

    # 1.5 Multiple prices in text & Ambiguities
    cases_multi = [
        ("UVP 600€, jetzt 300€ VB", 300.0, True, False, False, "UVP first, current price second", "LOW"),
        ("300€ VB (NP: 600€)", 300.0, True, False, False, "Current price first, original price (NP: 600€) in parentheses", "CRITICAL"),
        ("300 € VB (ehem. 500 €)", 300.0, True, False, False, "Current price first, former price (ehem. 500 €) second", "CRITICAL"),
        ("250 € VB (zzgl. 6,99 € Versand)", 250.0, True, False, False, "Price with shipping fee at end", "CRITICAL"),
        ("250 € VB (zzgl. 4,99 € Versand)", 250.0, True, False, False, "Price with shipping <= 5€ at end (triggers fake placeholder!)", "CRITICAL"),
        ("500 € 420 € VB", 420.0, True, False, False, "Strikethrough / reduced price: 500 € reduced to 420 €", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_multi:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p != exp_p or is_fake != exp_fake)
            details = f"{desc}: parsed {p} € (expected {exp_p} €)"
            if is_fake != exp_fake:
                details += f", is_fake={is_fake} (expected {exp_fake})"
            reporter.log_case("PRICING_MULTI_PRICES", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_MULTI_PRICES", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "CRITICAL", f"Crashed on input: {e}")

    # 1.6 Compact text without spaces
    cases_compact = [
        ("300€VB", 300.0, True, False, False, "No space between price and VB", "LOW"),
        ("300€VHB", 300.0, True, False, False, "No space with VHB", "HIGH"),
        ("VB300€", 300.0, True, False, False, "VB directly preceding price without space", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_compact:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p != exp_p or is_vb != exp_vb)
            details = f"{desc}: parsed {actual}"
            reporter.log_case("PRICING_COMPACT", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_COMPACT", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "HIGH", f"Crashed on input: {e}")

    # 1.7 Malformed & Edge Inputs
    cases_malformed = [
        ("", 0.0, False, False, True, "Empty string", "LOW"),
        ("   ", 0.0, False, False, True, "Whitespace only", "LOW"),
        ("-10 €", 0.0, False, False, True, "Negative price (regex strips minus sign!)", "HIGH"),
        ("Tausche gegen PS5", 0.0, False, False, True, "Trade offer with no price", "LOW"),
    ]

    for price_str, exp_p, exp_vb, exp_neg, exp_fake, desc, sev in cases_malformed:
        try:
            p, is_vb, needs_neg, is_fake = KleinanzeigenScraper.parse_price_info(price_str)
            actual = (p, is_vb, needs_neg, is_fake)
            expected = (exp_p, exp_vb, exp_neg, exp_fake)
            is_flaw = (p < 0 or (price_str == "-10 €" and p == 10.0))
            details = f"{desc}: parsed as {actual}"
            if price_str == "-10 €" and p == 10.0:
                details += " -> Negative sign lost: -10 € parsed as +10.0 €!"
            reporter.log_case("PRICING_MALFORMED", desc, price_str, expected, actual, is_flaw, sev, details)
        except Exception as e:
            reporter.log_case("PRICING_MALFORMED", desc, price_str, (exp_p, exp_vb, exp_neg, exp_fake), f"CRASH: {e}", True, "HIGH", f"Crashed on input: {e}")

    # Crash check on None
    try:
        KleinanzeigenScraper.parse_price_info(None)  # type: ignore
        reporter.log_case("PRICING_CRASH", "None input", None, "Graceful handle", "No crash", False, "LOW", "Handled None")
    except Exception as e:
        reporter.log_case("PRICING_CRASH", "None input", None, "Graceful handle", f"CRASH: {type(e).__name__}: {e}", True, "HIGH", f"Passing None crashes parse_price_info: {e}")


# ==============================================================================
# SECTION 2: KleinanzeigenScraper.fetch_detail_page()
# ==============================================================================
def test_fetch_detail_page_adversarial():
    print("\n--- Running Section 2: fetch_detail_page Adversarial Tests ---")
    scraper = KleinanzeigenScraper()

    # 2.1 HTTP Errors & Timeouts
    http_error_codes = [
        (404, "HTTP 404 Not Found"),
        (403, "HTTP 403 Forbidden (Cloudflare block)"),
        (500, "HTTP 500 Internal Server Error"),
        (502, "HTTP 502 Bad Gateway"),
        (503, "HTTP 503 Service Unavailable"),
    ]

    for status_code, desc in http_error_codes:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        scraper.scraper.get = MagicMock(return_value=mock_resp)

        listing = Listing(
            title="GPU",
            price=200.0,
            url="https://www.kleinanzeigen.de/s-anzeige/gpu/123",
            description="Initial teaser"
        )
        res = scraper.fetch_detail_page(listing)
        is_flaw = (res is not False)
        details = f"Returns False on {desc}"
        reporter.log_case("HTTP_ERRORS", desc, status_code, False, res, is_flaw, "LOW", details)

    # 2.1b Network Exceptions
    network_exceptions = [
        (requests.exceptions.Timeout("Connection timed out after 10s"), "Timeout Exception"),
        (requests.exceptions.ConnectionError("Failed to establish a connection"), "ConnectionError"),
        (requests.exceptions.ChunkedEncodingError("Incomplete response stream"), "ChunkedEncodingError"),
    ]

    for exc, desc in network_exceptions:
        scraper.scraper.get = MagicMock(side_effect=exc)
        listing = Listing(
            title="GPU",
            price=200.0,
            url="https://www.kleinanzeigen.de/s-anzeige/gpu/123",
            description="Initial teaser"
        )
        try:
            res = scraper.fetch_detail_page(listing)
            is_flaw = (res is not False)
            reporter.log_case("NETWORK_EXCEPTIONS", desc, type(exc).__name__, False, res, is_flaw, "LOW", f"Handled exception: {desc}")
        except Exception as e:
            reporter.log_case("NETWORK_EXCEPTIONS", desc, type(exc).__name__, False, f"CRASH: {e}", True, "CRITICAL", f"Unhandled exception: {e}")

    # 2.1c Invalid URLs
    invalid_urls = [
        (None, "None URL"),
        ("", "Empty URL"),
        ("ftp://invalid.com", "Non-HTTP URL"),
        ("javascript:void(0)", "Javascript scheme URL"),
    ]
    for url, desc in invalid_urls:
        listing = Listing(title="GPU", price=200.0, url=url, description="Initial")
        res = scraper.fetch_detail_page(listing)
        is_flaw = (res is not False)
        reporter.log_case("INVALID_URLS", desc, url, False, res, is_flaw, "LOW", f"Returned {res} for invalid URL {url}")

    # 2.2 Missing Description Element
    html_no_desc = """
    <html>
        <body>
            <div class="ad-content">
                <h1>RTX 3070</h1>
                <!-- Modern Tailwind container without #viewad-description-text or itemprop -->
                <div class="description-body">
                    Hier ist die echte Beschreibung im neuen Frontend!
                </div>
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_no_desc
    scraper.scraper.get = MagicMock(return_value=mock_resp)

    listing_missing_desc = Listing(
        title="RTX 3070",
        price=250.0,
        url="https://www.kleinanzeigen.de/s-anzeige/123",
        description="Short teaser"
    )
    ok = scraper.fetch_detail_page(listing_missing_desc)
    # The method returns True, but description was NOT updated!
    desc_updated = ("echte Beschreibung" in listing_missing_desc.description)
    reporter.log_case(
        "DOM_SELECTORS",
        "Missing legacy description ID (#viewad-description-text)",
        html_no_desc,
        "Description enriched from new class/container",
        listing_missing_desc.description,
        not desc_updated,
        "MEDIUM",
        "When page lacks #viewad-description-text / itemprop=description, description is silently NOT updated even though fetch_detail_page returns True."
    )

    # 2.3 False Positives in "Direkt kaufen" and "Versand möglich"
    html_adversarial_text = """
    <html>
        <body>
            <p id="viewad-description-text">
                Verkaufe meine RTX 3070.
                ACHTUNG: Ich biete KEIN Direkt kaufen und KEIN Sicher bezahlen an!
                Nur Barzahlung bei Abholung. Definitiv KEIN Versand möglich! Anfragen nach Versand werden ignoriert.
            </p>
            <div class="footer">
                Tipps: Bei Kleinanzeigen sicher handeln.
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_adversarial_text
    scraper.scraper.get = MagicMock(return_value=mock_resp)

    listing_false_positives = Listing(
        title="RTX 3070",
        price=250.0,
        url="https://www.kleinanzeigen.de/s-anzeige/123",
        description="",
        has_buyer_protection=False,
        shipping_available=False
    )
    scraper.fetch_detail_page(listing_false_positives)

    has_bp_flaw = listing_false_positives.has_buyer_protection is True
    reporter.log_case(
        "DETECTION_FALSE_POSITIVES",
        "Buyer Protection False Positive ('KEIN Direkt kaufen')",
        "ACHTUNG: Ich biete KEIN Direkt kaufen an!",
        False,
        listing_false_positives.has_buyer_protection,
        has_bp_flaw,
        "HIGH",
        "page_text check 'Direkt kaufen' in page_text triggers False Positive when seller explicitly says 'KEIN Direkt kaufen'!"
    )

    shipping_flaw = listing_false_positives.shipping_available is True
    reporter.log_case(
        "DETECTION_FALSE_POSITIVES",
        "Shipping Available False Positive ('KEIN Versand möglich')",
        "Definitiv KEIN Versand möglich!",
        False,
        listing_false_positives.shipping_available,
        shipping_flaw,
        "HIGH",
        "page_text check 'Versand möglich' in page_text triggers False Positive when seller says 'KEIN Versand möglich'!"
    )

    # 2.4 False Negatives in "Direkt kaufen" and "Versand möglich"
    # Case variations & badge formats used on Kleinanzeigen
    html_official_badges = """
    <html>
        <body>
            <p id="viewad-description-text">Verkaufe RTX 3070</p>
            <!-- Official OPP / Kleinanzeigen action bar -->
            <div class="action-box">
                <button class="btn-buy-now">Direktkauf</button>
                <span class="shipping-info">Versand ab 5,49 € mit DHL</span>
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_official_badges
    scraper.scraper.get = MagicMock(return_value=mock_resp)

    listing_false_negatives = Listing(
        title="RTX 3070",
        price=250.0,
        url="https://www.kleinanzeigen.de/s-anzeige/123",
        description="",
        has_buyer_protection=False,
        shipping_available=False
    )
    scraper.fetch_detail_page(listing_false_negatives)

    reporter.log_case(
        "DETECTION_FALSE_NEGATIVES",
        "Buyer Protection False Negative ('Direktkauf' button)",
        "button with 'Direktkauf'",
        True,
        listing_false_negatives.has_buyer_protection,
        listing_false_negatives.has_buyer_protection is False,
        "MEDIUM",
        "'Direktkauf' is not matched by 'Direkt kaufen' or 'Sicher bezahlen'"
    )

    reporter.log_case(
        "DETECTION_FALSE_NEGATIVES",
        "Shipping Available False Negative ('Versand ab 5,49 €')",
        "span with 'Versand ab 5,49 € mit DHL'",
        True,
        listing_false_negatives.shipping_available,
        listing_false_negatives.shipping_available is False,
        "MEDIUM",
        "'Versand ab 5,49 €' is not matched because code strictly looks for 'Versand möglich' in detail page (unlike search which checked '+ Versand')"
    )


# ==============================================================================
# SECTION 3: verification.py (AttributeExtractor & VerificationEngine)
# ==============================================================================
def test_verification_adversarial():
    print("\n--- Running Section 3: verification.py Adversarial Tests ---")

    spec_3070 = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )

    # 3.1 Negated Search/Trade Keywords (False Positive Search Rejection)
    title_kein_tausch = "MSI RTX 3070 Ventus 8GB - Festpreis, kein Tausch!"
    listing_kein_tausch = Listing(
        title=title_kein_tausch,
        price=280.0,
        url="https://kleinanzeigen.de/s-10",
        description="Fester Preis. Bitte keine Tauschanfragen."
    )
    res_tausch = VerificationEngine.verify(listing_kein_tausch, spec_3070)
    is_flaw_tausch = (res_tausch.status == ValidationStatus.REJECT and "Search Request" in str(res_tausch.rejection_reasons))
    reporter.log_case(
        "VERIFICATION_FALSE_REJECTION",
        "Negated trade keyword ('kein Tausch!')",
        title_kein_tausch,
        "PASS or REVIEW (Valid sale)",
        res_tausch.status.value,
        is_flaw_tausch,
        "CRITICAL",
        f"Legitimate sale listing rejected as search request because 'TAUSCH' matches in 'kein Tausch!': {res_tausch.rejection_reasons}"
    )

    title_suche_besitzer = "RTX 3070 sucht neuen Besitzer"
    listing_suche_besitzer = Listing(
        title=title_suche_besitzer,
        price=270.0,
        url="https://kleinanzeigen.de/s-11",
        description="Wegen Neuanschaffung abzugeben."
    )
    # Note: 'sucht' vs 'suche'
    attrs_besitzer = AttributeExtractor.extract_attributes(title_suche_besitzer, "")
    reporter.log_case(
        "VERIFICATION_SEARCH_REGEX",
        "Word boundary on 'sucht' vs 'suche'",
        title_suche_besitzer,
        False,
        attrs_besitzer.get("is_search_request", False),
        attrs_besitzer.get("is_search_request", False) is True,
        "LOW",
        f"Checks if 'sucht' falsely triggers 'suche': {attrs_besitzer.get('is_search_request', False)}"
    )

    # 3.2 Negated Defect Keywords (False Positive Defect Rejection)
    title_kein_defekt = "RTX 3070 Gaming - Nicht defekt, funktioniert 100%"
    listing_kein_defekt = Listing(
        title=title_kein_defekt,
        price=290.0,
        url="https://kleinanzeigen.de/s-12",
        description="Gebraucht, aber kein Bastlerteil, keine Defekte."
    )
    res_defekt = VerificationEngine.verify(listing_kein_defekt, spec_3070)
    is_flaw_defekt = (res_defekt.status == ValidationStatus.REJECT and "defective" in str(res_defekt.rejection_reasons))
    reporter.log_case(
        "VERIFICATION_FALSE_REJECTION",
        "Negated defect ('Nicht defekt, kein Bastlerteil')",
        title_kein_defekt,
        "PASS (Fully functional)",
        res_defekt.status.value,
        is_flaw_defekt,
        "CRITICAL",
        f"Legitimate GPU rejected as defect because 'DEFEKT' or 'BASTLER' appeared in negated sentence: {res_defekt.rejection_reasons}"
    )

    # 3.3 Box-Only / Scam Bypass (False Negative - Scam NOT detected!)
    # Scammer puts normal title, puts 'Nur OVP / Leerkarton' in description
    title_scam = "NVIDIA GeForce RTX 3070 Founders Edition 8GB Top"
    desc_scam = "Achtung: Sie bieten hier NUR auf die OVP (Leerkarton) ohne Grafikkarte!"
    listing_scam = Listing(
        title=title_scam,
        price=250.0,
        url="https://kleinanzeigen.de/s-13",
        description=desc_scam
    )
    res_scam = VerificationEngine.verify(listing_scam, spec_3070)
    # AttributeExtractor line 71: only checks in title_upper!
    is_flaw_scam = (res_scam.status == ValidationStatus.PASS)
    reporter.log_case(
        "VERIFICATION_SCAM_BYPASS",
        "Box-only / Leerkarton scam hidden in description",
        desc_scam,
        "REJECT (Box only scam)",
        res_scam.status.value,
        is_flaw_scam,
        "CRITICAL",
        f"Scammer hides 'NUR OVP (Leerkarton) ohne Grafikkarte' in description. AttributeExtractor only checks title! Verification result status: {res_scam.status.value}, confidence: {res_scam.confidence_score}"
    )

    # 3.4 VRAM vs System RAM Confusion
    # Title mentions GPU and System RAM (16GB)
    title_ram = "RTX 3070 Gaming PC 16 GB RAM i5 12400F"
    listing_ram = Listing(
        title=title_ram,
        price=550.0,
        url="https://kleinanzeigen.de/s-14",
        description="Top PC mit RTX 3070 8GB und 16 GB DDR4 RAM."
    )
    res_ram = VerificationEngine.verify(listing_ram, spec_3070)
    attrs_ram = AttributeExtractor.extract_attributes(title_ram, listing_ram.description)
    extracted_vram = attrs_ram.get("vram")
    # 16 is in [4, 6, 8, 10, 11, 12, 16, 20, 24], so regex in title picks 16GB RAM as VRAM!
    is_flaw_ram = (extracted_vram == 16 or any("VRAM Mismatch" in r for r in res_ram.rejection_reasons))
    reporter.log_case(
        "VERIFICATION_RAM_CONFUSION",
        "System RAM (16 GB RAM) misidentified as GPU VRAM",
        title_ram,
        "vram=8 (or unassigned), no mismatch",
        f"vram={extracted_vram}, reasons={res_ram.rejection_reasons}",
        is_flaw_ram,
        "HIGH",
        f"System RAM (16GB) in title matched as GPU VRAM, triggering VRAM Mismatch penalty for 8GB GPU!"
    )

    # 3.5 Negated Forbidden Tokens
    # Title has "RTX 3070 (keine Ti!)"
    title_keine_ti = "MSI RTX 3070 Ventus 8GB (keine Ti!)"
    listing_keine_ti = Listing(
        title=title_keine_ti,
        price=270.0,
        url="https://kleinanzeigen.de/s-15",
        description="Normale RTX 3070 Version, keine Ti."
    )
    res_keine_ti = VerificationEngine.verify(listing_keine_ti, spec_3070)
    is_flaw_ti = (res_keine_ti.status == ValidationStatus.REJECT and "Forbidden token" in str(res_keine_ti.rejection_reasons))
    reporter.log_case(
        "VERIFICATION_FORBIDDEN_TOKEN",
        "Negated forbidden token ('keine Ti!')",
        title_keine_ti,
        "PASS (It is a 3070)",
        res_keine_ti.status.value,
        is_flaw_ti,
        "HIGH",
        f"Listing clarifying '(keine Ti!)' rejected because forbidden token 'Ti' matches substring in title: {res_keine_ti.rejection_reasons}"
    )


if __name__ == "__main__":
    print("=" * 80)
    print("STARTING ADVERSARIAL QA SUITE FOR SCRAPING, PRICING & VERIFICATION")
    print("=" * 80)

    test_pricing_adversarial()
    test_fetch_detail_page_adversarial()
    test_verification_adversarial()

    reporter.print_summary()
    reporter.generate_markdown_report(os.path.join(os.path.dirname(__file__), "adversarial_test_report.md"))

