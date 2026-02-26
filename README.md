# 🕵️ Hardware Deal Finder 2.0

An agentic pipeline designed to find, verify, and rank hardware deals from classified ads (Kleinanzeigen) with high precision using **Entity Resolution** and **Statistical Price Analysis**.

## 🏗️ Architecture: The 4-Agent Pipeline

The application works through a sequential multi-agent process to ensure only relevant and high-value deals are presented.

1.  **PartsInput Agent (Canonicalization)**: 
    *   Takes raw user input (e.g., "RTX 3070 Ti") and converts it into a **Canonical Specification**.
    *   Generates optimized search queries and identifies "must-have" tokens and "exclusion" tokens.
2.  **MarketFetch Agent (Scraper)**:
    *   Executes high-precision searches on Kleinanzeigen using the spec's optimized queries.
    *   Handles location filters and radius searches.
3.  **ListingVerification Agent (Entity Resolution)**:
    *   Cross-references every raw listing against the Canonical Spec.
    *   Extracts attributes (e.g., VRAM, model variations) and assigns a confidence score.
    *   Filters out "search requests", "defective items", and "unrelated hardware".
4.  **Pricing & Ranking Agent**:
    *   Calculates statistical market metrics (Median, Median Absolute Deviation).
    *   Identifies price outliers and predicts "fair price" ranges.
    *   Detects high-risk signals (scam suspicion, suspicious pricing).
    *   Ranks listings based on value-for-money and listing quality.

## 🚀 Features

-   **Precision Filtering**: Nativer Ausschluss von "Gesuche" Anzeigen via URL-Params (`anzeige:angebote/`) und Blocklisten für unbeliebtes Zubehör (OVP, Sticker, Defekte).
-   **Statistical Analysis**: Real-time market stats showing if a deal is actually a bargain.
-   **Scam Protection (60% Median)**: Erkennt und warnt vor unrealistischen 1€-Lockangeboten und Angeboten, die >60% unter dem Markt-Median liegen.
-   **CSV Export**: Speichere deine fertig gefilterten Builds und gefundenen Einzelteile als Excel-kompatible `.csv` Datei lokal ab.
-   **Live-Deployment Ready**: Bietet ein sicheres Sidebar-Eingabefeld für User-eigene Gemini API-Keys – so hostest du die App kostenlos für andere, ohne deine eigenen API-Limits zu verbrauchen.
-   **Anti-Bot Evasion**: Uses `cloudscraper` to accurately scrape classified sites without being silently blocked by standard WAFs.
-   **Database Integration**: Automatically saves verified deals for later review.
-   **Modern UI**: Comprehensive Streamlit dashboard showing the pipeline stages.

## 🧠 AI-Powered Features (Hybrid Mode)
The application now supports optional AI agents for enhanced intelligence:

-   **HardwareIntentAgent (LLM)**: Understands natural language inputs (e.g., "Intel Ultra 7 without box") better than regex.
-   **HardwareKnowledgeAgent (LLM)**:
    -   **Alternatives**: Suggests comparable hardware (e.g., "RX 6800" for "RTX 3070").
    -   **Gap Analysis**: Suggests missing components (PSU, Motherboard) for your build.

To enable these features, rename `.env.template` to `.env` and add an API key (Gemini, OpenAI, or use local Ollama).

## 🛠️ Installation

1.  Clone the repository and install dependencies:
    Using `uv` (recommended):
    ```bash
    uv pip install -r requirements.txt
    ```
    Alternatively:
    ```bash
    pip install -r requirements.txt
    ```

2.  (Optional) Setup AI:
    ```bash
    cp .env.template .env
    # Edit .env with your keys
    ```

3.  Run the application:
    Using `uv` (recommended):
    ```bash
    uv run streamlit run hardware_crawler/app.py
    ```
    Alternatively:
    ```bash
    streamlit run hardware_crawler/app.py
    ```

## 🧪 Development

You can verify the pipeline logic using the standalone test script:
```bash
python verify_refactor.py
```

### Workflows (via Antigravity)

*   **/dev-test-debug**: Standard cycle for coding, testing, and UI validation.
*   **/dev-test-debug-log**: Advanced mode with persistent project memory and detailed logging.
*   **/log**: Consolidate session progress into memory, backlog, and documentation.
*   **/create-log-logic**: Bootstraps the logging logic (~/.agent structure) into a project.

---
*Developed as part of the Hardware Crawler Refactor.*
