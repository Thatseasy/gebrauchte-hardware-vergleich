"""
Deep Audit Test Suite for Hardware Matrix & Compatibility Engines.
Validates:
1. hardware_catalog.json (65 components, sockets, RAM generations, TDP, PSUs, aliases, duplicates)
2. CompatibilityEngine.check_compatibility() (forbidden socket combos, RAM mismatches, wattage validation)
3. SimilarityEngine.find_alternatives() and HardwareCatalog.get_alternatives() (CPU socket compatibility)
"""
import sys
import os
import json
from collections import defaultdict
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from hardware_crawler.catalog import HardwareCatalog, CatalogItem
from hardware_crawler.analysis import CompatibilityEngine, SimilarityEngine, GapAnalyzer
from hardware_crawler.models import CanonicalSpec, ComponentType
from hardware_crawler.database import DatabaseManager

class MatrixDeepAuditor:
    def __init__(self, catalog_path: str = "hardware_crawler/data/hardware_catalog.json"):
        self.catalog_path = catalog_path
        self.catalog = HardwareCatalog()
        self.issues: List[Dict[str, Any]] = []

    def record_issue(self, section: str, severity: str, title: str, details: str):
        self.issues.append({
            "section": section,
            "severity": severity,  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
            "title": title,
            "details": details
        })

    def run_all(self):
        print("=" * 80)
        print("HARDWARE MATRIX & COMPATIBILITY ENGINES - DEEP AUDIT")
        print("=" * 80)
        
        self.audit_catalog_integrity()
        self.audit_compatibility_engine()
        self.audit_similarity_engine()
        self.print_summary()

    def audit_catalog_integrity(self):
        print("\n[SECTION 1] AUDITING hardware_catalog.json INTEGRITY...")
        if not os.path.exists(self.catalog_path):
            self.record_issue("Catalog", "CRITICAL", "Catalog File Missing", f"Path not found: {self.catalog_path}")
            return

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        comps = data.get("components", [])
        total_comps = len(comps)
        print(f"Loaded {total_comps} components from {self.catalog_path}.")

        # Check total count
        if total_comps < 65:
            self.record_issue("Catalog", "LOW", f"Expected at least 65 components, found {total_comps}", "")

        # 1. Duplicate IDs
        ids = [c.get("id") for c in comps]
        id_counts = defaultdict(int)
        for cid in ids:
            id_counts[cid] += 1
        dup_ids = {cid: cnt for cid, cnt in id_counts.items() if cnt > 1}
        if dup_ids:
            self.record_issue("Catalog", "CRITICAL", "Duplicate IDs in Catalog", str(dup_ids))
        else:
            print("  [PASS] No duplicate IDs found.")

        # 2. Duplicate or Overlapping Aliases across different components
        alias_map = defaultdict(list)
        for c in comps:
            cid = c.get("id")
            c_name = c.get("canonical_name", "").upper().strip()
            alias_map[c_name].append(cid)
            alias_map[c_name.replace(" ", "")].append(cid)
            for a in c.get("aliases", []):
                a_clean = a.upper().strip()
                alias_map[a_clean].append(cid)
                alias_map[a_clean.replace(" ", "")].append(cid)

        conflicts = {a: set(cids) for a, cids in alias_map.items() if len(set(cids)) > 1}
        if conflicts:
            self.record_issue("Catalog", "HIGH", "Conflicting Aliases Across Components", str(conflicts))
        else:
            print("  [PASS] No conflicting aliases across components.")

        # 3. Socket & RAM Generation Audit
        known_sockets = {"AM4", "AM5", "LGA1700", "LGA1200", "LGA1151"}
        socket_counts = defaultdict(int)
        for c in comps:
            ctype = c.get("type")
            cid = c.get("id")
            name = c.get("canonical_name")
            sock = c.get("socket")
            mems = c.get("memory_types", [])

            if sock:
                socket_counts[sock] += 1

            if ctype == "CPU":
                if not sock or sock not in known_sockets:
                    self.record_issue("Catalog", "HIGH", f"CPU {cid} Invalid Socket", f"Socket: {sock}")
                if sock == "AM5" and mems != ["DDR5"]:
                    self.record_issue("Catalog", "CRITICAL", f"AM5 CPU {cid} RAM mismatch", f"Expected ['DDR5'], got {mems}")
                if sock == "AM4" and mems != ["DDR4"]:
                    self.record_issue("Catalog", "CRITICAL", f"AM4 CPU {cid} RAM mismatch", f"Expected ['DDR4'], got {mems}")
                if sock == "LGA1700" and not ("DDR4" in mems and "DDR5" in mems):
                    self.record_issue("Catalog", "MEDIUM", f"LGA1700 CPU {cid} RAM types", f"Got {mems}")

            elif ctype == "MOTHERBOARD":
                if not sock or sock not in known_sockets:
                    self.record_issue("Catalog", "HIGH", f"Motherboard {cid} Invalid Socket", f"Socket: {sock}")
                if sock == "AM5" and mems != ["DDR5"]:
                    self.record_issue("Catalog", "CRITICAL", f"AM5 Motherboard {cid} RAM mismatch", f"Expected ['DDR5'], got {mems}")
                if sock == "AM4" and mems != ["DDR4"]:
                    self.record_issue("Catalog", "CRITICAL", f"AM4 Motherboard {cid} RAM mismatch", f"Expected ['DDR4'], got {mems}")

        print(f"  [INFO] Socket distribution in catalog: {dict(socket_counts)}")
        if "LGA1200" not in socket_counts:
            self.record_issue("Catalog", "MEDIUM", "LGA1200 Missing in hardware_catalog.json",
                              "No LGA1200 CPUs or Motherboards present in the JSON catalog, though supported in CompatibilityEngine.SOCKET_MAP.")

        # 4. TDP and Recommended PSU Values
        for c in comps:
            ctype = c.get("type")
            cid = c.get("id")
            tdp = c.get("tdp_w")
            rec_psu = c.get("rec_psu_w")
            if ctype == "GPU":
                if not tdp or tdp < 50:
                    self.record_issue("Catalog", "HIGH", f"GPU {cid} Unrealistic TDP", f"TDP: {tdp}W")
                if not rec_psu or rec_psu <= tdp:
                    self.record_issue("Catalog", "HIGH", f"GPU {cid} Unrealistic Rec PSU", f"TDP: {tdp}W, Rec PSU: {rec_psu}W")
            elif ctype == "CPU":
                if not tdp or tdp < 35:
                    self.record_issue("Catalog", "HIGH", f"CPU {cid} Unrealistic TDP", f"TDP: {tdp}W")

        # 5. Questionable Aliases
        for c in comps:
            cid = c.get("id")
            aliases = c.get("aliases", [])
            if cid == "mb_z690" and "Z790" in aliases:
                self.record_issue("Catalog", "LOW", "Z790 aliased to mb_z690",
                                  "Z790 is a distinct motherboard generation mapped to Z690.")
            if cid == "cpu_ryzen_7_3700x" and "Ryzen 7 3800X" in aliases:
                self.record_issue("Catalog", "LOW", "Ryzen 7 3800X aliased to 3700X",
                                  "Ryzen 3800X is a higher clocked CPU model mapped to 3700X.")

    def audit_compatibility_engine(self):
        print("\n[SECTION 2] AUDITING CompatibilityEngine.check_compatibility()...")

        # Test Case 1: AM5 CPU + AM4 Motherboard (Forbidden)
        am5_am4_cases = [
            ("AMD Ryzen 7 7800X3D", "AMD B550 Motherboard"),
            ("AMD Ryzen 7 9800X3D", "AMD B450 Motherboard"),
            ("AMD Ryzen 5 7600X", "MSI MAG B550 TOMAHAWK"),
            ("Ryzen 5 7500F", "ASUS ROG STRIX B550-F"),
        ]
        for cpu_name, mb_name in am5_am4_cases:
            cpu = CanonicalSpec(name=cpu_name, type=ComponentType.CPU)
            mb = CanonicalSpec(name=mb_name, type=ComponentType.MOTHERBOARD)
            ok, warnings = CompatibilityEngine.check_compatibility([cpu, mb])
            if ok:
                self.record_issue("CompatibilityEngine", "CRITICAL",
                                  f"AM5 CPU on AM4 MB NOT Blocked: {cpu_name} + {mb_name}",
                                  f"Result: ok={ok}, warnings={warnings}")
            else:
                print(f"  [PASS] Blocked AM5 CPU on AM4 MB: {cpu_name} + {mb_name}")

        # Test Case 2: Intel LGA1700 CPU + LGA1200 Motherboard (Forbidden)
        lga1700_lga1200_cases = [
            ("Intel Core i5-12400F", "MSI Z490-A PRO"),
            ("Intel Core i7-14700K", "Gigabyte Z590 Gaming"),
            ("Intel Core i5-13400", "ASUS ROG STRIX B560-A"),
            ("Intel Core i5-13600K", "MSI Z490-A PRO"),
            ("Intel Core i7-13700K", "ASRock B460 Pro4"),
            ("Intel Core i5-12600K", "MSI H510M-A PRO"),
        ]
        for cpu_name, mb_name in lga1700_lga1200_cases:
            cpu = CanonicalSpec(name=cpu_name, type=ComponentType.CPU)
            mb = CanonicalSpec(name=mb_name, type=ComponentType.MOTHERBOARD)
            ok, warnings = CompatibilityEngine.check_compatibility([cpu, mb])
            cpu_socket = CompatibilityEngine.identify_socket(cpu_name)
            mb_socket = CompatibilityEngine.identify_socket(mb_name)
            
            if ok:
                self.record_issue("CompatibilityEngine", "CRITICAL",
                                  f"LGA1700 CPU on LGA1200 MB NOT Blocked: {cpu_name} + {mb_name}",
                                  f"Result: ok={ok}, warnings={warnings}")
            elif cpu_socket != "LGA1700":
                self.record_issue("CompatibilityEngine", "CRITICAL",
                                  f"LGA1700 CPU Socket Misidentified: {cpu_name}",
                                  f"Identified as {cpu_socket} instead of LGA1700! mb_socket={mb_socket}, warnings={warnings}")
            else:
                print(f"  [PASS] Blocked LGA1700 on LGA1200: {cpu_name} ({cpu_socket}) + {mb_name} ({mb_socket})")

        # Test Case 3: Intel LGA1700 CPUs misidentified as AM4 (SUBSTRING COLLISION BUG)
        intel_substring_bug_cases = [
            ("Intel Core i7-13700K", "AM4", "LGA1700"), # matches "3700" in AM4
            ("Intel Core i5-13600K", "AM4", "LGA1700"), # matches "3600" in AM4
            ("Intel Core i5-12600K", "AM4", "LGA1700"), # matches "2600" in AM4
            ("Intel Core i5-11600K", "AM4", "LGA1200"), # matches "1600" in AM4
        ]
        for cpu_name, wrong_sock, actual_sock in intel_substring_bug_cases:
            detected = CompatibilityEngine.identify_socket(cpu_name)
            if detected == wrong_sock:
                self.record_issue("CompatibilityEngine", "CRITICAL",
                                  f"Socket Substring Collision: {cpu_name}",
                                  f"CPU {cpu_name} erroneously detected as {detected} due to substring match against AM4 tokens! Actual socket: {actual_sock}")
                # Test impact: Pair with AM4 motherboard!
                cpu = CanonicalSpec(name=cpu_name, type=ComponentType.CPU)
                mb_am4 = CanonicalSpec(name="AMD B550 Motherboard", type=ComponentType.MOTHERBOARD)
                ok, warnings = CompatibilityEngine.check_compatibility([cpu, mb_am4])
                if ok:
                    self.record_issue("CompatibilityEngine", "CRITICAL",
                                      f"FALSE POSITIVE: Intel CPU on AM4 MB allowed!",
                                      f"{cpu_name} on AMD B550 Motherboard passed check_compatibility with 0 warnings because both identified as AM4!")
                # Test impact: Pair with actual LGA1700 motherboard!
                if actual_sock == "LGA1700":
                    mb_lga1700 = CanonicalSpec(name="Intel B760 Motherboard", type=ComponentType.MOTHERBOARD)
                    ok_valid, warnings_valid = CompatibilityEngine.check_compatibility([cpu, mb_lga1700])
                    if not ok_valid:
                        self.record_issue("CompatibilityEngine", "CRITICAL",
                                          f"FALSE NEGATIVE: Valid LGA1700 build rejected!",
                                          f"Valid build {cpu_name} + Intel B760 rejected: {warnings_valid}")

        # Test Case 4: RAM Compatibility (DDR4 on AM5, DDR5 on AM4, DDR5 on LGA1200)
        ram_cases = [
            ("AM5", "32GB DDR5 RAM", "AMD B650 Motherboard", True, "DDR5 on AM5 (Valid)"),
            ("AM5", "32GB DDR4 RAM", "AMD B650 Motherboard", False, "DDR4 on AM5 (Forbidden)"),
            ("AM4", "32GB DDR4 RAM", "AMD B550 Motherboard", True, "DDR4 on AM4 (Valid)"),
            ("AM4", "32GB DDR5 RAM", "AMD B550 Motherboard", False, "DDR5 on AM4 (Forbidden)"),
            ("LGA1200", "32GB DDR4 RAM", "MSI Z490-A PRO", True, "DDR4 on LGA1200 (Valid)"),
            ("LGA1200", "32GB DDR5 RAM", "MSI Z490-A PRO", False, "DDR5 on LGA1200 (Forbidden)"),
        ]
        for sock_family, ram_name, mb_name, should_pass, desc in ram_cases:
            mb = CanonicalSpec(name=mb_name, type=ComponentType.MOTHERBOARD)
            ram = CanonicalSpec(name=ram_name, type=ComponentType.RAM)
            ok, warnings = CompatibilityEngine.check_compatibility([mb, ram])
            if should_pass and not ok:
                self.record_issue("CompatibilityEngine", "HIGH", f"RAM Check False Negative: {desc}", str(warnings))
            elif not should_pass and ok:
                self.record_issue("CompatibilityEngine", "CRITICAL" if "AM5" in sock_family else "HIGH",
                                  f"RAM Check False Positive (Forbidden RAM allowed): {desc}",
                                  f"{ram_name} on {mb_name} ({sock_family}) passed check_compatibility with 0 warnings!")
            else:
                print(f"  [PASS] RAM test: {desc}")

        # Test Case 5: Power Supply (PSU) Wattage Check
        psu_cases = [
            ("NVIDIA GeForce RTX 4090", 450, "Intel Core i9-14900K", 253, "450W Power Supply", 450, False),
            ("NVIDIA GeForce RTX 4080", 320, "Intel Core i7-14700K", 253, "500W Power Supply", 500, False),
            ("NVIDIA GeForce RTX 3070", 220, "AMD Ryzen 5 5600X", 65, "750W Power Supply", 750, True),
        ]
        print("\n  Testing PSU wattage checks in CompatibilityEngine...")
        for gpu_name, gpu_tdp, cpu_name, cpu_tdp, psu_name, psu_watt, should_pass in psu_cases:
            specs = [
                CanonicalSpec(name=gpu_name, type=ComponentType.GPU),
                CanonicalSpec(name=cpu_name, type=ComponentType.CPU),
                CanonicalSpec(name=psu_name, type=ComponentType.PSU)
            ]
            ok, warnings = CompatibilityEngine.check_compatibility(specs)
            est_wattage = GapAnalyzer.estimate_psu_wattage(specs)

            if not should_pass and ok:
                self.record_issue("CompatibilityEngine", "CRITICAL",
                                  f"Missing PSU Wattage Check: {gpu_name} + {psu_name}",
                                  f"{gpu_name} ({gpu_tdp}W TDP) with {psu_name} ({psu_watt}W) passed with ok={ok}, warnings={warnings}! Estimated minimum required wattage: {est_wattage}W.")
            elif not should_pass and not ok:
                print(f"  [PASS] Blocked insufficient PSU: {gpu_name} + {psu_name} ({warnings})")
            else:
                print(f"  [PASS] Sufficient PSU accepted: {gpu_name} + {psu_name}")

    def audit_similarity_engine(self):
        print("\n[SECTION 3] AUDITING SimilarityEngine & HardwareCatalog ALTERNATIVES...")

        # 1. HardwareCatalog.get_alternatives() for CPUs
        print("  Auditing HardwareCatalog.get_alternatives()...")
        cpu_items = [item for item in self.catalog.items.values() if item.type == "CPU"]
        cross_socket_leaks = []
        for cpu in cpu_items:
            for threshold in [0.15, 0.30, 0.50, 1.0]:
                alts = self.catalog.get_alternatives(cpu, threshold_pct=threshold)
                for alt in alts:
                    if alt.socket != cpu.socket:
                        cross_socket_leaks.append((cpu.canonical_name, cpu.socket, alt.canonical_name, alt.socket))

        if cross_socket_leaks:
            self.record_issue("HardwareCatalog", "CRITICAL", "Cross-Socket CPU Alternatives in HardwareCatalog",
                              str(cross_socket_leaks))
        else:
            print(f"  [PASS] HardwareCatalog.get_alternatives(): 0 cross-socket leaks across all {len(cpu_items)} CPUs.")

        # 2. SimilarityEngine.find_alternatives() (Analysis.py)
        print("  Auditing SimilarityEngine.find_alternatives()...")
        test_db_path = "scratch/test_audit_db.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = DatabaseManager(test_db_path)
        try:
            # Populate DB with reference CPUs of different sockets having similar scores
            # Ryzen 7 5800X3D (AM4, score 87)
            # Ryzen 5 7600X (AM5, score 80)
            # Core i5-13600K (LGA1700, score 84)
            db.save_reference_hardware({'id': 'cpu_am4_1', 'name': 'AMD Ryzen 7 5800X3D', 'type': 'CPU', 'score': 87, 'socket': 'AM4'})
            db.save_reference_hardware({'id': 'cpu_am5_1', 'name': 'AMD Ryzen 5 7600X', 'type': 'CPU', 'score': 80, 'socket': 'AM5'})
            db.save_reference_hardware({'id': 'cpu_lga1700_1', 'name': 'Intel Core i5-13600K', 'type': 'CPU', 'score': 84, 'socket': 'LGA1700'})

            sim_engine = SimilarityEngine(db)
            spec_am4 = CanonicalSpec(name='AMD Ryzen 7 5800X3D', type=ComponentType.CPU)
            alts = sim_engine.find_alternatives(spec_am4, threshold=0.15)
            
            incompatible_alts = [a for a in alts if a.attributes.get('socket') != 'AM4']
            if incompatible_alts:
                alt_summary = [f"{a.name} ({a.attributes.get('socket')})" for a in incompatible_alts]
                self.record_issue("SimilarityEngine", "CRITICAL",
                                  "SimilarityEngine Suggests Cross-Socket CPU Alternatives",
                                  f"Query for AM4 CPU 'AMD Ryzen 7 5800X3D' returned incompatible socket CPUs: {', '.join(alt_summary)}. "
                                  f"SimilarityEngine.find_alternatives() lacks socket filtering!")
            else:
                print("  [PASS] SimilarityEngine strictly enforced socket match.")

        finally:
            if os.path.exists(test_db_path):
                try:
                    os.remove(test_db_path)
                except Exception:
                    pass

    def print_summary(self):
        print("\n" + "=" * 80)
        print("AUDIT FINDINGS & DEFECT REPORT")
        print("=" * 80)

        criticals = [i for i in self.issues if i['severity'] == 'CRITICAL']
        highs = [i for i in self.issues if i['severity'] == 'HIGH']
        mediums = [i for i in self.issues if i['severity'] == 'MEDIUM']
        lows = [i for i in self.issues if i['severity'] == 'LOW']

        print(f"Total Issues Found: {len(self.issues)}")
        print(f"  🔴 CRITICAL: {len(criticals)}")
        print(f"  🟠 HIGH:     {len(highs)}")
        print(f"  🟡 MEDIUM:   {len(mediums)}")
        print(f"  🟢 LOW:      {len(lows)}")
        print("-" * 80)

        for idx, issue in enumerate(self.issues, 1):
            print(f"#{idx} [{issue['severity']}] [{issue['section']}] {issue['title']}")
            if issue['details']:
                print(f"    Details: {issue['details']}")
        print("=" * 80)

if __name__ == "__main__":
    auditor = MatrixDeepAuditor()
    auditor.run_all()
