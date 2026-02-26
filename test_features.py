from hardware_crawler.canonicalization import CanonicalSpecFactory
from hardware_crawler.analysis import CompatibilityEngine
from hardware_crawler.models import ComponentType

def test_features():
    print("Testing Multi-Input and Compatibility...")
    
    # 1. Multi-Input Parsing
    input_str = "Ryzen 5800X, RTX 3070 Ti, B550 Gaming"
    specs = CanonicalSpecFactory.from_input_list(input_str)
    
    print(f"Input: {input_str}")
    for i, s in enumerate(specs):
        print(f" - Item {i}: {s.name} -> Type: {s.type}")
        
    assert len(specs) == 3
    print("Len check passed")
    assert specs[0].type == ComponentType.CPU
    print("CPU check passed")
    assert specs[1].type == ComponentType.GPU
    print("GPU check passed")
    assert specs[2].type == ComponentType.MOTHERBOARD
    print("MB check passed")
    
    # 2. Compatibility Check (Should Pass)
    ok, warnings = CompatibilityEngine.check_compatibility(specs)
    print(f"Compatibility Result (Expected True): {ok}")
    if not ok: print(warnings)
    assert ok is True
    
    # 3. Incompatible Test
    bad_input = "Ryzen 7 7800X3D, B450 Tomahawk" # AM5 CPU on AM4 Board
    bad_specs = CanonicalSpecFactory.from_input_list(bad_input)
    ok_bad, warnings_bad = CompatibilityEngine.check_compatibility(bad_specs)
    
    print(f"\nTesting Incompatibility: {bad_input}")
    print(f"Result (Expected False): {ok_bad}")
    print(f"Warnings: {warnings_bad}")
    
    assert ok_bad is False
    assert "Incompatible Sockets" in warnings_bad[0]
    
    print("\n✅ Verification Passed!")

if __name__ == "__main__":
    test_features()
