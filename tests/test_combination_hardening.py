import pytest
from hardware_crawler.models import CanonicalSpec, ComponentType, Listing, ValidationStatus, VerificationResult
from hardware_crawler.analysis import CombinationEngine
from hardware_crawler.logging_session import SessionLogger

def test_hard_wattage_cutoff_blocks_400w_psu(tmp_path):
    """
    TICKET-03 Verification:
    Ensures an underpowered 400W PSU (10€) or 500W PSU is strictly blocked for an RTX 3080 (320W)
    + Ryzen 7 5800X3D (105W) setup, where min_wattage = 105 + 320 + 100 = 525W.
    """
    specs = [
        CanonicalSpec(name="AMD Ryzen 7 5800X3D", type=ComponentType.CPU),
        CanonicalSpec(name="NVIDIA GeForce RTX 3080 10GB", type=ComponentType.GPU),
        CanonicalSpec(name="650W Power Supply", type=ComponentType.PSU)
    ]

    pass_verif = VerificationResult(status=ValidationStatus.PASS, confidence_score=0.99, matched_attributes={})

    listings_map = {
        "AMD Ryzen 7 5800X3D": [
            Listing(title="AMD Ryzen 7 5800X3D CPU", price=220.0, url="http://test/cpu", verification=pass_verif)
        ],
        "NVIDIA GeForce RTX 3080 10GB": [
            Listing(title="ASUS TUF RTX 3080 10GB", price=420.0, url="http://test/gpu", verification=pass_verif)
        ],
        "650W Power Supply": [
            # 10€ 400W PSU (cheapest, but dangerous / physically underpowered!)
            Listing(title="HKC PC Netzteil 400W ATX Power Supply", price=10.0, url="http://test/psu400", verification=pass_verif),
            # 40€ 500W PSU (still below 525W cutoff)
            Listing(title="BeQuiet System Power 500W", price=40.0, url="http://test/psu500", verification=pass_verif),
            # 60€ 650W PSU (safe & sufficient)
            Listing(title="Seasonic Focus GX 650W Gold Netzteil", price=60.0, url="http://test/psu650", verification=pass_verif)
        ]
    }

    session_logger = SessionLogger(session_id="test_wattage_cutoff", log_dir=tmp_path)
    build = CombinationEngine.create_best_build(specs, listings_map, session_logger=session_logger)

    assert build is not None
    psu_chosen = next((c for c in build.components if c.product_match and c.product_match.type == ComponentType.PSU), None)
    assert psu_chosen is not None
    # 400W and 500W must be rejected; 650W must be chosen
    assert "650W" in psu_chosen.title
    assert psu_chosen.price == 60.0

    # Verify hardware_plausibility_rejected event was logged
    events = SessionLogger.read_session_events(session_logger.log_file)
    rejections = [e for e in events if e.get("event_type") == "hardware_plausibility_rejected"]
    assert len(rejections) >= 2
    titles_rejected = [r["data"]["rejected_listing_title"] for r in rejections]
    assert any("400W" in t for t in titles_rejected)
    assert any("500W" in t for t in titles_rejected)

def test_bundle_multi_slot_satisfaction(tmp_path):
    """
    TICKET-04 Verification:
    Ensures a bundle (CPU + MB + RAM for 290€) satisfies all 3 slots simultaneously,
    preventing duplicate purchases of Motherboard (110€) and RAM (55€).
    """
    specs = [
        CanonicalSpec(name="AMD Ryzen 7 5800X3D", type=ComponentType.CPU),
        CanonicalSpec(name="AMD B550 Motherboard", type=ComponentType.MOTHERBOARD),
        CanonicalSpec(name="32GB DDR4 RAM", type=ComponentType.RAM)
    ]

    pass_verif = VerificationResult(status=ValidationStatus.PASS, confidence_score=0.99, matched_attributes={})

    listings_map = {
        "AMD Ryzen 7 5800X3D": [
            # Bundle offering CPU + MB + RAM for 290€
            Listing(
                title="Bundle: AMD Ryzen 7 5800X3D + MSI B550 Gaming Plus + 32GB RAM DDR4",
                price=290.0,
                url="http://test/bundle290",
                description="Verkaufe mein Gaming Bundle bestehend aus Ryzen 5800X3D, B550 Mainboard und 32GB DDR4 RAM.",
                verification=pass_verif
            ),
            # Separate CPU for 220€
            Listing(title="AMD Ryzen 7 5800X3D", price=220.0, url="http://test/cpu", verification=pass_verif)
        ],
        "AMD B550 Motherboard": [
            Listing(title="MSI B550-A PRO Motherboard", price=110.0, url="http://test/mb", verification=pass_verif)
        ],
        "32GB DDR4 RAM": [
            Listing(title="Corsair Vengeance 32GB DDR4-3600 Kit", price=55.0, url="http://test/ram", verification=pass_verif)
        ]
    }
    # Separate parts sum = 220 + 110 + 55 = 385€
    # Bundle price = 290€ -> savings = 95€

    session_logger = SessionLogger(session_id="test_bundle_multi_slot", log_dir=tmp_path)
    build = CombinationEngine.create_best_build(specs, listings_map, session_logger=session_logger)

    assert build is not None
    # Only 1 listing (the bundle) should be purchased for these 3 slots!
    assert len(build.components) == 1
    assert build.components[0].price == 290.0
    assert build.total_price == 290.0
    assert build.bundle_savings_total == 95.0

    # Verify bundle_slot_satisfied event was logged
    events = SessionLogger.read_session_events(session_logger.log_file)
    bundle_events = [e for e in events if e.get("event_type") == "bundle_slot_satisfied"]
    assert len(bundle_events) == 1
    assert bundle_events[0]["data"]["bundle_savings"] == 95.0
    assert set(bundle_events[0]["data"]["satisfied_slots"]) == {"CPU", "MOTHERBOARD", "RAM"}

def test_ready_to_play_gap_filling(tmp_path):
    """
    TICKET-05 Verification:
    Ensures missing Case, Cooler, Storage are transparently priced (+50€, +30€, +55€)
    and 6.99€ shipping buffer is added per unique listing.
    """
    specs = [
        CanonicalSpec(name="AMD Ryzen 5 5600", type=ComponentType.CPU),
        CanonicalSpec(name="NVIDIA GeForce RTX 3060", type=ComponentType.GPU),
        CanonicalSpec(name="AMD B550 Motherboard", type=ComponentType.MOTHERBOARD),
        CanonicalSpec(name="500W Power Supply", type=ComponentType.PSU)
        # Note: CASE, COOLER, STORAGE are missing!
    ]

    pass_verif = VerificationResult(status=ValidationStatus.PASS, confidence_score=0.99, matched_attributes={})

    listings_map = {
        "AMD Ryzen 5 5600": [Listing(title="Ryzen 5600", price=90.0, url="http://t/cpu", verification=pass_verif)],
        "NVIDIA GeForce RTX 3060": [Listing(title="RTX 3060 12GB", price=200.0, url="http://t/gpu", verification=pass_verif)],
        "AMD B550 Motherboard": [Listing(title="B550 Board", price=75.0, url="http://t/mb", verification=pass_verif)],
        "500W Power Supply": [Listing(title="500W PSU", price=40.0, url="http://t/psu", verification=pass_verif)]
    }
    # Parts total = 90 + 200 + 75 + 40 = 405€
    # Shipping = 4 listings * 6.99€ = 27.96€
    # Gaps = Case (50€) + Cooler (30€) + Storage (55€) = 135€
    # True Ready-to-Play = 405 + 27.96 + 135 = 567.96€

    session_logger = SessionLogger(session_id="test_gap_fill", log_dir=tmp_path)
    build = CombinationEngine.create_best_build(specs, listings_map, session_logger=session_logger)

    assert build is not None
    assert build.total_price == 405.0
    assert build.shipping_cost_total == 27.96
    assert build.gap_fillers_total == 135.0
    assert build.true_ready_to_play_price == 567.96

    assert len(build.standard_fillers) == 3
    filler_slots = [f["slot"] for f in build.standard_fillers]
    assert "CASE" in filler_slots
    assert "COOLER" in filler_slots
    assert "STORAGE" in filler_slots

    # Verify ready_to_play_gap_filled event
    events = SessionLogger.read_session_events(session_logger.log_file)
    gap_events = [e for e in events if e.get("event_type") == "ready_to_play_gap_filled"]
    assert len(gap_events) == 1
    assert gap_events[0]["data"]["true_ready_to_play_price"] == 567.96
