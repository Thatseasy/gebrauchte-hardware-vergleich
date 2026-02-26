import sys
import os
import sqlite3

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from hardware_crawler.database import DatabaseManager

def test_db_integration():
    print("Testing DB Integration...")
    db_path = "test_products.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = DatabaseManager(db_path)
    
    # 1. Add verified listing
    listing = {
        "title": "Verkaufe RTX 3070 Verified",
        "price": 400.0,
        "link": "http://test.com/1",
        "source": "Kleinanzeigen",
        "canonical_name": "NVIDIA GeForce RTX 3070",
        "verification_status": "PASS",
        "confidence_score": 0.95,
        "risk_flags": []
    }
    
    success = db.add_listing(listing)
    assert success, "Failed to add listing"
    
    # 2. Add Duplicate (should succeed with OR REPLACE or fail depending on logic)
    # My logic was INSERT OR REPLACE
    success2 = db.add_listing(listing)
    assert success2, "Failed to update duplicate listing"
    
    # 3. Retrieve
    rows = db.get_all_listings()
    assert len(rows) == 1
    row = rows[0]
    assert row['title'] == "Verkaufe RTX 3070 Verified"
    assert row['verification_status'] == "PASS"
    
    print("DB Integration Passed.")
    
    # Clean up
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    test_db_integration()
