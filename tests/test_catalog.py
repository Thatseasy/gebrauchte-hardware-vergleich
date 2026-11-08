import pytest
from hardware_crawler.catalog import HardwareCatalog
from hardware_crawler.models import ComponentType

@pytest.fixture(scope="module")
def catalog():
    return HardwareCatalog.reload()

def test_catalog_lookup(catalog):
    gpu = catalog.find_item("RTX 3070 Ti")
    assert gpu is not None
    assert gpu.canonical_name == "NVIDIA GeForce RTX 3070 Ti"
    assert gpu.vram_gb == 8
    assert gpu.tdp_w == 290
    assert gpu.type == "GPU"

    cpu = catalog.find_item("Ryzen 7 7800X3D")
    assert cpu is not None
    assert cpu.socket == "AM5"
    assert cpu.memory_types == ["DDR5"]
    assert cpu.gaming_score == 100

def test_catalog_alternatives(catalog):
    # Test GPU Alternatives (within +/- 15% raster score)
    rtx_3070 = catalog.find_item("RTX 3070")
    assert rtx_3070 is not None
    gpu_alts = catalog.get_alternatives(rtx_3070, threshold_pct=0.15)
    assert len(gpu_alts) > 0
    gpu_alt_names = [g.canonical_name for g in gpu_alts]
    assert any("2080" in name or "6700" in name or "3070 Ti" in name for name in gpu_alt_names)

    # Test CPU Alternatives: Must strictly share the same socket!
    r5_3600 = catalog.find_item("Ryzen 5 3600")
    assert r5_3600 is not None
    assert r5_3600.socket == "AM4"
    cpu_alts = catalog.get_alternatives(r5_3600, threshold_pct=0.35)
    assert len(cpu_alts) > 0
    for alt in cpu_alts:
        assert alt.socket == "AM4", f"Alternative {alt.canonical_name} must have socket AM4, but had {alt.socket}"

def test_catalog_trap_matrix(catalog):
    """
    Validates anti-collision and brand-token filtering rules against known trap queries:
    1. 'Intel Core i5-13600' must NOT collide with '3600' (Ryzen 5 3600)
    2. 'Intel Core i7-13700' must NOT collide with '3700' (Ryzen 7 3700X)
    3. 'AMD Radeon RX 5700 XT' must NOT collide with '5700' (Ryzen 7 5700X)
    4. 'AMD Ryzen 5 7600' must NOT collide with GPU RX 7600
    5. 'RTX 4070 Super' must resolve to 4070 Super, NEVER base 4070
    6. 'RTX 3060 12GB' vs 'RTX 3060 8GB' must resolve to their respective VRAM SKUs
    """
    # Trap 1: Intel i5-13600 vs Ryzen 5 3600
    res1 = catalog.find_item("Intel Core i5-13600")
    assert res1 is not None, "Intel Core i5-13600 lookup failed"
    assert res1.id == "cpu_intel_i5_13600k", f"Expected cpu_intel_i5_13600k, got {res1.id}"
    assert res1.id != "cpu_ryzen_5_3600", "Critical collision: Intel i5-13600 matched Ryzen 5 3600!"

    # Trap 2: Intel i7-13700 vs Ryzen 7 3700X
    res2 = catalog.find_item("Intel Core i7-13700")
    assert res2 is not None, "Intel Core i7-13700 lookup failed"
    assert res2.id == "cpu_intel_i7_13700k", f"Expected cpu_intel_i7_13700k, got {res2.id}"
    assert res2.id != "cpu_ryzen_7_3700x", "Critical collision: Intel i7-13700 matched Ryzen 7 3700X!"

    # Trap 3: RX 5700 XT vs Ryzen 7 5700X
    res3 = catalog.find_item("AMD Radeon RX 5700 XT")
    assert res3 is not None, "AMD Radeon RX 5700 XT lookup failed"
    assert res3.id == "gpu_rx_5700_xt", f"Expected gpu_rx_5700_xt, got {res3.id}"
    assert res3.id != "cpu_ryzen_7_5700x", "Critical collision: RX 5700 XT matched Ryzen 7 5700X!"

    # Trap 4: Ryzen 5 7600 vs RX 7600
    res4 = catalog.find_item("AMD Ryzen 5 7600")
    assert res4 is not None, "AMD Ryzen 5 7600 lookup failed"
    assert res4.id == "cpu_ryzen_5_7600", f"Expected cpu_ryzen_5_7600, got {res4.id}"
    assert res4.id != "gpu_rx_7600", "Critical collision: AMD Ryzen 5 7600 matched GPU RX 7600!"

    # Trap 5: Specificity - RTX 4070 Super vs RTX 4070
    res5 = catalog.find_item("RTX 4070 Super")
    assert res5 is not None, "RTX 4070 Super lookup failed"
    assert res5.id == "gpu_rtx_4070_super", f"Expected gpu_rtx_4070_super, got {res5.id}"
    assert res5.id != "gpu_rtx_4070", "Specificity failure: RTX 4070 Super matched base RTX 4070!"

    # Trap 6: VRAM SKU separation (RTX 3060 12GB vs 8GB)
    res6a = catalog.find_item("RTX 3060 12GB")
    assert res6a is not None, "RTX 3060 12GB lookup failed"
    assert res6a.id == "gpu_rtx_3060_12gb"
    assert res6a.vram_gb == 12

    res6b = catalog.find_item("RTX 3060 8GB")
    assert res6b is not None, "RTX 3060 8GB lookup failed"
    assert res6b.id == "gpu_rtx_3060_8gb"
    assert res6b.vram_gb == 8

def test_catalog_type_partitioning(catalog):
    """Verifies that passing component_type restricts search to that partition."""
    # With type GPU, '7600' in context of RX 7600 returns GPU
    gpu_7600 = catalog.find_item("RX 7600", component_type=ComponentType.GPU)
    assert gpu_7600 is not None
    assert gpu_7600.id == "gpu_rx_7600"

    # With type CPU, 'Ryzen 7600' returns CPU
    cpu_7600 = catalog.find_item("Ryzen 7600", component_type=ComponentType.CPU)
    assert cpu_7600 is not None
    assert cpu_7600.id == "cpu_ryzen_5_7600"

    # Searching for GPU while specifying CPU returns None
    assert catalog.find_item("GeForce RTX 4090", component_type="CPU") is None

def test_catalog_self_consistency(catalog):
    """
    Self-consistency audit: Every canonical name and every registered alias
    of every catalog item must deterministically resolve back to its own item ID.
    """
    failures = []
    total_checks = 0
    for item in catalog.items.values():
        test_strings = [item.canonical_name] + item.aliases
        for name in test_strings:
            total_checks += 1
            found = catalog.find_item(name)
            if found is None:
                failures.append(f"Item '{item.id}' alias '{name}' resolved to None")
            elif found.id != item.id:
                failures.append(f"Item '{item.id}' alias '{name}' incorrectly resolved to '{found.id}'")

    assert not failures, f"{len(failures)} out of {total_checks} aliases failed self-consistency: {failures[:5]}"
