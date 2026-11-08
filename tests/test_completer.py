import pytest
from hardware_crawler.completer import BuildCompleter, detect_partial_intent, BuildProposal
from hardware_crawler.models import CanonicalSpec, ComponentType
from hardware_crawler.orchestrator import HardwareOrchestrator
from hardware_crawler.catalog import HardwareCatalog

@pytest.fixture(scope="module")
def catalog():
    return HardwareCatalog.reload()

@pytest.fixture
def completer(catalog):
    return BuildCompleter(catalog)

def test_detect_partial_intent():
    # 1. Single CPU -> Partial
    specs_cpu = [CanonicalSpec(name="AMD Ryzen 7 5800X3D", type=ComponentType.CPU)]
    assert detect_partial_intent(specs_cpu, "AMD Ryzen 7 5800X3D") is True

    # 2. Single GPU -> Partial
    specs_gpu = [CanonicalSpec(name="NVIDIA GeForce RTX 3070", type=ComponentType.GPU)]
    assert detect_partial_intent(specs_gpu, "RTX 3070") is True

    # 3. CPU + GPU -> Partial (needs MB, RAM, PSU)
    specs_pair = [
        CanonicalSpec(name="AMD Ryzen 5 5600", type=ComponentType.CPU),
        CanonicalSpec(name="NVIDIA GeForce RTX 3070", type=ComponentType.GPU)
    ]
    assert detect_partial_intent(specs_pair, "Ryzen 5 5600, RTX 3070") is True

    # 4. Complete system (>= 3 core components) -> Not partial
    specs_full = [
        CanonicalSpec(name="AMD Ryzen 5 5600", type=ComponentType.CPU),
        CanonicalSpec(name="NVIDIA GeForce RTX 3070", type=ComponentType.GPU),
        CanonicalSpec(name="AMD B550 Motherboard", type=ComponentType.MOTHERBOARD),
        CanonicalSpec(name="16GB DDR4 RAM", type=ComponentType.RAM),
        CanonicalSpec(name="650W Power Supply", type=ComponentType.PSU)
    ]
    assert detect_partial_intent(specs_full) is False

    # 5. Dual-Track complete PC query -> Not partial
    assert detect_partial_intent(specs_gpu, "Gaming PC RTX 3070") is False

    # 6. Empty specs -> Not partial
    assert detect_partial_intent([]) is False

def test_completer_am4_cpu(completer):
    """Verifies that an AM4 CPU (Ryzen 7 5800X3D) generates 3 valid, compatible tiers."""
    specs = [CanonicalSpec(name="AMD Ryzen 7 5800X3D", type=ComponentType.CPU)]
    proposals = completer.complete_builds(specs)

    assert len(proposals) == 3
    budget, sweetspot, high_end = proposals

    # Budget Tier Checks
    assert budget.tier_id == "budget"
    assert budget.gaming_score == 42
    assert 500.0 <= budget.total_price <= 680.0
    assert budget.is_compatible is True
    comp_names = [c.name for c in budget.components]
    assert any("B450" in n for n in comp_names)
    assert any("RX 6600" in n for n in comp_names)
    assert any("DDR4" in n for n in comp_names)

    # Sweetspot Tier Checks
    assert sweetspot.tier_id == "sweetspot"
    assert sweetspot.gaming_score == 65
    assert 700.0 <= sweetspot.total_price <= 880.0
    assert sweetspot.is_compatible is True
    sw_names = [c.name for c in sweetspot.components]
    assert any("B550" in n for n in sw_names)
    assert any("RTX 3070" in n or "6700 XT" in n for n in sw_names)
    assert any("32GB" in n for n in sw_names)

    # High-End Tier Checks
    assert high_end.tier_id == "high_end"
    assert high_end.gaming_score == 88
    assert 1050.0 <= high_end.total_price <= 1250.0
    assert high_end.is_compatible is True
    hi_names = [c.name for c in high_end.components]
    assert any("4070 Super" in n for n in hi_names)
    assert any("750W" in n for n in hi_names)

def test_completer_gpu_input(completer):
    """Verifies that a GPU input (RTX 3070) generates 3 valid tiers with matching CPUs."""
    specs = [CanonicalSpec(name="NVIDIA GeForce RTX 3070", type=ComponentType.GPU)]
    proposals = completer.complete_builds(specs)

    assert len(proposals) == 3
    budget, sweetspot, high_end = proposals

    # Budget Tier: Ryzen 5 5600 + B550 + 16GB RAM + 550W PSU (~580€ target)
    assert budget.tier_id == "budget"
    assert budget.is_compatible is True
    b_cpus = [c.name for c in budget.components if c.category == "CPU"]
    assert len(b_cpus) == 1 and "5600" in b_cpus[0]
    assert 550.0 <= budget.total_price <= 680.0

    # Sweetspot Tier: Ryzen 7 5700X3D + B550 + 32GB RAM + 650W PSU (~750€ target)
    assert sweetspot.tier_id == "sweetspot"
    assert sweetspot.is_compatible is True
    m_cpus = [c.name for c in sweetspot.components if c.category == "CPU"]
    assert len(m_cpus) == 1 and "5700X3D" in m_cpus[0]
    assert 700.0 <= sweetspot.total_price <= 820.0

    # High-End Tier: Ryzen 7 7800X3D + B650 + 32GB DDR5 + 750W PSU (~1.050€ target)
    assert high_end.tier_id == "high_end"
    assert high_end.is_compatible is True
    h_cpus = [c.name for c in high_end.components if c.category == "CPU"]
    assert len(h_cpus) == 1 and "7800X3D" in h_cpus[0]
    h_rams = [c.name for c in high_end.components if c.category == "RAM"]
    assert any("DDR5" in r for r in h_rams)
    assert 980.0 <= high_end.total_price <= 1180.0

def test_completer_am5_cpu(completer):
    """Verifies that an AM5 CPU (Ryzen 7 7800X3D) pairs strictly with AM5 boards and DDR5 RAM."""
    specs = [CanonicalSpec(name="AMD Ryzen 7 7800X3D", type=ComponentType.CPU)]
    proposals = completer.complete_builds(specs)

    assert len(proposals) == 3
    for p in proposals:
        assert p.is_compatible is True
        # Ensure all tiers use DDR5
        ram_comps = [c for c in p.components if c.category == "RAM"]
        assert all("DDR5" in r.name for r in ram_comps)
        # Ensure motherboards are AM5
        mb_comps = [c for c in p.components if c.category == "MOTHERBOARD"]
        assert all(any(chip in m.name for chip in ["A620", "B650", "X670", "B850", "X870"]) for m in mb_comps)

def test_completer_lga1700_cpu(completer):
    """Verifies that an Intel LGA1700 CPU generates compatible Intel setups."""
    specs = [CanonicalSpec(name="Intel Core i5-13600K", type=ComponentType.CPU)]
    proposals = completer.complete_builds(specs)

    assert len(proposals) == 3
    for p in proposals:
        assert p.is_compatible is True
        mb_comps = [c for c in p.components if c.category == "MOTHERBOARD"]
        assert all(any(chip in m.name for chip in ["H610", "B660", "B760", "Z690", "Z790"]) for m in mb_comps)

def test_completer_dual_cpu_gpu(completer):
    """Verifies that when both CPU and GPU are entered, both are preserved."""
    specs = [
        CanonicalSpec(name="AMD Ryzen 7 5700X3D", type=ComponentType.CPU),
        CanonicalSpec(name="AMD Radeon RX 6700 XT", type=ComponentType.GPU)
    ]
    proposals = completer.complete_builds(specs)

    assert len(proposals) == 3
    for p in proposals:
        assert p.is_compatible is True
        user_parts = [c for c in p.components if c.is_user_input]
        assert len(user_parts) == 2
        user_names = [c.name for c in user_parts]
        assert any("5700X3D" in n for n in user_names)
        assert any("6700 XT" in n for n in user_names)

def test_orchestrator_partial_intent_flow():
    """Verifies end-to-end integration of partial intent and proposal application in HardwareOrchestrator."""
    orch = HardwareOrchestrator()
    
    # 1. User inputs only a CPU
    added = orch.process_user_intent("AMD Ryzen 7 5800X3D")
    assert len(added) > 0
    assert orch.is_partial_intent is True
    assert len(orch.build_proposals) == 3

    sweetspot_tier = orch.build_proposals[1]
    assert sweetspot_tier.tier_id == "sweetspot"

    # 2. User selects 1-click "🚀 Dieses Setup scannen"
    orch.apply_build_proposal(sweetspot_tier)
    assert orch.is_partial_intent is False
    assert len(orch.specs) == 7
    spec_types = {s.type for s in orch.specs}
    assert ComponentType.CPU in spec_types
    assert ComponentType.GPU in spec_types
    assert ComponentType.MOTHERBOARD in spec_types
    assert ComponentType.RAM in spec_types
    assert ComponentType.PSU in spec_types
