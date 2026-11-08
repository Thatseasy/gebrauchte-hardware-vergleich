import pytest
from hardware_crawler.models import Listing, CanonicalSpec, ComponentType, ValidationStatus
from hardware_crawler.verification import VerificationEngine, AttributeExtractor

def test_verify_valid_vb_asking_price():
    spec = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )
    # Listing with 280 € VB
    listing = Listing(
        title="MSI RTX 3070 Ventus 2X 8GB Top Zustand",
        price=280.0,
        url="https://kleinanzeigen.de/s-1",
        platform="Kleinanzeigen",
        location="Berlin",
        description="Verkaufe voll funktionstüchtige RTX 3070.",
        is_vb=True,
        needs_negotiation=False,
        is_fake_placeholder=False
    )
    res = VerificationEngine.verify(listing, spec)
    assert res.status == ValidationStatus.PASS
    assert res.confidence_score >= 0.85
    assert not res.rejection_reasons
    assert any("VB Asking Price" in f for f in res.review_flags)
    assert not VerificationEngine.should_escalate_to_llm(res)

def test_verify_rejects_fake_vb_placeholder():
    spec = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )
    # Listing with 1 € VB placeholder
    listing = Listing(
        title="RTX 3070 Gaming X 8GB",
        price=1.0,
        url="https://kleinanzeigen.de/s-2",
        platform="Kleinanzeigen",
        location="Hamburg",
        description="Macht mir Angebote",
        is_vb=True,
        is_fake_placeholder=True
    )
    res = VerificationEngine.verify(listing, spec)
    assert res.status == ValidationStatus.SCAM_SUSPECT
    assert listing.is_scam_suspected is True
    assert listing.scam_reason == "Scheinpreis / Fake-Platzhalter (<= 5€)"
    assert any("<= 5€" in r for r in res.rejection_reasons)

def test_verify_rejects_defects_and_searches():
    spec = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )
    # Defekt -> SCAM_SUSPECT
    listing_defect = Listing(
        title="RTX 3070 Defekt kein Bild",
        price=100.0,
        url="https://kleinanzeigen.de/s-3",
        platform="Kleinanzeigen",
        location="Köln",
        description="Grafikkarte gibt kein Bild mehr aus, für Bastler."
    )
    res = VerificationEngine.verify(listing_defect, spec)
    assert res.status == ValidationStatus.SCAM_SUSPECT
    assert listing_defect.is_scam_suspected is True
    assert listing_defect.scam_reason == "Defekt / Bastlerware / Ersatzteilspender"
    assert any("defective" in r for r in res.rejection_reasons)

    # Suche -> bleibt REJECT
    listing_suche = Listing(
        title="SUCHE RTX 3070 dringend",
        price=250.0,
        url="https://kleinanzeigen.de/s-4",
        platform="Kleinanzeigen",
        location="München",
        description="Zahle bis zu 250 Euro."
    )
    res2 = VerificationEngine.verify(listing_suche, spec)
    assert res2.status == ValidationStatus.REJECT
    assert listing_suche.is_scam_suspected is False
    assert any("Search Request" in r for r in res2.rejection_reasons)

def test_verify_box_only_scam_suspect():
    spec = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )
    # OVP / Leerkarton -> SCAM_SUSPECT
    listing_box = Listing(
        title="RTX 3070 Nur OVP Leerkarton",
        price=40.0,
        url="https://kleinanzeigen.de/s-box",
        platform="Kleinanzeigen",
        location="Bremen",
        description="Nur die leere Originalverpackung."
    )
    res = VerificationEngine.verify(listing_box, spec)
    assert res.status == ValidationStatus.SCAM_SUSPECT
    assert listing_box.is_scam_suspected is True
    assert listing_box.scam_reason == "Verdacht auf OVP / Leerkarton / Fehlende Kernkomponente"

def test_verify_bundle_detection_escalates_to_llm():
    spec = CanonicalSpec(
        name="RTX 3070",
        type=ComponentType.GPU,
        must_contain_tokens=["3070"],
        must_exclude_tokens=["Ti"],
        expected_attributes={"vram": [8]},
        search_queries=["RTX 3070"]
    )
    # Complete PC bundle found when looking for standalone GPU
    listing_bundle = Listing(
        title="High End Gaming PC mit RTX 3070 und Ryzen 5600X",
        price=650.0,
        url="https://kleinanzeigen.de/s-5",
        platform="Kleinanzeigen",
        location="Frankfurt",
        description="Kompletter PC abzugeben, Top Zustand."
    )
    res = VerificationEngine.verify(listing_bundle, spec)
    assert any("bundle_detected" in f for f in res.review_flags)
    assert VerificationEngine.should_escalate_to_llm(res)
