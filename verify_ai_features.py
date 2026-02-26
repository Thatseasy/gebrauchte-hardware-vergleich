import sys
import os
import logging

# Ensure we can import the package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from hardware_crawler.orchestrator import HardwareOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ai_features():
    print("Testing AI Features (DataCard & BuildAgent)...")
    
    orch = HardwareOrchestrator()
    
    # 1. Test DataCardAgent
    component_name = "NVIDIA RTX 3070"
    print(f"\n[1] Testing DataCard for '{component_name}'...")
    data_card = orch.data_card_agent.enrich_component(component_name)
    print(f"Result: {data_card}")
    
    if data_card:
        print("✅ Data Card received.")
    else:
        print("⚠️ Data Card Empty (Check API Key or Mock).")

    # 2. Test BuildAgent
    current_parts = ["AMD Ryzen 5 3600", "MSI B450 Tomahawk"]
    print(f"\n[2] Testing BuildAgent for '{current_parts}'...")
    build_plan = orch.build_agent.create_build_plan(current_parts)
    print(f"Result: {build_plan}")
    
    if build_plan and build_plan.get("status") in ["Incomplete", "Complete"]:
        print("✅ Build Plan received.")
    else:
        print("⚠️ Build Plan Empty/Error.")

if __name__ == "__main__":
    test_ai_features()
