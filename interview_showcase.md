# 🚀 Hardware Deal Finder 2.0 – Technisches 2-Minuten Showcase Skript

*Dieses Skript ist exakt auf 2 Minuten Sprechzeit ausgelegt (ca. 240 Wörter) und rückt die architektonischen und technischen Aspekte (Data Engineering, Multi-Agent System, WAF-Evasion) in den Vordergrund.*

---

### [0:00 - 0:25] Architektur-Vision & Problemstellung
**(Du teilst deinen Bildschirm, man sieht das Start-Dashboard bzw. Architektur-Diagramm)**

💬 *"Hallo zusammen. Ich präsentiere den Hardware Deal Finder 2.0. Das primäre Ziel des Projekts war es, eine robuste Data-Pipeline zu bauen, die Rauschen und Scam auf classified Boards algorithmisch herausfiltert. Um hohe Präzision zu garantieren, habe ich eine sequentielle Multi-Agenten-Architektur in Python entwickelt. Statt auf fehleranfällige Regex-Ketten zu setzen, nutze ich LLM-gestütztes Parsing und statistische Entity Resolution."*

### [0:25 - 0:55] Parsing & WAF Evasion (Live-Demo Start)
**(Du klickst in das Suchfeld, gibst "RTX 3070" ein und startest die Suche)**

💬 *"Lassen Sie uns den Durchstich live ansehen: Ich suche nach einer RTX 3070. Im ersten Schritt greift der 'Hardware Intent Agent'. Er zwingt das LLM über strikte JSON-Schemas, den unstrukturierten Input in validierte Pydantic-Models zu überführen. Anschließend übernimmt der Scraper. Hier setze ich auf die Request-Bibliothek Cloudscraper, um gängige Web Application Firewalls und Bot-Protections zuverlässig und performant zu umgehen."*

### [0:55 - 1:25] Entity Resolution & Statistical Pricing
**(Du zeigst kurz auf die aktiven Agenten-Logs in der UI)**

💬 *"Sobald die Rohdaten vorliegen, startet der Verification-Agent. Er führt eine Entity Resolution auf den Titeln und Descriptions durch. Er erkennt den semantischen Kontext und verwirft False-Positives, wie OVP oder Defekte, mit einem ermittelten Confidence-Score. Im Kernstück greift danach die Pricing-Engine: Sie berechnet in Echtzeit den Median der validierten Datenpunkte. Angebote, die mehr als 60 Prozent unter diesem Median liegen, droppen wir hart, um Scam deterministisch zu blockieren."*

### [1:25 - 2:00] Output & Tech-Stack
**(Das Ergebnis lädt. Du zeigst die bereinigte Liste, die Mediane und Warnings)**

💬 *"Hier ist das bereinigte Ergebnis: Statistische Sicherheit und via 'Compatibility Engine' bekommen wir direkt Warnungen bei falschen CPU-Sockets. Das Frontend ist eine reaktive Streamlit-App. Das komplette Dependency-Management läuft über den schnellen Rust-Paketmanager `uv`. Durch die 'Bring-Your-Own-Key' Architektur für die LLM-Schnittstelle ist die Applikation zudem völlig zustandslos und damit ready für ein Zero-Cost Cloud-Deployment. Ich freue mich auf Ihre Fragen zur Code-Basis."*

---

### 📝 Vorbereitung am Tag des Interviews:
1. **App starten:** Stelle sicher, dass die App lokal läuft (`uv run streamlit run hardware_crawler/app.py`).
2. **Tab offen lassen:** Habe das Fenster im Browser schon bereit, um direkt loszulegen.
3. **Generalprobe:** Lies den Text 2-3 Mal mit gestoppter Zeit laut vor. Die Fachbegriffe (Entity Resolution, Pydantic, WAF) sollten flüssig über die Lippen gehen.
