import sys
import os
sys.path.append(os.getcwd())
from hardware_crawler.database import DatabaseManager

print("Initializing DB Manager...")
db = DatabaseManager(":memory:")
print("Methods:", dir(db))
if hasattr(db, "add_listing"):
    print("add_listing found")
else:
    print("add_listing MISSING")
