import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")

from hardware_crawler.models import Listing, CanonicalSpec, ComponentType, ValidationStatus, VerificationResult, Build
from hardware_crawler.ui_components import render_listing_details, render_build_listings, render_build_details

def test_missing_price_listing_details():
    print("\n--- Test 1: Listing with price=None in render_listing_details ---")
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    l = Listing(
        title="Geforce RTX 3070",
        price=None, # Price is None!
        url="https://example.com",
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    try:
        render_listing_details({"RTX 3070": [l]}, [spec])
        print("PASS (no crash)")
    except Exception as e:
        print(f"CRASH: {type(e).__name__}: {e}")

def test_zero_price_listing_details():
    print("\n--- Test 2: Listing with price=0.0 in render_listing_details ---")
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    l = Listing(
        title="Geforce RTX 3070 VB",
        price=0.0, # Pure VB with price 0
        url="https://example.com",
        is_vb=True,
        needs_negotiation=True,
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    try:
        render_listing_details({"RTX 3070": [l]}, [spec])
        print("PASS (no crash)")
    except Exception as e:
        print(f"CRASH: {type(e).__name__}: {e}")

def test_missing_price_build_listings():
    print("\n--- Test 3: Listing with price=None in render_build_listings ---")
    l = Listing(
        title="Gaming PC RTX 3070",
        price=None,
        url="https://example.com",
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    try:
        render_build_listings([l])
        print("PASS (no crash)")
    except Exception as e:
        print(f"CRASH: {type(e).__name__}: {e}")

def test_extreme_prices_negotiation():
    print("\n--- Test 4: Extreme prices in render_listing_details ---")
    spec = CanonicalSpec(type=ComponentType.GPU, name="RTX 3070")
    for price in [float('inf'), float('nan'), 10.0, 10.01, -100.0, 999999999.0]:
        print(f"Testing price: {price}")
        l = Listing(
            title="Geforce RTX 3070",
            price=price,
            url="https://example.com",
            is_vb=True,
            verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
        )
        try:
            render_listing_details({"RTX 3070": [l]}, [spec])
            print(f"  Price {price}: PASS")
        except Exception as e:
            print(f"  Price {price}: CRASH {type(e).__name__}: {e}")

def test_none_title_and_attributes():
    print("\n--- Test 5: None title/location/url in render_build_details ---")
    l = Listing(
        title=None,
        price=None,
        url=None,
        location=None
    )
    b = Build(components=[l])
    try:
        render_build_details(b)
        print("PASS (no crash)")
    except Exception as e:
        print(f"CRASH: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_missing_price_listing_details()
    test_zero_price_listing_details()
    test_missing_price_build_listings()
    test_extreme_prices_negotiation()
    test_none_title_and_attributes()
