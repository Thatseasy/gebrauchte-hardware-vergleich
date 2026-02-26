import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from hardware_crawler.canonicalization import CanonicalSpecFactory
from hardware_crawler.scrapers import KleinanzeigenScraper
from hardware_crawler.verification import VerificationEngine
from hardware_crawler.models import Build, BuildType, ValidationStatus, ComponentType
from hardware_crawler.analysis import GapAnalyzer

def debug_flow():
    print("--- 1. Canonicalization ---")
    input_text = "Ryzen 5800X, RTX 3070"
    specs = CanonicalSpecFactory.from_input_list(input_text)
    for s in specs:
        print(f"Spec: {s.name} ({s.type}) Queries: {s.search_queries}")

    print("\n--- 2. Scraping (Mocked or Real?) ---")
    # Let's run REAL scraping to see if it hangs or errors
    scraper = KleinanzeigenScraper()
    
    results_by_spec = {}
    
    for spec in specs:
        print(f"Scraping for {spec.name}...")
        try:
            listings = scraper.search_for_spec(spec)
            print(f"Found {len(listings)} raw listings.")
            
            verified = []
            for l in listings:
                res = VerificationEngine.verify(l, spec)
                l.verification = res
                if res.status == ValidationStatus.PASS:
                    verified.append(l)
            
            print(f"Verified PASS: {len(verified)}")
            if verified:
                print(f"Top match: {verified[0].title} - {verified[0].price}")
            
            results_by_spec[spec.name] = verified
            
        except Exception as e:
            print(f"ERROR scraping {spec.name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n--- 3. Build Assembly ---")
    try:
        virtual_components = []
        for spec in specs:
            if spec.type in [ComponentType.BUILD, ComponentType.BUNDLE]: continue
            
            listings = results_by_spec.get(spec.name, [])
            if listings:
                best = sorted(listings, key=lambda x: x.price)[0]
                # CRITICAL: This is where we assume the bug was
                best.product_match = spec 
                virtual_components.append(best)
        
        if virtual_components:
            print(f"Assembling build with {len(virtual_components)} components...")
            v_build = Build(components=virtual_components, build_type=BuildType.VIRTUAL)
            v_build.calculate_totals()
            print(f"Total Price: {v_build.total_price}")
            print(f"Total Performance: {v_build.total_performance_score}")
        else:
            print("No components found for build.")
            
        print("\n--- 4. Gap Analysis ---")
        missing = GapAnalyzer.analyze_completeness(specs)
        print(f"Missing: {missing}")
        wattage = GapAnalyzer.estimate_psu_wattage(specs)
        print(f"Est Wattage: {wattage}")

    except Exception as e:
        print(f"ERROR in Build Assembly: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_flow()
