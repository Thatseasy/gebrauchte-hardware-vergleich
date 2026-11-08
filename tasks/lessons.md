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



