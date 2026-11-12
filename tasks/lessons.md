# Lessons Learned

Historical and session lessons captured to prevent repeating mistakes.

## 1. Environment & Architecture
- **Package Management**: Use `uv` for all python commands, tests, and dependencies (`uv run pytest`, `uv add`, etc.).
- **Windows File Locks (SQLite)**: On Windows, open SQLite connections lock the database file. Any cleanup (`os.remove`) must ensure connections and cursors are explicitly closed, or use pytest's `tmp_path` fixture.
- **LLM Deprecations**: Gemini models deprecate older versions (e.g. `gemini-2.0-flash` is retired with 404). Always support configurable model names via `GEMINI_MODEL` (defaulting to `gemini-3.8-flash`).

## 2. Web Scraping & Pricing Nuances
- **VB-Preis-Parsing (Kritische Nuance)**: 
  Niemals pauschal Listings `< 5€` verwerfen, ohne das Format zu prüfen! Kleinanzeigen kennt vier Preistypen:
  1. *Festpreis mit Betrag:* `200 €` -> Preis: 200.0, is_vb: False
  2. *Verhandlungsbasis mit Betrag:* `200 € VB` -> Preis: 200.0, is_vb: True (Muss erhalten bleiben!)
  3. *Reine VB ohne Betrag:* `VB` -> Preis: None/0.0, is_vb: True, needs_negotiation: True (Ggf. gesondert kennzeichnen, nicht stillschweigend droppen)
  4. *Fake-VB / Platzhalter:* `1 € VB` -> is_fake_placeholder: True (Nur diese werden für automatisierte Preis-Berechnungen gefiltert).
- **Kleinanzeigen Astro/Tailwind Overhaul**: Kleinanzeigen updated its search result frontend. Legacy classes (`article.aditem`, `.aditem-main--...`) fail silently. Modern articles have `article[data-adid][data-href]` with embedded `<script type="application/ld+json">` containing title, description, and thumbnail image.

## 3. Hybrid-Logik & Agenten-Rolle
- **Script-First mit LLM-Verification & Edit**: 
  Skripte eignen sich für schnelle Extraktion von Zahlen und Standard-Tokens, versagen aber bei semantischen Verstrickungen im Fließtext (z. B. "PC ohne GPU", "Nur Karton", unklare Bundles). 
  *Architekturregel:* Skripte vergeben Confidence-Scores und Flags; das LLM springt gezielt an, um Listings mit Unsicherheiten zu verifizieren UND falsche Skript-Extrakte aktiv zu editieren/korrigieren.
- **Komplett-PC Dekonstruktion (BOM)**:
  Komplett-PCs dürfen nicht wie Einzelteile gesucht werden. Sie benötigen eine eigene Suchspur und einen LLM-gestützten BOM-Extraktor (Bill of Materials), der verbaute Komponenten extrahiert und gegen die Hardware-Matrix monetär bewertet.
- **TPU / PCGH Rasterization Benchmark Scaling**:
  Im relativen Gaming-Performance-Index (TPU 4090 = 100) besitzen Karten wie die RTX 3070 einen Score von ~49% und RTX 3080 ~63%. Diese Skala spiegelt echte Spiele-FPS viel akkurater wider als synthetische PassMark-Punkte (wo Multi-Core-Integer-Leistung Gaming-Scores verzerrte). Schwellenwerte müssen entsprechend auf 0–100 Gaming-Index kalibriert sein.
- **Mobile/Laptop-Ausschluss durch Tier 2 Verifikation**:
  Bei der Suche nach Desktop-Grafikkarten (z. B. `RTX 3070`) tauchen auf Kleinanzeigen regelmäßig Gaming-Laptops auf. Der Tier-2 LLM-Active-Verifier identifiziert mobile Chipsätze ("Laptop mit integrierter RTX 3070") zuverlässig im Batch und schließt sie für Desktop-Builds aus.

## 4. QA & Stabilitäts-Muster (Ausfallsicherheit & Concurrency)
- **Graceful Fallback bei LLM-Ausfall (Kein Datenverlust):** Wenn ein LLM (Gemini) wegen Quota, Timeout oder 503 ausfällt, dürfen eskalierte Listings (Tier 2) nicht pauschal auf `REJECT` gesetzt werden. Stattdessen greift ein Graceful Fallback auf die Skript-Konfidenz, um Schnäppchen nicht stillschweigend zu löschen.
- **Preis-Sicherheit bei Build-Generatoren:** Listings mit `price = 0.0` (reine VB) oder `price = None` dürfen niemals als günstigste Komponente in eine Kaufempfehlung fließen. Berechnungen müssen `price > 5.0` erzwingen.
- **Windows File Locking bei Logging:** Auf Windows führen parallele Datei-Appends ohne `threading.Lock` zu Zeilenverlust (Race Conditions). Logging-Klassen (`SessionLogger`) müssen atomar gelockt werden.

## 5. UI/UX, CSV-Export & Frontend-Resilienz
- **UTF-8 BOM für Excel auf Windows:** CSV-Dateien ohne `\ufeff` (UTF-8 BOM) werden von Microsoft Excel auf Windows standardmäßig im ANSI-Zeichensatz (CP1252) geöffnet, was deutsche Umlaute zerstört (`GehÃ¤use`, `LÃ¼fter`). CSV-Exporte müssen immer `encoding="utf-8-sig"` bzw. `\ufeff` voranstellen.
- **NoneType-Schutz bei Preisen & Strings:** In UI-Renderern (`render_listing_details`, `render_build_listings`) führt `l.price > 0.0` bei `l.price is None` sofort zu einem fatalen `TypeError`. Vergleiche müssen `(l.price is not None and l.price > 0.0)` prüfen. Ebenso müssen String-Truncations (`l.title[:70]`) auf `(l.title or '')` absichern.
- **Session-State-Integrität bei Reset:** Bei einem UI-Reset (`🔄 Neue Suche starten`) darf der `active_api_key` nicht verloren gehen. `HardwareOrchestrator(api_key=active_api_key)` muss stets mit dem vorhandenen Key neu erzeugt werden.
- **Robustes Session-Log Rendering:** JSONL-Viewer dürfen nicht davon ausgehen, dass jedes Feld (`timestamp`, `data`, `event_type`) existiert und string-basiert ist. `ev.get('timestamp')` kann `None` oder `int` sein; vor Slicing (`[11:19]`) muss Typ und Vorhandensein geprüft werden (`str(ev.get('timestamp') or '')[11:19]`), und `ev` muss ein `dict` sein (`isinstance(ev, dict)`).
- **Overflow-Schutz bei VB-Berechnungen:** Bei `price = float('inf')` wirft `round()` einen `OverflowError`. Verhandlungsvorlagen müssen Preise auf finite Zahlen (`math.isfinite(price) and 10.0 <= price <= 100000.0`) begrenzen.
- **HTML-Sanitization im Chat/UI:** Titel von Kleinanzeigen enthalten Nutzer-Eingaben. Die Kombination aus `unsafe_allow_html=True` und String-Slicing (`[:70]`) riskiert defekte HTML-Tags und XSS. Titel sollten HTML-escaped (`html.escape`) gerendert werden.

## 6. Hardware-Erkennung & Regex-Schutz
- **Regex-Wortgrenzen bei Modellnamen**: Teilenummern dürfen nicht mit einfachen Substring-Matches (`in text`) geprüft werden. Beispiel: Intel Core `i7-13700K` enthält den Substring `3700`, wodurch er fälschlicherweise als AM4 (Ryzen 7 3700X) klassifiziert wurde. Wortgrenzen (`\b(Ryzen\s*7\s*3700X?)\b`) und plattformspezifische Reihenfolge sind zwingend erforderlich.
- **Keine Cross-Socket CPU-Alternativen**: `SimilarityEngine` darf bei Prozessoren niemals sockel-fremde Alternativen vorschlagen (z. B. AM4 CPU als Alternative zu Intel LGA1700), da ein CPU-Wechsel ohne Mainboard-Tausch physikalisch unmöglich ist.

## 7. Scraper-Resilienz & Fehler-Signalisierung
- **HTTP 429 Rate-Limit Propagierung**: HTTP 429 (Too Many Requests) darf niemals in generischen `except Exception:`-Blöcken im Scraper zu einer stillen leeren Liste (`[]`) verschluckt werden. Überlastungs- und Block-Signale müssen explizit per `HTTPError` oder Status-Flag an den Aufrufer (Orchestrator/UI) durchgereicht werden, damit Backoff-Strategien greifen können.
- **Europäischer CSV-Standard**: Deutsche Excel-Installationen verwenden standardmäßig das Semikolon `;` als Feldtrenner und erwarten ein UTF-8 BOM (`\ufeff`). Ein reines Komma-CSV führt dazu, dass sämtliche Spalten in Spalte A zusammengequetscht werden.

## 8. DOM-First Preisfindung & Scam-Transparenz
- **Strikter Ausschluss von Fließtext bei Preisermittlung**: In Kleinanzeigen-Suchergebnissen enthalten Beschreibungsblöcke (`.aditem-main--middle--description`, `p[class*="description"]`, `p[class*="onSurfaceSubdued"]`) häufig Währungsangaben ("Neupreis 800 €", "UVP 600 €"), die bei unachtsamer Suche nach `€` als Angebotspreis interpretiert werden. Ein striktes Ausschließen aller Beschreibungs- und Fließtextknoten sowie eine hierarchische Selektorensuche (`[data-testid="ad-price"]`, `.aditem-main--middle--price-shipping--price`, `.aditem-addon--price`, `.aditem-main--middle--price`, `p[class*="price"], span[class*="price"]`) garantiert, dass nur das echte DOM-Preiselement ausgewertet wird.
- **Transparenz statt Datenverlust bei Scam-Verdacht**: Inserate mit Defekten, OVP/Leerkartons oder Fake-Preisen (<= 5€) dürfen nicht stillschweigend gelöscht werden. Durch Einführung von `ValidationStatus.SCAM_SUSPECT` mit `is_scam_suspected = True` und detailliertem `scam_reason` bleiben diese Angebote für den Nutzer im Frontend transparent einsehbar (eingeklappter Warn-Expander), fließen aber niemals in Virtual Builds oder Deal-Rankings ein.
- **Wunschpreis-Fallback bei reiner VB**: Inserate mit reiner `VB` ohne Betrag können im Teaser oder der Volltext-Beschreibung einen konkreten Wunschpreis nennen (`r'(?i)(?:wunschpreis|festpreis|hätte\s*gerne|abzugeben\s*für|preis\s*:?)\s*(\d+(?:[.,]\d+)?)\s*€'`). Ein kontrollierter Fallback schaltet das Inserat von `needs_negotiation = True` auf `is_vb = True` mit beziffertem Preis um und kennzeichnet die Quelle via `price_source: description_fallback`.
## 9. Auto-Build Vervollständigung & Windows-Konsole
- **Deterministische 0ms-Vervollständigung statt LLM-Latenz:** Bei Eingabe unvollständiger Hardware (z.B. nur CPU oder nur GPU) liefert die Kombination aus `HardwareCatalog` (241 Teile) und `CompatibilityEngine` in 0 ms 100% kompatible, perfekt abgestimmte Setups (Budget, Sweetspot, High-End) ohne API-Tokens oder LLM-Netzwerkaufrufe zu verbrauchen.
- **Windows-Konsolen-Encoding (CP1252):** Ungefilterte Emojis (z.B. `✅`) in `print()` werfen auf Standard-Windows-Konsolen ohne gesetztes `PYTHONIOENCODING=utf-8` einen `UnicodeEncodeError`. Standalone-Testskripte sollten ASCII-Fallbacks (`[OK]`) verwenden oder explizit `sys.stdout.reconfigure(encoding='utf-8')` setzen.
- **Vollständige Indentierung bei Context-Managern:** Beim Umschließen bestehender Loops mit Metriken/Profiling (`with timer.measure(...):`) muss der gesamte innere Loop-Block eingerückt werden, um zu verhindern, dass die Schleife vorzeitig beendet wird und Logik nur für das letzte Listenelement läuft.

## 10. Performance, Concurrency & Telemetry Hardening
- **Kleinanzeigen Burst-Schutz:** Zu hohe Concurrency (`max_workers >= 5`) führt bei Kleinanzeigen / Cloudflare zuverlässig zu TCP RST (`ConnectionResetError: WinError 10054`). Begrenzung auf `max_workers = 2`, Re-Use einer Keep-Alive-Session und sanfter Jitter (`0.2s - 0.4s`) stabilisieren das Scraping vollständig.
- **Vorselektion vor Detailseiten-Fetches:** Detailseiten sollten niemals blind für alle Roh-Suchtreffer geladen werden. Ein deterministischer Teaser-Score (Preis-Korridor, Anchor-Tokens, Käuferschutz) begrenzt Volltext-Fetches auf die Top-3 Kandidaten und senkt Datenvolumen und Latenz drastisch.
- **Fail-Fast bei Gemini 504 Deadline Exceeded:** LLM Timeouts (504 / Deadline Exceeded) dürfen keine exponentiellen Retry-Schleifen auslösen, sondern müssen sofort mit sicherem Heuristik-Fallback beantwortet werden, um Multi-Minuten-Hänger zu eliminieren.

## 11. Real-User Browser Testing, Streamlit Skeletons & Multi-Line Hardening
- **Streamlit Skeleton Timing & Playwright Visibility**: `locator.count()` liefert in Playwright sofort das Ergebnis ohne zu warten. Während eines Streamlit WebSocket-Reruns (`st.rerun()`) werden Widgets kurzzeitig als pulsierende graue Platzhalter (`div[class*="stSkeleton"]`) gerendert. Tests müssen explizit auf die Sichtbarkeit des Zielelements warten (`locator.wait_for(state="visible")`) oder das Verschwinden von Skeletons abwarten, um unvollständige Screenshots oder flüchtige Fehlschläge zu verhindern.
- **Narrative Fließtext- und Disclaimer-Filterung**: Echte Kleinanzeigen-Verkäufer kopieren Benchmark-Logs (3DMark, FurMark), Temperaturangaben ("CPU-Temperatur bei Last: 60°C"), rechtliche Klauseln (AGB, Impressum, Widerruf) oder Modding-Hinweise in ihre Texte. Durch strikte Präfix-Erkennung und Disclaimer-Regex werden diese Zeilen zuverlässig als Floskeln erkannt und verfälschen nicht die Stückliste.
- **Deduplizierung singulärer Komponenten**: Inserate nennen Schlüsselkomponenten oft mehrfach (im Titel, im Einleitungssatz und in der technischen Liste). Eine strikte Singular-Kategoriendeduplizierung (maximal 1 CPU, 1 GPU, 1 Mainboard, 1 Gehäuse, 1 Netzteil, 1 Kühler) mit Priorisierung deterministischer Katalogtreffer verhindert künstliche Wertaufblähung.
- **Fokussierte Alternativen-Generierung**: Die Suche nach Alternativen für jedes Gehäuse, jeden Lüfter oder jede zweite SSD vergrößert das Suchvolumen exponentiell (27+ Suchen bei max_workers=2). Eine Begrenzung der Alternativensuchen auf Kernhardware (GPU, CPU, Mainboard) hält Markt-Scans unter 30-40s, während das Ready-to-Play Modell Lücken mit marktüblichen Richtpreisen transparent schließt.

## 12. Deal-Checker Nuances & UX Polish (Post-Test Refinements)
- **Vollständiges Hardware-Spektrum bei Ready-to-Play**:
  Viele Kleinanzeigen-Angebote listen nur GPU, CPU, RAM und SSD auf, unterschlagen aber Mainboard und Netzteil. Eine Ready-to-Play-Prüfung muss das gesamte 8-teilige Spektrum (CPU, GPU, MOTHERBOARD, RAM, STORAGE, PSU, COOLER, CASE) prüfen. Ohne Mainboard (+80€) und Netzteil (+65€) ist ein PC nicht lauffähig.
- **Mathematische Konsistenz bei fehlendem Angebotspreis**:
  Wenn kein Preis genannt wurde (`final_price <= 0`), darf der `ready_to_play_total` nicht aus `0 + zusatzaufwand` berechnet werden (was zu absurden ~80 € für einen Komplett-PC führte). In diesem Fall muss der Gesamt-Fertigstellungswert auf `total_market_value + ready_to_play_extra` basieren (~703 €).
- **Escape-Sequenzen in Python F-Strings**:
  In Nicht-Raw-Strings wird `\r` als Carriage Return (0x0D) interpretiert. `f"$\rightarrow$"` wird zu `ightarrow`. Formel-Pfeile sollten als Unicode `→` geschrieben werden.
- **Keine Schein-Metriken bei fehlendem Preis**:
  Bei unbekanntem Preis darf kein `k.A. (Festpreis)` oder ein grüner Aufwärtspfeil `↑ 0.0%` gerendert werden. Angebotspreis muss sauber als `k.A.` und Ersparnis als `—` dargestellt werden.
- **Interaktiver Nachtrags-Pfad statt toter Call-to-Action**:
  Wenn die UI den Nutzer auffordert: 'Bitte trage den Angebotspreis ein', muss direkt in der Deal-Checker-Karte ein Eingabefeld (`st.number_input`) mit Bestätigungs-Button bereitstehen, und der Chat-Input muss reine Zahlen ('650 €') als Preis-Nachtrag für den aktiven Deal erkennen, anstatt 'I didn't detect hardware parts' zu antworten.
- **Statische Import-/NameError-Prüfung bei UI-Code (`ruff check --select F821`)**:
  Streamlit-App-Code (`app.py`, `ui_components.py`) wird von reinen Engine-Pytest-Suiten oft nicht vollständig ausgeführt. Vor jedem Commit muss `uv run ruff check --select F821 hardware_crawler/ streamlit_app.py tests/` ausgeführt werden, um fehlende Imports (wie `import re`) oder `NameError` sofort abzufangen.
