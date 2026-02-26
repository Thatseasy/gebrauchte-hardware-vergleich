# 🚀 Live Deployment Guide

Da der Crawler nun so gebaut ist, dass er keine zentralen API-Key-Kosten verursacht (User geben ihren eigenen Gemini-Key in das bereitgestellte Sidebar-Feld ein), ist er perfekt geeignet, um ihn kostenlos auf **Streamlit Community Cloud** zu hosten.

Mit dieser Methode hast du innerhalb von 3 Minuten eine Live-URL, die du deinen 20-40 Tester-Nutzern schicken kannst.

## 1. Voraussetzungen
- Dein aktueller Code (inklusive der `requirements.txt`) muss auf **GitHub** (in einem public oder private Repository) liegen.
- Du brauchst einen (kostenlosen) Account bei [share.streamlit.io](https://share.streamlit.io/).

## 2. Deployment auf Streamlit Community Cloud (Empfohlen & Kostenlos)

Die Streamlit Cloud ist die einfachste Methode, da sie direkt für solche Apps gemacht ist.

1. Gehe auf [share.streamlit.io](https://share.streamlit.io/) und logge dich mit deinem GitHub-Account ein.
2. Klicke oben rechts auf **"New app"**.
3. Bestätige den Zugriff auf deine GitHub Repositories.
4. Fülle das kleine Formular aus:
   - **Repository:** Wähle dein Repository aus (z.B. `Thatseasy/kleinanzeigen_hardware_crawler`).
   - **Branch:** `main` (Stelle sicher, dass du unsere neu entwickelten Branches via Pull-Request in deinen `main` Branch gemerged hast!).
   - **Main file path:** Trage hier den Pfad ein: `hardware_crawler/app.py`.
   - **App URL:** Denke dir einen schönen Namen aus (z.B. `gaming-pc-crawler`).
5. Klicke auf **Deploy!**

Streamlit liest nun automatisch deine `requirements.txt`, installiert alle Pakete (inklusive `google-generativeai` und `cloudscraper`) und startet den Server. Nach 1-2 Minuten erhältst du deine fertige, öffentliche URL.

## 3. Sicherheits-Informationen für Nutzer
Wenn deine Tester den Link öffnen, werden sie unten im Chat von einem roten Hinweis blockiert. 
Sie müssen Folgendes tun:
1. Links in der Seitenleiste unter **API Access** ihren eigenen API-Key eintragen.
2. Einen kostenlosen API-Key bekommt man mit 2 Klicks (Google Account vorausgesetzt) unter: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
3. Sobald der Key im Feld steht, verschwindet die rote Sperre und sie können die Suche starten.

> **Wichtig:** Streamlit sichert die Sessions automatisch (`st.session_state`). Wenn Nutzer A seinen Key eingibt, kann Nutzer B (der parallel die Seite öffnet) diesen Key **nicht** sehen oder nutzen. Jeder Nutzer läuft in einem sicheren "Sandbox-Thread".

## 4. Troubleshooting: Cloudscraper vs. Captchas
Der Hardware-Crawler nutzt `cloudscraper`, um die "Cloudflare"-Blockaden von eBay-Kleinanzeigen zu umgehen. Das funktioniert lokal hervorragend.
Sollten Serverseitig (nach dem Streamlit-Deployment) plötzliche `403 Forbidden` Scraping-Fehler auftreten, bedeutet das, dass Kleinanzeigen die IP-Adressen der nordamerikanischen Streamlit-Server auf die harte Blocklist gesetzt hat.
*Sollte das passieren, müssten wir ein kleines Proxy-Netzwerk in `scrapers.py` nachrüsten, was für den Start aber meistens nicht nötig ist.*

## Alternative Hosting-Methoden
Falls du vollen Serverzugriff möchtest (z.B. um Logs auf der Festplatte zu speichern), empfiehlt sich ein klassischer **VPS (Virtual Private Server)** z.B. bei Hetzner für ca. 4€/Monat:
1. Server mieten (Ubuntu 24.04).
2. Repo clonen.
3. Python Virtualenv erstellen und via `uv pip install -r requirements.txt` Abhängigkeiten installieren.
4. App via `nohup streamlit run hardware_crawler/app.py --server.port 80 &` dauerschleifig laufen lassen.
