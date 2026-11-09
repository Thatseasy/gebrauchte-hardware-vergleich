# Master Implementation Plan: Kleinanzeigen Gaming-PC Crawler 2.0

## Phase 1: Fundament & Test-Grün (Baseline Health)
- [x] **Git Sync**: `origin/main` Branches (.devcontainer, .gitignore, .env.template) sauber zusammengeführt, ohne lokale Batching-Änderungen zu verlieren.
- [x] **SQLite Windows Lock Fix**: Echter Context Manager mit `conn.close()` im `finally`-Block und `PRAGMA journal_mode=WAL;` in `DatabaseManager` (`test_db_integration.py` fixen).
- [x] **Legacy Test Migration**: `tests/test_database.py` auf aktuelle API (`add_listing`, `get_all_listings`) anpassen.
- [x] **Socket-Erkennung**: `CompatibilityEngine.identify_socket` dynamisch über `SOCKET_MAP` anbinden (behebt `test_features.py`).
- [x] **Gemini-Update**: `hardware_crawler/llm_client.py` auf `gemini-3.8-flash` umstellen.
- [x] **Health Verification**: `uv run pytest` ausführen $\rightarrow$ 100% Tests grün.

## Phase 2: Lokale Hardware- & Kompatibilitäts-Matrix
- [x] **Matrix-Datenbestand (`hardware_catalog.json`) anlegen**:
  - Top ~120 Gaming-GPUs (NVIDIA GTX 900 bis RTX 4000, AMD RX 400 bis RX 7000).
  - Top ~90 Gaming-CPUs (AMD AM4 & AM5, Intel LGA1151v2, LGA1200, LGA1700).
  - Attribute: Sockel, RAM-Generation (DDR4/DDR5), TDP, empfohlene Netzteil-Wattage, TechPowerUp/PCGH Gaming-Index, faire Gebrauchtpreis-Korridore.
- [x] **Deterministische Engines anbinden**:
  - `SimilarityEngine`: Exakte sockel-kompatible Alternativen in 0 ms per Katalog-Lookup.
  - `CompatibilityEngine`: Deterministische Prüfung (Sockel-Match, DDR4 vs DDR5, Wattage = TDP + 100W <= PSU).
  - `DataCardAgent`: Lookups primär aus dem Katalog, kein teurer LLM-Call mehr für Standard-Specs.
- [x] **Unit-Tests für Matrix & Kompatibilität**: Tests für AM4/AM5, DDR4/DDR5 und Wattage-Checks in `tests/test_catalog.py` verifiziert.

## Phase 3: Resilienter Kleinanzeigen-Scraper & Präzises VB-Preis-Parsing
- [x] **Astro & JSON-LD Parser**:
  - Artikel-Extraktion über `article[data-adid]` und `data-href`.
  - Primäre Metadatenerfassung über Schema.org `<script type="application/ld+json">` (Titel, Beschreibung, High-Res Bild-URL).
- [x] **Präzises VB-Preis-Parsing (Kein Datenverlust bei "200€ VB")**:
  - *Kategorie 1:* Festpreis (`200 €`).
  - *Kategorie 2:* Verhandlungsbasis mit Wunschpreis (`200 € VB`, `VB 200 €`) $\rightarrow$ Preis bleibt 200.0, `is_vb = True`.
  - *Kategorie 3:* Reine VB ohne Zahl (`VB`) $\rightarrow$ `price = 0.0`, `needs_negotiation = True`.
  - *Kategorie 4:* Fake-VB / Platzhalter (`1 € VB`, `0 €`) $\rightarrow$ `is_fake_placeholder = True`.
- [x] **Unit-Tests für Scraper**: Offline-HTML-Testcases für alle 4 Preis-Varianten und die neuen Astro-Klassen in `tests/test_scrapers.py`.

## Phase 4: Hybrid-Verifikation (Script-First mit LLM-Verification & Edit)
- [x] **Stufe 1 (Skript-Heuristik)**:
  - Regex-Ausschluss ("SUCHE", "KAUFE", "TAUSCH", "DEFEKT", 1€ Platzhalter).
  - Vorab-Extraktion von Modell-Tokens, VRAM, OVP.
  - Zuweisung eines Confidence-Scores und Review-Flags (`low_confidence`, `complete_pc_bundle_detected`, `ambiguous_vram`).
- [x] **Stufe 2 (LLM Verification & Active Edit)**:
  - Übergabe von unsicheren Grenzgängern im Batch (`verify_listings_batch()`).
  - Das LLM prüft nicht nur binär (Ja/Nein), sondern **editiert und korrigiert aktiv** fehlerhafte Skript-Extrakte (z. B. VRAM-Korrektur oder Ausschluss mobiler Gaming-Laptops).
- [x] **Strukturierte Session-Logs**:
  - Logging-Pipeline (`logs/sessions/session_<timestamp>.jsonl`) via `SessionLogger` implementiert.
  - Dokumentiert jeden Schritt: Rohe Treffer, Skript-Flags, LLM-Verifikationen & Korrekturen, BOM-Extraktionen, Endauswahl.

## Phase 5: Komplett-PC Crawler & BOM-Extraktion (Bill of Materials)
- [x] **Zweispurige Suchstrategie**:
  - Automatische Parallel-Suche nach Einzelteilen UND Komplett-PCs (`Gaming PC <Komponente>`).
- [x] **LLM BOM-Extractor**:
  - Zerlegt den Anzeigentext eines Komplett-PCs in strukturierte Komponenten (CPU, GPU, RAM, Mainboard, SSD, PSU).
- [x] **Arbitrage- & TCO-Rechner**:
  - Gegenüberstellung: Einzelteilwert des PCs vs. Angebotspreis.
  - Einberechnung von Versandkosten ($5 \times \text{Versand} = 35\text{€}$) bei Einzelteilen vs. 1x Komplett-PC.
  - Anzeige des Preisvorteils im System und in den Session-Logs.

## Phase 6: E2E-Verification & UI
- [x] Durchlauf eines realen End-to-End-Szenarios ("RTX 3070") live gegen Kleinanzeigen ausgeführt (77 Treffer gefunden, 3 Komplett-PCs dekonstruiert, 34 Listings aktiv editiert, 2 Laptops herausgefiltert).
- [x] Überprüfung der erzeugten Session-Logs (`logs/sessions/sess_20261108_071136_16138d.jsonl`) auf lückenlose Konsistenz.
- [x] Streamlit UI Feinschliff:
  - Anzeige von VB-Status (`200 € (VB)`).
  - Komplett-PC Arbitrage-Ersparnis-Banner (`🔥 Spar-Vorteil: ~X€ günstiger`).
  - Neuer Tab "📜 Session Log" für transparente Audit-Einsicht.
- [x] Dokumentation & Review in `tasks/todo.md` und `tasks/lessons.md`.

## Phase 8: LLM & BOM Red-Teaming & Robustness Audit
- [x] **Test-Suite Aufbau (`scratch/test_llm_bom_redteam.py`)**:
  - Testfälle für bösartige/irreführende Kleinanzeigen-Texte ("PC OHNE Grafikkarte", "OVP Verkaufe", "Upgrade von X auf Y", vage Bezeichnungen, Rechtschreibfehler).
  - Testfälle für LLM-Fehlertoleranz (Markdown ```json``` Wrapping, unvollständiges/kaputtes JSON, None-GPU Parsing in Arbitrage, API-Exceptions).
- [x] **Execution & Live Red-Teaming**:
  - Ausführung von `scratch/test_llm_bom_redteam.py` mit `uv run`.
  - Analyse der Antworten von `CompletePCParserAgent`, `HardwareVerificationAgent`, `HardwareIntentAgent`.
- [x] **Schwachstellen- & False-Positive-Analyse**:
  - Identifikation von Prompt-Lecks, Arbitrage-Verzerrungen (z. B. Fallback auf +200€ wenn GPU="None"), und Truncation-Risiken (600 Zeichen Cutoff).
  - Dokumentation von Schwachstellen und Empfehlungen/Fixes.
- [x] **Verification & Reporting**:
  - Bereitstellung des finalen Prüfberichts für den Orchestrator / Caller (100% bestanden).

---

## 🔍 Verification & Test Results
- **Unit & Integration Tests**: 19 von 19 Tests erfolgreich (`uv run pytest tests test_features.py test_db_integration.py` $\rightarrow$ 100% grün in 1.58s).
  - `tests/test_catalog.py`: Deterministic lookups & socket-safe CPU alternatives.
  - `tests/test_database.py`: Context manager, SQLite WAL mode, backward compatibility aliases.
  - `tests/test_scrapers.py`: Astro JSON-LD parsing, 4-tier VB price extraction & detail page enrichment.
  - `tests/test_verification.py`: VB preservation, fake-VB rejection, bundle & search detection.
  - `tests/test_orchestrator.py`: 3-Tier funnel, active LLM edit, complete PC arbitrage, session logger.
  - `tests/test_logging.py`: Structured JSONL audit trails.
- **Live E2E Verification (Phase 7 - Live Kleinanzeigen Run)**:
  - Query: `"RTX 3070"` (Session-ID: `sess_20261108_072146_590ac6`)
  - **Optimierte Komplett-PC Suche**: Reale Gaming-PCs mit bereinigter Query `Gaming PC RTX 3070` gefunden.
  - **Detailseiten-Volltext**: Volle Beschreibung jedes Top-PCs nachgeladen.
  - **100% BOM-Erfassung**:
    - Deal 1 (`750 € VB`): *i5-13600KF, RTX 3070, Asus Prime Z690-P, 16GB Fury Beast, 1TB Kingston SSD, 600W Gold PSU, 27" Alienware 360Hz Monitor Bundle*. Käuferschutz: Ja, Versand: Ja. Arbitrage-Sparvorteil: `+40 €` (ohne den Monitor einzurechnen!).
    - Deal 5 (`1000 € VB`): *Ryzen 5 5600, Palit JetStream RTX 3070, Gigabyte B550M Aorus Elite, 32GB DDR4-3600, 2TB Silicon Power NVMe + 1TB HDD, BeQuiet Pure Power 12M 750W*. Käuferschutz: Ja.
  - **VB-Verhandlung**: Für alle Angebote automatischer Vorschlag mit 10–12% Preisnachlass im UI generiert.

## 🛡️ Head of QA Final Certification
- **`scratch/qa_head_audit.py`**: **24/24 Tests bestanden (100.0%)**, 0 Issues (CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0).
- **`scratch/test_scraper_adversarial.py`**: **73/73 Tests bestanden (100.0%)**, 0 Flaws.
- **`scratch/test_matrix_deep_audit.py`**: **21/21 Hardware-Prüfungen bestanden (100.0%)**, 0 Issues.
- **`scratch/test_ui_workflow_audit.py`**: **30/30 Checks bestanden (100.0%)**, 0 Fatal Crashes, 0 Data Integrity Issues.
- **`scratch/test_llm_bom_redteam.py`**: **100% bestanden**, alle Adversarial-, Truncation- & Arbitrage-Guards aktiv.
- **Pytest Suite (`uv run pytest tests test_features.py test_db_integration.py`)**: **19/19 Tests grün (100.0%)**.

---

## Phase 10: Taskforce Fix & Verification Plan

### Track A: Scraper & Heuristic Hardening (Agent A)
- [x] **`scrapers.py:parse_price_info` refaktorisieren**:
  - Dezimaltrennzeichen: Punkt nur als Tausendertrenner werten, wenn 3 Ziffern folgen; `12.50 €` als 12.50 € parsen.
  - Tausendertrenner mit Leerzeichen/Unicode: `1 250 €` und `1\u00a0250 €` vor Regex zusammenführen.
  - VHB & Verhandlungsbasis: `\b(VB|VHB|V\.B\.|VERHANDLUNGSBASIS)\b` erfassen.
  - Mehrere Preise: Neupreise (`NP`, `UVP`) und Versandkosten (`zzgl.`, `Versand`) filtern, damit der echte Angebotspreis gewählt wird.
  - Null-Safeguard: `None` und leere Strings fangen.
- [x] **`verification.py` refaktorisieren**:
  - Negations-Filter: `"kein Tausch"`, `"nicht defekt"`, `"kein Bastler"` nicht mehr als REJECT werten.
  - OVP/Leerkarton-Prüfung: Zwingend in `title` UND `description` prüfen.
  - VRAM-Unterscheidung: `GB RAM` nicht als GPU-VRAM interpretieren.
  - Negative Preise (`<= 0€` ohne VB) sauber abweisen.

### Track B: Hardware Architecture & Compatibility (Agent B)
- [x] **`analysis.py:identify_socket` reparieren**:
  - Wortgrenzen / Regex nutzen (`\b3600\b`, `Ryzen.*3700X`), damit Intel `13700K`, `13600K`, `12600K` nicht als AM4 kollidieren.
  - Spezifische Sockel (LGA1700) vor generischen AM4-Zahlen matchen.
- [x] **Echte Netzteil-Wattage Prüfung in `check_compatibility`**:
  - `(CPU_TDP + GPU_TDP + 100W) * 1.15 <= PSU_Wattage` prüfen und bei Unterdimensionierung Warnung ausgeben.
- [x] **`SimilarityEngine` sockel-sicher anbinden**:
  - Direkt `HardwareCatalog.get_alternatives()` nutzen (Cross-Socket CPU-Leakage verhindern).
- [x] **LGA1200 Support & RAM-Block**:
  - DDR5 auf LGA1200-Boards blockieren.

### Track C: Frontend, Concurrency & Resilience (Agent C)
- [x] **`logging_session.py`: Thread-Safe Locking**:
  - `threading.Lock()` um `log_event()` setzen, um Zeilenverlust unter Windows Concurrency zu beheben.
- [x] **`ui_components.py`: Defensive Null- & Type-Safeguards**:
  - `l.price is not None and l.price > 0.0` absichern.
  - `(c.title or "")[:60]` und `f"{c.price:.0f} €" if c.price is not None else "Preis k.A."`.
  - `math.isfinite(l.price)` vor Verhandlungsvorlagen-Berechnung prüfen.
  - HTML-Escaping (`html.escape`) bei Titeln vor Markdown-Rendering.
- [x] **CSV-Export Härtung**:
  - `utf-8-sig` mit BOM (`\ufeff`) und Semikolon `;` Delimiter für deutsches Microsoft Excel.
- [x] **`app.py`: Reset & Key Preservation**:
  - `st.session_state.orchestrator = HardwareOrchestrator(api_key=active_api_key)` bei Reset nutzen.
  - Session-Log Tab-Crash beheben: Datensätze validieren (`isinstance(ev, dict)`, `str(ev.get('timestamp') or '')[11:19]`).
  - UNKNOWN Groceries ("Banane") nicht in den Kleinanzeigen Market-Scan schicken.
- [x] **`orchestrator.py` & `llm_client.py`: Graceful Fallback**:
  - Wenn LLM fehlschlägt (429/503/Timeout), Angebote mit Heuristik-Score $\ge 0.65$ NICHT blind als REJECT löschen, sondern als `PASS`/`REVIEW` mit Flag `LLM_UNAVAILABLE` erhalten.
  - In `llm_client.py`: 503 Overloaded in Retry-Filter aufnehmen und Markdown-Fences vor `json.loads` strippen.

### Track D: End-to-End Re-Test & Certification (Lead QA)
- [x] **Adversarial Regression-Suites ausführen**:
  - `scratch/test_scraper_adversarial.py` $\rightarrow$ 73/73 Testfälle bestanden.
  - `scratch/test_matrix_deep_audit.py` $\rightarrow$ 21/21 Hardware-Prüfungen bestanden.
  - `scratch/test_ui_workflow_audit.py` $\rightarrow$ 30/30 Frontend-Checks bestanden (0 Crashes, 0 Data-Issues).
  - `scratch/qa_head_audit.py` $\rightarrow$ 24/24 Chaos-Szenarien bestanden (100% Pass Rate).
- [x] **Pytest Gesamttests**:
  - `uv run pytest tests test_features.py test_db_integration.py` $\rightarrow$ 19/19 grün (100%).

---

## Phase 11: DOM-First Pricing, Scam Transparency & Catalog Expansion Strategy

### Subagent 1: DOM Price Extraction & Scam Separation Investigation
- [x] **DOM Price Extraction Audit**:
  - Untersuchen, wie `_parse_article` und `parse_price_info` aktuell den Preis beziehen: Nutzer-Eindruck bestätigt! `ad.find_all(...)` erfasste Beschreibungstexte mit '€', und der dedizierte Selektor lag im blockierten `else`-Zweig.
  - Regelwerk definiert: Primäre DOM-Preiselemente haben absolute Priorität. Beschreibung wird bei vorhandenem Betrag ignoriert und nur bei reiner "VB" als Wunschpreis-Fallback herangezogen.
- [x] **Scam Separation Architecture (Transparenz statt Löschen)**:
  - Bisher: Inserate mit OVP, Leerkarton, Defekt wurden als REJECT stillschweigend gelöscht.
  - Konzept fertig: `ValidationStatus.SCAM_SUSPECT` mit `is_scam_suspected = True` und `scam_reason` einführen, in `listings_map` erhalten, aus Virtual Builds ausschließen und im Frontend in eingeklappter Warn-Sektion anzeigen.

### Subagent 2: Hardware Catalog Expansion & Optimization Strategy
- [x] **Bestandsanalyse des 67-Teile-Katalogs**:
  - Bisheriger Katalog war ein MVP für Top-Hardware der letzten 1–2 Generationen. Auf Kleinanzeigen sind jedoch >60% Budget-PCs (200–700€) mit Ryzen 1000–3000, Intel 8.–11. Gen, GTX 10/16, RTX 20, RX 500/5000.
  - Schwere Substring-Lücke in `find_item()` aufgedeckt: `"13600"` matchte fälschlicherweise auf `"3600"` (Ryzen 5 3600).
- [x] **Skalierungs- & Generierungsstrategie**:
  - Zweistufige Hybrid-Lösung beschlossen: Kuratierter Core-Katalog mit ~235–250 Komponenten (0ms, 100% deterministisch) + Dynamischer Self-Learning Cache für Exoten.
  - 5-Schichten-Kollisionsschutz (Regex-Wortgrenzen mit Lookarounds, Verbot isolierter Modellnummern, Brand-Token-Filter, Typ-Partitionierung, CI-Trap-Matrix-Tests).

### Phase 11 Umsetzungsschritte (Beauftragung über Subagents)
- [x] **Track A (DOM & Scam Implementation)**:
  - [x] `hardware_crawler/models.py`: `ValidationStatus.SCAM_SUSPECT` und `scam_reason` ergänzen.
  - [x] `hardware_crawler/scrapers.py`: `_parse_article()` auf strikte DOM-Preisselektoren umstellen (Ausschluss von Beschreibungs-Tags) und Wunschpreis-Fallback bei reiner VB einbauen.
  - [x] `hardware_crawler/verification.py`: Scam-/OVP-/Defekt-Erkennung auf `SCAM_SUSPECT` umstellen.
  - [x] `hardware_crawler/orchestrator.py`: Erhalt von `SCAM_SUSPECT`-Inseraten in `listings_map` & Kennzeichnung defekter Komplett-PCs.
  - [x] `hardware_crawler/analysis.py`: Ausschluss von `SCAM_SUSPECT` / `is_scam_suspected` aus `create_best_build()`.
  - [x] `hardware_crawler/ui_components.py`: Eingeklappte Warnbox `⚠️ Verdächtige Angebote / Scam-Verdacht (${count})` im Frontend rendern & CSV-Export anpassen.
  - [x] Tests & Verifikation: `tests/test_scrapers.py`, `tests/test_verification.py`, `scratch/test_scraper_adversarial.py`, `scratch/qa_head_audit.py` ausführen und verifizieren (100% grün).
- [x] **Track B (Hardware Catalog Expansion & Collision Hardening)**:
  - [x] **Phase B.1: Catalog Engine Hardening (`hardware_crawler/catalog.py`)**:
    - [x] Replace naive substring check with regex word boundaries: `(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])`
    - [x] Implement Brand-Token filtering (detect Intel vs AMD tokens, prevent cross-brand match unless comparison)
    - [x] Support type-partitioned matching (`component_type: Optional[str] = None`) with `alias_map_by_type`
    - [x] Sort aliases by specificity/length descending
  - [x] **Phase B.2: Catalog Generator Expansion (`scripts/generate_catalog.py`)**:
    - [x] Define ~75 GPUs (RTX 40, RTX 30, RTX 20, GTX 10/16/9, RX 7000, RX 6000, RX 5000/500, Intel Arc)
    - [x] Define ~70 CPUs (AM5, AM4, LGA1700, LGA1200, LGA1151v2)
    - [x] Define ~30 Motherboard Chipsets (AM5, AM4, LGA1700, LGA1200, LGA1151v2)
    - [x] Define RAM Kits (8GB, 16GB, 32GB, 64GB DDR4 & DDR5)
    - [x] Define PSUs (400W, 450W, 500W, 550W, 600W, 650W, 750W, 850W, 1000W)
    - [x] Strip all bare 4-digit numbers as aliases
    - [x] Execute `uv run python scripts/generate_catalog.py` and verify `hardware_catalog.json` size (241 items)
  - [x] **Phase B.3: Trap-Matrix & Consistency Tests (`tests/test_catalog.py`)**:
    - [x] Add Trap Matrix tests (Intel i5-13600 vs Ryzen 3600, i7-13700 vs Ryzen 3700X, RX 5700 XT vs Ryzen 5700X, Ryzen 5 7600 vs RX 7600, RTX 4070 Super vs RTX 4070, RTX 3060 12GB vs 8GB)
    - [x] Add self-consistency test (all catalog aliases resolve to their own item)
    - [x] Update `scratch/test_matrix_deep_audit.py` if needed for new socket/catalog expectations (241 components, 0 defects)
  - [x] **Phase B.4: Comprehensive Verification**:
    - [x] Run `uv run pytest tests/test_catalog.py` (5/5 passed in 0.17s)
    - [x] Run `uv run python scratch/test_matrix_deep_audit.py` (21/21 passed, 0 defects)
    - [x] Run full test suite `uv run pytest` (26/26 passed in 1.81s)

---

## 🏆 Track B Review: Hardware-Katalog-Erweiterung & Kollisionshärtung
- **Beseitigung der Substring-Lücke**: In `HardwareCatalog.find_item()` wurde das naive `alias in clean` durch Regex-Lookarounds `(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])` ersetzt.
- **Brand-Token-Filterung**: Text mit expliziten Intel-Tokens (`INTEL`, `CORE I3-I9`, `I3-I9`, `LGA1700/1200/1151`, `ARC`) blockiert AMD-Kandidaten und umgekehrt (außer bei Vergleichen oder wenn beide Brands genannt werden).
- **Typ-Partitionierung**: `find_item()` unterstützt `component_type` (`ComponentType.GPU`, `"CPU"` etc.) zur zielgerichteten Suche in `alias_map_by_type`.
- **Spezifitäts-Sortierung**: Aliase werden nach Länge, Modifikatoren (`SUPER`, `TI`, `XTX`, `XT`, `X3D`, `GB`) und Trennzeichen absteigend sortiert, sodass spezifischere Begriffe (`RTX 4070 SUPER`, `RTX 3060 12GB`) stets vor allgemeinen Begriffen (`RTX 4070`, `RTX 3060`) matchen.
- **241 Kernkomponenten**: Vollständige Marktabdeckung des deutschen Kleinanzeigen-Gebrauchtmarktes (RTX 40/30/20, GTX 10/16/9, RX 7000/6000/5000/500/400, Intel Arc, AM5, AM4, LGA1700, LGA1200, LGA1151v2, Mainboards AM5/AM4/LGA1700/LGA1200/LGA1151, RAM DDR4/DDR5, PSUs 400W–1200W).
- **Keine nackten 4-stelligen Nummern**: Striktes Verbot von nackten Nummern ("3600", "5700", "7600") als Aliase, zusätzlich abgesichert durch automatische Filterung im Loader.
- **Vollständige Trap-Matrix- & Konsistenz-Verifikation**: Alle 6 Trap-Matrix-Fälle und 1.228 Alias-Self-Consistency-Prüfungen in `tests/test_catalog.py` und `scratch/test_matrix_deep_audit.py` zu 100% bestanden.


---

## 🏆 Track A Review: DOM-First Preisextraktion & Scam-Transparenz
- **DOM-Priorisierung**: `_parse_article()` priorisiert dedizierte DOM-Preisselektoren (`[data-testid="ad-price"]`, `.aditem-main--middle--price-shipping--price`, `.aditem-addon--price`, `.aditem-main--middle--price`, `p[class*="price"], span[class*="price"]`).
- **Fließtext-Ausschluss**: Beschreibungsknoten (`.aditem-main--middle--description`, `p[class*="description"]`, `p[class*="onSurfaceSubdued"]`) werden strikt von der Preiskandidaten-Suche ausgeschlossen (kein Auslesen von "Neupreis 800 €" als Angebotspreis).
- **Wunschpreis-Fallback**: Nur wenn im DOM reine 'VB' ohne Betrag vorliegt, wird im Beschreibungstext via Regex nach Wunschpreis gesucht (`price_source: description_fallback`).
- **Scam-Transparenz**: `ValidationStatus.SCAM_SUSPECT` für OVP/Leerkarton, Defekte/Bastlerware und Fake-Platzhalter (<= 5€) mit explizitem `scam_reason`. Angebote bleiben in `listings_map` erhalten, werden im Session-Logger protokolliert und im Frontend in einer standardmäßig eingeklappten Warnbox (`⚠️ Verdächtige Angebote / Scam-Verdacht`) übersichtlich mit Grund, Preis und Link dargestellt.
- **Build-Schutz**: `CombinationEngine.create_best_build()` schließt Scam-verdächtige Inserate strikt aus Virtual Builds aus.
- **Test-Ergebnisse**:
  - `pytest tests/test_scrapers.py tests/test_verification.py`: 11/11 bestanden (100%).
  - `scratch/test_scraper_adversarial.py`: 73/73 bestanden (100%).
  - `scratch/qa_head_audit.py`: 24/24 bestanden (100%).
  - Gesamtsuite `pytest`: 21/21 Unit/Integration Tests grün.

---

## Phase 12: Telemetrie, Traffic-Profiling & Auto-Build-Vervollständigung

### Team 1: Performance, Traffic & Telemetry (Performance & Telemetry Engineer)
- [x] **1.1 Root-Cause Fix für 4-10 Min. Hänger & Resilienz**:
  - [x] `scrapers.py`: Kleinanzeigen-Timeout von 15s auf 7s senken, ConnectionReset-Handling einbauen.
  - [x] `scrapers.py`: Cloudscraper Keep-Alive Session mit Standard-Headern wiederverwenden, sanftes Throttling/Jitter (0.2–0.4s).
  - [x] `orchestrator.py`: ThreadPoolExecutor `max_workers` auf 2 begrenzen.
  - [x] `orchestrator.py`: `fetch_detail_page()` nur für Top-3 bis Top-5 aussichtsreichste Komplett-PCs vorselektiert aufrufen.
  - [x] `llm_client.py`: Gemini 504 Deadline Exceeded abfangen und sofort leeres Dict / Heuristik-Fallback zurückgeben statt Endlos-Retries.
- [x] **1.2 Traffic- & Performance-Monitor (`TrafficMonitor` / `PerformanceTimer`)**:
  - [x] `logging_session.py`: `TrafficMonitor` implementieren (Requests, Datenvolumen KB, HTTP-Statuscodes 200/429/403/504/ConnReset, Cache-Hits, LLM-Calls).
  - [x] `logging_session.py`: `PerformanceTimer` implementieren (Zeiterfassung für Intent, Scraping, Verifikation, BOM, Gesamt).
  - [x] Telemetrie-Hooks in `KleinanzeigenScraper`, `LLMClient`, `HardwareCatalog`, `HardwareOrchestrator` anbinden.
  - [x] `SessionLogger.log_session_complete()` um vollständige Telemetrie-Zusammenfassung erweitern.
- [x] **1.3 Streamlit UI & Browser-Telemetrie**:
  - [x] `ui_components.py`: `render_telemetry_summary()` erstellen für kompakte Darstellung (Dauer, Requests, KB, avg Latenz).
  - [x] `app.py`: Live-Dauer im Status-Balken anzeigen (`⏱️ {elapsed:.1f}s | ...`).
  - [x] `app.py`: "⚡ Performance & Traffic"-Zusammenfassung nach dem Scan rendern.
  - [x] `app.py`: Leichtes JavaScript-Snippet (`st.components.v1.html`) für `window.onerror` & Resource Timing einbinden.
- [x] **1.4 Tests & Zertifizierung**:
  - [x] Unit- & Integrationstests (`uv run pytest`) erweitern und ausführen (33/33 grün in 7.24s).
  - [x] `scratch/qa_head_audit.py` ausführen und 100% grün verifizieren (24/24 bestanden, 0 Issues).
  - [x] Ergebnisse dokumentieren und an Caller melden.

### Team 2: Partial-Input & Auto-Build Completer (Build Completer Engineer)
- [x] **1. Erkennung von Teil- / Einzeleingaben (`is_partial_intent`)**:
  - [x] `orchestrator.py`: `detect_partial_intent(specs)` implementieren & Attribut `is_partial_intent` verankern.
  - [x] Erkennung für 1–2 Kernkomponenten (CPU, GPU) ohne Komplett-PC-Intent.
- [x] **2. `BuildCompleter` Engine (`hardware_crawler/completer.py`)**:
  - [x] Datenklassen `BuildProposal` und `CompletedComponent` definieren.
  - [x] 0ms deterministische Sockel-, Plattform- und TDP-Erkennung via `HardwareCatalog`.
  - [x] Generierung von 3 Tiers (Budget, Mittelklasse/Sweetspot, High-End):
    * CPU-Fokus (AM4 wie 5800X3D, AM5 wie 7800X3D, LGA1700, LGA1200): Budget (RX 6600, ~590€, ~42% Score), Sweetspot (RTX 3070 / RX 6700 XT, ~770€, ~65% Score), High-End (RTX 4070 Super / RX 7800 XT, ~1.140€, ~88% Score).
    * GPU-Fokus (z. B. RTX 3070): Budget (Ryzen 5 5600 + B550 + 16GB, ~580€), Sweetspot (Ryzen 7 5700X3D + B550 + 32GB, ~750€), High-End (Ryzen 7 7800X3D + B650 + 32GB DDR5, ~1.050€).
    * Dual-Fokus (CPU + GPU bereits vorhanden): Ergänzung von Board, RAM, Netzteil, Speicher & Gehäuse.
  - [x] Automatische Berechnung: Gesamtpreis, Gaming-Score, P/L-Verhältnis (Punkte pro Euro / 100€) und Kompatibilitätsbestätigung (`CompatibilityEngine`).
  - [x] Konvertierung jedes Vorschlags in `CanonicalSpec`-Liste für den Sofort-Scan.
- [x] **3. UI-Integration in `app.py` & `ui_components.py`**:
  - [x] `ui_components.py`: `render_build_proposals(proposals)` implementieren mit ansprechenden Build-Karten nebeneinander.
  - [x] `app.py`: Bei `is_partial_intent = True` Vorschläge anzeigen und 1-Klick-Übernahme "🚀 Dieses Setup scannen" aktivieren.
  - [x] Option "Nur eigene Teile scannen" für maximale Flexibilität beibehalten.
- [x] **4. Tests & Verifikation**:
  - [x] `tests/test_completer.py` erstellen mit Tests für AM4, AM5, LGA1700, GPU-Eingabe (RTX/Radeon) und Intent-Erkennung (7/7 bestanden).
  - [x] Ausführung `uv run pytest tests/test_completer.py` und Gesamt-Suite `uv run pytest` (31/31 bestanden, 100% grün).
  - [x] Dokumentation & Abschlussbericht an Caller via `send_message`.

---

## 🏆 Team 2 Review: Auto-Build Completer & Partial Input Architecture
- **Deterministische 0ms Engine (`BuildCompleter`)**: Keine LLM-Latenz und keine Token-Kosten. Ermittelt Plattform (AM4, AM5, LGA1700, LGA1200), Sockel, TDP und RAM-Typ deterministisch über den 241-Komponenten-Katalog.
- **Drei perfekt ausbalancierte Tiers**:
  1. *🌱 Budget (Maximale Ersparnis):* Maximale Kosteneffizienz für 1080p Ultra (z.B. B450 + 16GB DDR4 + 500W PSU + RX 6600 bei 5800X3D-Eingabe; oder Ryzen 5 5600 + B550 + 16GB RAM + 550W PSU bei RTX 3070-Eingabe).
  2. *⚖️ Mittelklasse (P-L Sweetspot):* Der Sieger für 1440p High-FPS (B550 + 32GB RAM + 650W PSU + RTX 3070 / RX 6700 XT; oder Ryzen 7 5700X3D + 32GB RAM + 650W PSU).
  3. *🚀 High-End (Maximale Power):* Maximale Leistung auf der Zielplattform (RTX 4070 Super / 7800 XT + 32GB RAM + 750W Gold PSU; oder Ryzen 7 7800X3D + B650 + DDR5).
- **Metriken & Kompatibilitätsgarantie**: Jedes Tier liefert Gesamtpreis, Preiskorridor, relativen Gaming-Score (0-100), P/L-Verhältnis (`pl_label`, z.B. `8.4 Pkt. / 100€`), BOM-Auflistung und eine Verifikation durch `CompatibilityEngine.check_compatibility()` (100% kompatibel).
- **1-Klick Streamlit UI**: Interaktive Build-Karten nebeneinander mit direkter Übernahme (`orch.apply_build_proposal()`) und sofortigem Suchlauf. Alternative Option ("Nur eigene Teile scannen") bleibt für volle Flexibilität verfügbar.
- **Tests**: 7/7 Tests in `tests/test_completer.py` und 33/33 Tests im gesamten Projekt erfolgreich (`uv run pytest` 100% grün).

---

## 🏆 Team 1 Review: Performance, Traffic-Reduktion & Telemetrie
- **Root-Cause des 4–10 Min. Hängers eliminiert**:
  1. *Kleinanzeigen TCP RST & Concurrency:* `max_workers` in `orchestrator.py` von 5 auf 2 gesenkt. Session-Reuse mit Keep-Alive und Standard-Browser-Headern in `KleinanzeigenScraper` implementiert. Sanftes Throttling / Jitter (`0.2s - 0.4s`) zwischen Requests hinzugefügt. Automatische Re-Initialisierung bei `ConnectionResetError` / WinError 10054.
  2. *Detailseiten-Überlastung behoben:* `fetch_detail_page()` wird in `_search_and_evaluate_complete_pcs()` nur noch für die Top-3 aussichtsreichsten Komplett-PCs aufgerufen (mittels heuristischem `_pc_teaser_score` vorselektiert nach Preis-Korridor, Anchor-Tokens, Käuferschutz und Versand) statt ungedeckelt für alle Inserate. Timeout von 15s auf 7s gesenkt.
  3. *Gemini 504 Deadline Exceeded:* Request-Timeout auf 20s begrenzt. Im Fehlerfall wird ein `504` / `Deadline Exceeded` / Timeout sofort im Exception-Filter abgefangen und bricht ohne langwierige Retry-Schleifen direkt mit sicherem Heuristik-Fallback ab.
- **`TrafficMonitor` & `PerformanceTimer` (`logging_session.py`)**:
  - `TrafficMonitor`: Zählt präzise HTTP-Requests, übertragene Datenmengen (KB), Status-Codes (200, 429, 403, 504, ConnectionReset), 0ms Katalog-Cache-Hits und LLM-Aufrufe / geschätzte Tokens.
  - `PerformanceTimer`: Erfasst präzise Zeiten (`duration_ms` / Sekunden) für Intent Parsing & Katalog-Lookup, Kleinanzeigen Markt-Scraping, Verifikation & Scam-Filterung, LLM-Aufrufe & BOM-Extraktion sowie die Scan-Gesamtdauer.
  - Vollständige Integration in den JSONL-Audit-Trail via `log_session_complete()`.
- **Streamlit UI & Browser-Telemetrie (`app.py`, `ui_components.py`)**:
  - Live-Verlaufsanzeige im Streamlit-Statusbalken während des Scans (`⏱️ {elapsed:.1f}s | Scanne Kleinanzeigen für {spec_name}...`).
  - Neue visuelle Komponente `render_telemetry_summary()`: Zeigt nach dem Scan eine kompakte 4-Metriken-Karte (Gesamtdauer, HTTP-Requests, Datenvolumen KB, Ø Latenz) mit aufklappbaren Details zu Pipeline-Phasen und Status-Codes.
  - Leichtgewichtiges Browser-JS-Snippet via `components.html`: Erfasst `window.onerror`, unhandled promise rejections sowie Resource- & Navigation-Timings (DOM Ready, Page Load, Transfer Size) im Browser-Log.
- **Tests & Qualitätssicherung**:
  - `uv run pytest`: 33/33 Tests bestanden (100% grün in 7.24s).
  - `scratch/qa_head_audit.py`: 24/24 Chaos- und Stress-Szenarien bestanden (100.0%, 0 Issues).
  - `scratch/test_scraper_adversarial.py`: 73/73 Tests bestanden (100.0%, 0 Flaws).

---

## Sprint 3: Deal-Checker, Full-Build Intelligence & UX Overhaul

### Phase 1: Rules & Notion Project Management Setup
- [x] Create `rules.md` in workspace root enforcing Notion sync, logging-first approach, and strict team separation.
- [x] Create Notion Subpage "Sprint 3: Deal-Checker, Full-Build Intelligence & UX Overhaul" under page `2f4d261b-913c-80c2-9bbe-c43b94062846` (Page ID: `412d261b-913c-812c-a951-ee4c69a7895b`).
- [x] Create Notion Task Database with columns: Task Name, Status, Priority, Assignee / Team, Category (Data Source: `collection://9ec6db6c-82f2-4125-96f1-ecbe285aed56`).
- [x] Populate Notion database with detailed Sprint 3 tickets:
  - [x] `TICKET-01`: Deal-Checker & Inserat-Bewertung (Paste-to-Evaluate Mode)
  - [x] `TICKET-02`: Multi-Line Listing Parser Hardening & Intent Recovery
  - [x] `TICKET-03`: Hardware Plausibilität & Hard Wattage Cutoff (Block underpowered PSUs)
  - [x] `TICKET-04`: Bundle-Intelligence (Multi-Component Slot Satisfaction)
  - [x] `TICKET-05`: Ready-to-Play Lückenfüllung & Gesamtkostenschätzung
  - [x] `TICKET-06`: Versus-View UI (Kleinanzeigen Komplett-PC vs. Bester Eigenbau)
  - [x] `TICKET-07`: [Backlog] Nightly Delta-Poller & Smart Caching Architecture (Spike)
  - [x] `TICKET-08`: Real-World QA & Browser-Verifikation mit Kleinanzeigen-Inseraten

### Phase 2: Team 1 - Planning & Architecture (Sprint Architect & Spec Writer)
- [x] Dispatch Team 1 subagent to draft technical specifications and pre-implementation logging plan:
  - [x] Pre-Implementation Logging & Telemetry Strategy (What, Where, How across all pipeline stages).
  - [x] TICKET-01: Deal-Checker & Inserat-Bewertung (Paste-to-Evaluate Domain Model & Negotiation Assistant).
  - [x] TICKET-02: Multi-Line Listing Parser Hardening & sess_20261108_122052_2abad8 Forensics.
  - [x] TICKET-03: Hardware Plausibilität & Hard Wattage Cutoff (Block underpowered PSUs before price sort).
  - [x] TICKET-04: Bundle-Intelligence (Multi-Component Slot Satisfaction in CombinationEngine).
  - [x] TICKET-05: Ready-to-Play Lückenfüllung & Gesamtkostenschätzung (Case 50€, Cooler 30€, SSD 55€).
  - [x] TICKET-06: Versus-View UI (2-Spalten-Layout & KPI Showdown: Fertig-PC vs. Bester Eigenbau).
  - [x] TICKET-07: Nightly Delta-Poller & Smart Caching Architecture (Spike & SQLite schema).
- [x] Save specification as `tasks/sprint_3_spec.md`.
- [x] Review Team 1 architectural specification and report to caller.

---

## 🏆 Team 1 Review: Sprint 3 Architecture & Specification
- **Spezifikation & Schnittstellendefinitionen abgeschlossen**: Ausführliches Architekturdokument `tasks/sprint_3_spec.md` (634 Zeilen) erstellt.
- **Pre-Implementation Logging & Telemetrie**: Schemas für alle 6 Kernereignisse (`intent_type_detected`, `deal_check_evaluated`, `hardware_plausibility_rejected`, `bundle_slot_satisfied`, `ready_to_play_gap_filled`, `telemetry_summary`) strikt vor der Implementierung definiert.
- **TICKET-01 bis TICKET-07 vollständig spezifiziert**:
  - `TICKET-01`: Deal-Checker & Inserat-Bewertung mit automatischer Intent-Klassifizierung (`DEAL_CHECK_PASTE` vs. `SEARCH`), Domain-Modell (`DealCheckResult`, `PriceAssessment`), Arbitrage-Formel und deutschem Verhandlungs-Assistenten.
  - `TICKET-02`: Multi-Line Parser Hardening mit Forensik zu `sess_20261108_122052_2abad8.jsonl`, Eliminierung des Query-Stitchings und 0ms Zeilen-Normalisierung gegen den 241-Komponenten-Katalog.
  - `TICKET-03`: Harte Blockierung unterdimensionierter Netzteile (`min_wattage = cpu_tdp + gpu_tdp + 100W`) VOR der Preis-Sortierung in `CombinationEngine`.
  - `TICKET-04`: Multi-Slot-Befriedigung durch Bundles (z.B. CPU + Mainboard + RAM) zur Verhinderung doppelter Komponenten im DIY-Build.
  - `TICKET-05`: Ready-to-Play Lückenfüllung mit Markt-Richtpreisen (Gehäuse 50€, Kühler 30€, SSD 55€) und Versandkosten-Buffer (6.99€/Verkäufer) für echte TCO-Transparenz.
  - `TICKET-06`: Versus-View UI mit 2-Spalten-Showdown in Streamlit (Fertig-PC vs. Bester Eigenbau) inklusive KPI-Vergleich und automatischer System-Empfehlung.
  - `TICKET-07`: Spike für Nightly Delta-Poller auf Seite 1 mit SQLite-Caching (`listings_cache.db`), Preis-Historie und 0ms Warm-Query-Serving.

### Phase 3: Team 2 - Implementation (Fullstack & Core Engine Engineer)
- [x] **Step 1: Pre-Implementation Logging & Telemetry**
  - [x] Implement event helper methods in `hardware_crawler/logging_session.py`:
    * `intent_type_detected`
    * `deal_check_evaluated`
    * `hardware_plausibility_rejected`
    * `bundle_slot_satisfied`
    * `ready_to_play_gap_filled`
    * `telemetry_summary`
- [x] **Step 2: TICKET-01 & TICKET-02: Deal-Checker & Multi-Line Parser**
  - [x] Create `hardware_crawler/deal_checker.py`:
    * `PriceAssessment` Enum & Dataclasses (`EvaluatedComponent`, `NegotiationStrategy`, `DealCheckResult`)
    * `detect_deal_check_intent()` 0ms heuristic classifier
    * `MultiLineAdParser` with bullet stripping, annotation cleanup, regex & 241-catalog matching
    * `DealChecker` valuation engine & German negotiation message generator
  - [x] Update `hardware_crawler/agents.py`: Integrate `MultiLineAdParser` into `HardwareIntentAgent` to prevent query-stitching and drop of secondary parts.
- [x] **Step 3: TICKET-03: Hardware Plausibility & Hard Wattage Cutoff**
  - [x] In `hardware_crawler/analysis.py` (`CombinationEngine`):
    * Implement `_filter_plausible_components()` / `_filter_plausible_psu()` before price sorting
    * Enforce `min_wattage = cpu_tdp + gpu_tdp + 100W`
    * Strictly block underpowered PSUs (e.g. 400W PSU for RTX 3080)
    * Log `hardware_plausibility_rejected`
- [x] **Step 4: TICKET-04: Bundle-Intelligence**
  - [x] In `hardware_crawler/analysis.py` (`CombinationEngine`):
    * Detect bundle listings (CPU + Motherboard, CPU + MB + RAM)
    * Satisfy multiple build slots simultaneously
    * Prevent duplicate purchases for bundle-covered slots
    * Log `bundle_slot_satisfied`
- [x] **Step 5: TICKET-05: Ready-to-Play Gap Filling & TCO**
  - [x] In `hardware_crawler/completer.py` / `analysis.py`:
    * Implement `fill_ready_to_play_gaps()`: add benchmark prices (Case 50€, Cooler 30€, SSD 55€)
    * Compute shipping buffer (6.99€ per distinct seller listing)
    * Calculate and display True Ready-to-Play price
    * Log `ready_to_play_gap_filled`
- [x] **Step 6: TICKET-06: Versus-View UI & Streamlit Integration**
  - [x] In `hardware_crawler/ui_components.py`:
    * Implement `render_deal_check_view()`
    * Implement `render_versus_view()` (2-column showdown, KPIs, recommendation)
  - [x] In `hardware_crawler/app.py`:
    * Integrate `detect_deal_check_intent()` and Deal-Checker flow into chat/search
- [x] **Step 7: Unit & Integration Tests Verification**
  - [x] Create `tests/test_deal_checker.py` (including forensics case from `sess_20261108_122052_2abad8.jsonl`)
  - [x] Create `tests/test_combination_hardening.py`
  - [x] Run `uv run pytest` and verify 100% green test suite (42/42 tests passed)
  - [x] Run QA deep audits (qa_head_audit: 24/24, test_scraper_adversarial: 73/73, matrix_audit: 21/21)
  - [x] Report completion to caller via `send_message`

---

## 🏆 Team 2 Review: Sprint 3 Core Implementation
- **0ms Deal-Checker & Inserat-Bewertung (`deal_checker.py`)**:
  - `MultiLineAdParser`: Zerlegt mehrzeilige Kleinanzeigen-Dumps, strippt Aufzählungszeichen, Emojis und Modding-Annotationen (z.B. PTM7950, Deshroud).
  - Re-Test des User-Falls aus `sess_20261108_122052_2abad8.jsonl`: Alle 8 Komponenten (CPU, GPU, RAM, Motherboard, PSU, Case, Cooler, SSD) wurden zu 100% ohne Query-Stitching und ohne Droppen sekundärer Teile extrahiert.
  - Arbitrage-Bewertung (`DealCheckResult`): Berechnet faire Marktwerte der Teile gegen den 241-Komponenten-Katalog, klassifiziert in `TOP_DEAL`, `FAIR_DEAL` oder `OVERPRICED`.
  - Verhandlungs-Assistent: Generiert höfliche deutsche Anschreiben mit 8–12% Rabattangebot, Barzahlung und Vor-Ort-Abholung.
- **Hardware-Plausibilität & Hard Wattage Cutoff (`analysis.py`)**:
  - VOR der Preissortierung: Berechnet `min_wattage = cpu_tdp + gpu_tdp + 100W`.
  - Unterdimensionierte Netzteile (z.B. 400W PSU bei 320W RTX 3080 + 105W 5800X3D) werden strikt verworfen (`hardware_plausibility_rejected`).
- **Bundle-Intelligence (`analysis.py`)**:
  - Erkennt Bundle-Angebote (CPU + Mainboard + RAM). Befriedigt mehrere Slots gleichzeitig und verhindert doppelte Zukäufe (`bundle_slot_satisfied`).
- **Ready-to-Play Lückenfüllung & TCO (`completer.py` / `analysis.py`)**:
  - Fehlende Slots (Gehäuse 50€, Kühler 30€, SSD 55€) werden transparent mit Markt-Richtpreisen ergänzt.
  - Versandkostenpauschale von 6.99€ pro Einzel-Listing wird im `true_ready_to_play_price` abgebildet (`ready_to_play_gap_filled`).
- **Versus-View UI (`ui_components.py` & `app.py`)**:
  - 2-Spalten-Showdown in Streamlit: Fertig-PC Inserat vs. Bester DIY-Build mit KPI-Gegenüberstellung (Preis, Gaming-Score, P/L) und automatischer System-Empfehlung.
- **Test-Ergebnisse**:
  - `uv run pytest`: 42/42 Tests grün (100% in 8.3s).
  - `scratch/qa_head_audit.py`: 24/24 Tests bestanden (100.0%, 0 Flaws).
  - `scratch/test_scraper_adversarial.py`: 73/73 Tests bestanden (100.0%, 0 Flaws).
  - `scratch/test_matrix_deep_audit.py`: 21/21 Hardware-Prüfungen bestanden (100.0%, 0 Flaws).

---

### Phase 4: Team 3 - Real-User QA Testing (Browser & Playwright Specialist)
- [x] **Team 3 Real-User Browser QA Execution**:
  - [x] Pre-flight Check: Verify Streamlit running on http://localhost:8501 and Playwright Chromium readiness.
  - [x] Step 1: Scrape & select 2-3 real, active Gaming-PC listings from Kleinanzeigen (Title, Description, Price, URL).
  - [x] Step 2: Implement and run automated Playwright real-user browser test suite (`scratch/test_browser_qa.py`):
    * Input real ad fulltext into Streamlit chat input.
    * Verify automatic Deal-Checker intent triggering (`DEAL_CHECK_PASTE`).
    * Verify component deconstruction (CPU, GPU, RAM, Motherboard, PSU, Storage, Cooler, Case).
    * Verify Arbitrage savings & valuation badges (TOP_DEAL / FAIR_DEAL / OVERPRICED).
    * Verify German negotiation assistant template and target offer calculation.
    * Verify Versus-View showdown trigger and 2-column comparative display.
    * Capture high-res fullpage screenshots into `scratch/qa_screenshots/`.
  - [x] Step 3: Run Gegenprüfung with user's original case (`sess_20261108_122052_2abad8.jsonl`) live in browser.
  - [x] Step 4: Verification against Acceptance Criteria of TICKET-01 through TICKET-06.
  - [x] Step 5: Deliver comprehensive QA Certification Report to caller.

---

## 🏆 Team 3 Review: Real-User Browser QA & Certification (TICKET-08)
- **100% Automatisierter Real-User Browser Test (`scratch/test_browser_qa.py`)**:
  - Ausführung mit Playwright Chromium im Headless-Modus auf dem Live-Streamlit-Server (`http://localhost:8501`).
  - 3 reale End-to-End Testfälle erfolgreich validiert:
    1. *Reales Inserat 1:* Ryzen 5 5600 + RTX 3070 (900 € VB, URL: `3558840374-228-794`) $\rightarrow$ Deal-Checker erkennt 9 Komponenten, stuft als OVERPRICED ein (-150 € Abweichung zum Marktwert ~750 €) und erzeugt Gegenangebot von 690 € (-23.3%). Versus-View Showdown belegt P/L-Vorteil des DIY-Builds (7.6 vs. 5.8 Pkt./100 €).
    2. *Reales Inserat 4:* Intel i5-13600KF + RTX 3070 (800 € Festpreis, URL: `3565447776-228-8088`) $\rightarrow$ Deal-Checker erkennt 7 Komponenten, Ready-to-Play Lücke (+30 € für CPU-Kühler) und Verhandlungsassistent mit 740 € Angebot.
    3. *Originalfall des Nutzers (`sess_20261108_122052_2abad8.jsonl`):* Ryzen 5800X3D + RTX 3080 10GB + B450-F + 32GB RAM + Dark Rock Pro 4 + 1TB NVMe + Pure Base 500 + Seasonic 650W $\rightarrow$ 8/8 Komponenten sauber ohne Query-Stitching erkannt. Fairer Gebrauchtpreis (~952 € Marktwert vs. 850 € Angebotspreis, +102 € Ersparnis). Gegenangebot 750 € (-11.8%). Versus-View Showdown bestätigt Fertig-PC Vorteil gegenüber 8 Einzelpaketen mit Versand (850 € vs. 868 € DIY).
- **Hochauflösende Screenshots erstellt & archiviert**:
  - `scratch/qa_screenshots/deal_checker_real_ad_1.png`: Deal-Checker Bewertung, KPI-Metriken, Komponenten-Tabelle, Verhandlungsassistent.
  - `scratch/qa_screenshots/versus_view_real_ad_1.png`: 2-Spalten-Showdown Fertig-PC vs. Bester DIY-Build mit Gaming-Score und P/L-Verhältnis.
  - `scratch/qa_screenshots/deal_checker_real_ad_4.png`: Ready-to-Play Lückenhinweis und Festpreis-Verhandlungsnachricht.
  - `scratch/qa_screenshots/deal_checker_user_original_case.png`: Vollständige 8/8 Komponenten-Zerlegung des Nutzerfalls.
  - `scratch/qa_screenshots/versus_view_user_original_case.png`: Gegenüberstellung Fertig-PC vs. DIY für den Original-Nutzerfall.
- **Engine-Härtung**:
  - `MultiLineAdParser`: Deduplizierung singulärer Komponenten (CPU, GPU, Mainboard, Gehäuse, Netzteil, Kühler) und Filterung von Benchmark-/Haftungs-Disclaimern (3DMark, FurMark, AGB, Impressum).
  - `HardwareOrchestrator`: Fokussierung von Kleinanzeigen-Alternativensuchen auf Kernhardware (GPU, CPU, Mainboard) verhindert ausufernde Scans nach Gehäuse-Exoten und senkt E2E-Latenz drastisch.
- **Regressionstest-Status**:
  - Pytest Gesamt-Suite: **42/42 Tests grün (100.0%)** in 7.08s.
  - `qa_head_audit.py`: **24/24 Tests bestanden (100.0%)**, 0 Issues.

### Phase 6: Autonomous Bug Fixing & UX Polish (Post-Test Refinements)
- [x] **Fix 1: Complete Essential Hardware Spectrum in Deal-Checker (`deal_checker.py`)**
  - Add missing Motherboard (+80€), PSU (+65€), Cooler (+30€), Case (+50€), Storage (+55€), RAM (+45€), CPU (+150€), GPU (+250€) to `missing_essential_parts`
- [x] **Fix 2: Mathematical Soundness in Ready-to-Play Total (`deal_checker.py`)**
  - Fix `ready_to_play_total`: when `final_price <= 0`, base estimate on `total_market_value + ready_to_play_extra` instead of `0 + extra`
- [x] **Fix 3: Fix LaTeX/Markdown corruption `ightarrow` (`ui_components.py`)**
  - Replace `f"$\rightarrow$..."` with clean unicode `→`
- [x] **Fix 4: Fix Metric Badges for Missing Price (`ui_components.py` & `app.py`)**
  - Display `k.A.` without `(Festpreis)` and `—` for savings instead of `0 € (↑ 0.0%)`
- [x] **Fix 5: Interactive Inline Price Input (`ui_components.py` & `app.py`)**
  - Add inline number input directly in the Deal-Checker card + support standalone price inputs in chat
- [x] **Fix 6: Storage Regex & Pricing Precision (`deal_checker.py`)**
  - Match spaced formats like `512 GB` and adjust 512GB used fair value to ~28€
- [x] **Fix 7: Deduplicate Warning Banner (`app.py`)**
  - Remove redundant duplicate banner in chat message vs. card
- [x] **Verification & Tests**
  - Add unit test for the user's 4-component test case in `tests/test_deal_checker.py`
  - Run `uv run pytest` and verify 100% pass rate (41/41 tests passing)
- [x] **Deliverables & Response Formulation**
  - Formulate detailed critique of user screenshots
  - Answer log visibility question (localhost vs Streamlit Cloud)
  - Detail 10 user simulation flows





