import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.stdout.reconfigure(encoding="utf-8")
from hardware_crawler.ui_components import generate_csv_export
from hardware_crawler.models import Listing, ValidationStatus, VerificationResult

def run_test():
    l1 = Listing(
        title='MSI "Gaming X Trio", 8GB, Top Zustand!',
        price=280.0,
        url='https://kleinanzeigen.de/s-anzeige/123',
        location='München - Schöneberg',
        verification=VerificationResult(status=ValidationStatus.PASS, confidence_score=1.0, matched_attributes={})
    )
    l2 = Listing(
        title='Gehäuse & Lüfter (Weiß, Neuwertig)\nMit OVP',
        price=50.0,
        url='https://kleinanzeigen.de/s-anzeige/456',
        location='Köln',
        verification=None
    )
    listings_map = {'NVIDIA RTX 3070': [l1], 'Gehäuse': [l2]}
    csv_str = generate_csv_export(listings_map)
    print("CSV String output:")
    print(csv_str)
    print("Has UTF-8 BOM?:", csv_str.startswith("\ufeff"))
    print("Bytes start with BOM?:", csv_str.encode("utf-8").startswith(b"\xef\xbb\xbf"))
    
    # Check Excel decoding behavior
    # Without BOM, Excel decodes as CP1252 / Windows-1252 on German Windows
    try:
        decoded_cp1252 = csv_str.encode("utf-8").decode("cp1252")
        print("Excel (CP1252) mojibake sample:", decoded_cp1252[:120])
    except UnicodeDecodeError as e:
        print("Excel (CP1252) decode error:", e)

if __name__ == "__main__":
    run_test()
