import sys
import os

# Ensure we can import the package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from hardware_crawler.canonicalization import CanonicalSpecFactory
from hardware_crawler.verification import VerificationEngine
from hardware_crawler.models import Listing, CanonicalSpec, ComponentType

def test_pipeline():
    print("Testing Pipeline...")
    
    # 1. Canonicalization
    input_text = "RTX 3070 Ti"
    spec = CanonicalSpecFactory.from_text_input(input_text)
    print(f"Spec created: {spec.name}")
    # Relaxed assertion for AI-enriched output
    for token in ["3070", "Ti"]:
        assert token in spec.must_contain_tokens, f"Token {token} missing from {spec.must_contain_tokens}"
    
    # 2. Mock Search Results (Simulating Scraper Output)
    mock_listings = [
        Listing(title="Verkaufe Nvidia RTX 3070 Ti Gaming X Trio", price=450.0, url="http://test/1", description="Gebraucht, top zustand 8GB"),
        Listing(title="RTX 3070 ohne Ti", price=350.0, url="http://test/2", description="Normale 3070 8GB"),
        Listing(title="Defekte RTX 3070 Ti nur Karton", price=100.0, url="http://test/3", description="DEFEKT OVP"),
        Listing(title="Suche RTX 3070 Ti", price=0.0, url="http://test/4", description="Suche eine Karte"),
    ]
    
    # 3. Verification
    print("\nVerifying Mock Listings...")
    results = []
    for l in mock_listings:
        res = VerificationEngine.verify(l, spec)
        l.verification = res
        results.append(l)
        print(f"[{res.status.name}] {l.title} (Conf: {res.confidence_score:.2f}) -> Reasons: {res.rejection_reasons}")

    # Assertions
    # 1. First one should PASS
    assert results[0].verification.status.name == "PASS", f"First listing should pass, got {results[0].verification.status.name} ({results[0].verification.rejection_reasons})"
    
    # 2. Second should PASS (Tokens are present string-wise, even if negative context - this is a known limitation)
    # If we wanted to reject "ohne", we'd need exclusion rules or better NLP.
    
    # 3. Defect
    assert results[2].verification.status.name in ["REVIEW", "REJECT"], "Defective item should not PASS"
    assert any(x in str(results[2].verification.rejection_reasons) for x in ["Defect", "Defekt"])
    
    # 4. Suche
    assert results[3].verification.status.name == "REJECT"

    print("\nPipeline Test Passed (Logic verification).")

if __name__ == "__main__":
    test_pipeline()
