import pytest
from hardware_crawler.deal_checker import (
    DealChecker, MultiLineAdParser, detect_deal_check_intent, PriceAssessment
)
from hardware_crawler.logging_session import SessionLogger

def test_detect_deal_check_intent():
    # 1. Pasted ad with specs and price
    pasted_ad = (
        "Verkaufe Gaming PC:\n"
        "- Ryzen 7 5800X3D\n"
        "- RTX 3080 10GB\n"
        "- 32GB RAM DDR4\n"
        "Preis: 850 € VB"
    )
    is_deal, price, is_vb, conf, mode = detect_deal_check_intent(pasted_ad)
    assert is_deal is True
    assert mode == "DEAL_CHECK_PASTE"
    assert price == 850.0
    assert is_vb is True
    assert conf >= 0.90

    # 2. Simple search query should NOT be classified as deal check
    search_query = "RTX 3070"
    is_deal_search, price_search, _, _, mode_search = detect_deal_check_intent(search_query)
    assert is_deal_search is False
    assert mode_search in ["SINGLE_SEARCH", "PARTIAL_SEARCH"]

    # 3. Two parts query
    dual_query = "Ryzen 5800X3D + B550"
    is_deal_dual, _, _, _, _ = detect_deal_check_intent(dual_query)
    assert is_deal_dual is False

def test_multiline_ad_parser_forensic_case():
    """
    Forensic Re-Test of Session sess_20261108_122052_2abad8.jsonl:
    Ensures all 8 lines are cleanly resolved into 8 structured components with 0ms catalog lookup,
    without query-stitching and without dropping Motherboard, RAM, SSD, Cooler, Case.
    """
    forensic_text = (
        "- Mainboard Asus Strix B450-F Gaming\n"
        "- RAM 32GB DDR4 Corsair Vengeance LPX 3200Mhz CL16\n"
        "- CPU AMD Ryzen 7 5800X3D\n"
        "- CPU Kühler BeQuiet Dark Rock Pro 4 mit PTM7950 Wärmeleitpaste (Top Performance, kein Austrocknen für viele Jahre)\n"
        "- GPU ASUS TUF RTX 3080 10GB - PTM7950 Wärmeleitpaste + VRAM Wärmeleitpads mit Thermal Putty getauscht. 3D gedrucktes Shroud in schwarz. Das originale Shroud habe ich verkauft, da ich die Karte mit Deshroud und Noctua Lüftern betrieben habe.\n"
        "- SSD 1TB NVMe Sandisk Extreme Pro\n"
        "- Gehäuse BeQuiet Pure Base 500 mit Glas Seitenteil und Mesh+Dämmungs Top Panel\n"
        "- Netzteil Seasonic Focus GX 650W"
    )

    parser = MultiLineAdParser()
    components, unrecognized, parsed_price, is_vb = parser.parse_ad_text(forensic_text)

    # All 8 components must be extracted
    assert len(components) == 8, f"Expected 8 components, got {len(components)}: {[c.canonical_name for c in components]}"

    categories = [c.category for c in components]
    assert "MOTHERBOARD" in categories
    assert "RAM" in categories
    assert "CPU" in categories
    assert "COOLER" in categories
    assert "GPU" in categories
    assert "STORAGE" in categories
    assert "CASE" in categories
    assert "PSU" in categories

    # Verify no query concatenation
    for c in components:
        # Check that none of the components contain foreign component tokens stitched from other lines
        if c.category == "CPU":
            assert "Dark Rock" not in c.canonical_name
            assert "3080" not in c.canonical_name
        elif c.category == "GPU":
            assert "Ryzen" not in c.canonical_name
            assert "SSD" not in c.canonical_name
        elif c.category == "PSU":
            assert "Seasonic" in c.raw_name or "650W" in c.canonical_name

def test_deal_checker_valuations(tmp_path):
    """Verifies TOP_DEAL, FAIR_DEAL, and OVERPRICED assessment boundaries."""
    ad_specs = (
        "- CPU AMD Ryzen 7 5800X3D\n"
        "- GPU NVIDIA GeForce RTX 3080 10GB\n"
        "- RAM 32GB DDR4 RAM\n"
        "- Netzteil 650W Power Supply"
    )
    # Market value sum is approx: 240 + 400 + 52.5 + 47.5 = 740 EUR

    checker = DealChecker()
    session_logger = SessionLogger(session_id="test_deal_eval", log_dir=tmp_path)

    # 1. TOP_DEAL: Asking price 500€ for ~740€ parts -> savings 240€ (>= 150€)
    res_top = checker.evaluate_ad(ad_specs, seller_asking_price=500.0, is_vb=True, session_logger=session_logger)
    assert res_top.assessment == PriceAssessment.TOP_DEAL
    assert res_top.arbitrage_savings >= 150.0
    assert "Top Deal" in res_top.assessment_headline

    # 2. FAIR_DEAL: Asking price 720€ for ~740€ parts -> savings 20€
    res_fair = checker.evaluate_ad(ad_specs, seller_asking_price=720.0, is_vb=True, session_logger=session_logger)
    assert res_fair.assessment == PriceAssessment.FAIR_DEAL
    assert -50.0 <= res_fair.arbitrage_savings < 150.0
    assert "Fairer Gebrauchtpreis" in res_fair.assessment_headline

    # 3. OVERPRICED: Asking price 900€ for ~740€ parts -> savings -160€ (< -50€)
    res_over = checker.evaluate_ad(ad_specs, seller_asking_price=900.0, is_vb=False, session_logger=session_logger)
    assert res_over.assessment == PriceAssessment.OVERPRICED
    assert res_over.arbitrage_savings < -50.0
    assert "Zu teuer" in res_over.assessment_headline

    # Verify event was logged in JSONL
    events = SessionLogger.read_session_events(session_logger.log_file)
    eval_events = [e for e in events if e.get("event_type") == "deal_check_evaluated"]
    assert len(eval_events) == 3

def test_deal_checker_negotiation_strategy():
    """Verifies generation of polite German negotiation message."""
    ad_specs = (
        "- CPU AMD Ryzen 7 5800X3D\n"
        "- GPU ASUS TUF RTX 3080 10GB\n"
        "- RAM 32GB DDR4\n"
        "- Mainboard B450"
    )
    checker = DealChecker()
    res = checker.evaluate_ad(ad_specs, seller_asking_price=850.0, is_vb=True)

    neg = res.negotiation
    assert neg is not None
    assert 650.0 <= neg.target_offer_price <= 800.0
    assert neg.suggested_discount_pct > 0
    assert "Hallo, ich habe Interesse" in neg.chat_message_german
    assert "vor Ort abholen" in neg.chat_message_german
    assert "bar bezahlen" in neg.chat_message_german
