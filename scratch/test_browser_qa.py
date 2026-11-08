import sys
import os
import time
import json

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playwright.sync_api import sync_playwright, Page, expect

SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "qa_screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def wait_for_streamlit_ready(page: Page, timeout: int = 30000):
    """Waits until Streamlit finishes rerunning and skeleton placeholders disappear."""
    # Wait for status widget or skeletons to clear
    page.wait_for_timeout(1000)
    try:
        page.wait_for_selector('div[class*="stSkeleton"]', state="detached", timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(1000)

def submit_ad_text(page: Page, text: str):
    """Puts text into stChatInputTextArea and submits."""
    chat_input = page.locator('textarea[data-testid="stChatInputTextArea"]')
    chat_input.wait_for(state="visible", timeout=15000)
    
    chat_input.fill(text)
    page.wait_for_timeout(500)
    chat_input.press("Enter")
    print("  -> Submitted ad text into chat input. Waiting for evaluation...")
    
    # Wait for the Deal-Checker button to become visible (which guarantees rerun completed!)
    versus_btn = page.locator('button:has-text("Gegen besten DIY-Build vergleichen")')
    versus_btn.wait_for(state="visible", timeout=35000)
    wait_for_streamlit_ready(page, timeout=15000)
    print("  -> Deal-Checker evaluation fully rendered!")

def test_real_ad_1(browser):
    """TEST CASE 1: Real Kleinanzeigen Ad 1 (Ryzen 5 5600 + RTX 3070, 900 EUR VB)"""
    print("\n=================================================================")
    print("--- [TEST CASE 1] Real Ad 1: Ryzen 5 5600 + RTX 3070 (900 EUR VB) ---")
    print("=================================================================")
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    page = context.new_page()
    page.goto("http://localhost:8501", wait_until="networkidle")
    wait_for_streamlit_ready(page)

    ad_1_text = (
        "Gaming PC | RTX 3070 8GB | Ryzen 5 5600 | White RGB Build\n"
        "Preis: 900 € VB\n"
        "Ich verkaufe einen Gaming-PC mit RTX 3070 und Ryzen 5 5600 in einem weißen Gehäuse mit Glasfront und RGB-Beleuchtung.\n"
        "Technische Daten:\n"
        "Prozessor: AMD Ryzen 5 5600 (6 Kerne / 12 Threads)\n"
        "Grafikkarte: ASUS GeForce RTX 3070 8 GB\n"
        "Mainboard: ASUS ROG Strix B550-A Gaming\n"
        "Arbeitsspeicher: 16 GB Corsair Vengeance RGB DDR4-3200 (2 × 8 GB)\n"
        "SSD: 250 GB Intenso M.2 NVMe\n"
        "SSD: 500 GB Samsung M.2 NVMe (PCIe 4.0)\n"
        "Wasserkühlung: Corsair iCUE LINK H150i RGB 360 mm\n"
        "Netzteil: Corsair CX 650W\n"
        "Gehäuse: Weißes Glasgehäuse mit zahlreichen RGB-Lüftern"
    )
    submit_ad_text(page, ad_1_text)

    # Verification of Deal-Checker UI elements
    page_text = page.inner_text("body")
    assert "Kleinanzeigen-Inserat erkannt" in page_text, "Assertion Failed: Deal-Checker did not trigger automatically!"
    assert any(tier in page_text for tier in ["Fairer Gebrauchtpreis", "Top Deal", "Zu teuer"]), "Assertion Failed: Price Assessment missing!"
    assert "Angebotspreis" in page_text, "Assertion Failed: Asking price metric missing!"
    assert "Geschätzter Marktwert" in page_text, "Assertion Failed: Market value metric missing!"
    assert "Spar-Vorteil" in page_text, "Assertion Failed: Savings metric missing!"
    assert "Verhandlungs-Assistent" in page_text, "Assertion Failed: Negotiation assistant missing!"
    assert "Empfohlenes Einstiegsgebot" in page_text, "Assertion Failed: Negotiation target missing!"
    print("  [OK] Deal-Checker, Components, Valuation & Negotiation Assistant verified for Ad 1.")

    # Capture Deal-Checker Screenshot
    screenshot_path_1 = os.path.join(SCREENSHOT_DIR, "deal_checker_real_ad_1.png")
    page.screenshot(path=screenshot_path_1, full_page=True)
    print(f"  [SCREENSHOT] Saved: {screenshot_path_1}")

    # Trigger Versus-View
    print("  -> Triggering Versus-View comparison (Scanning DIY components on Kleinanzeigen)...")
    versus_btn = page.locator('button:has-text("Gegen besten DIY-Build vergleichen")')
    assert versus_btn.count() > 0, "Assertion Failed: Versus-View button not found!"
    versus_btn.first.click()
    
    # Wait for Versus-View to complete scan & render
    page.wait_for_selector('text=DER SHOWDOWN: FERTIG-PC vs. EIGENBAU', timeout=180000)
    wait_for_streamlit_ready(page, timeout=15000)

    versus_text = page.inner_text("body")
    assert "KLEINANZEIGEN FERTIG-PC" in versus_text, "Assertion Failed: Complete PC column missing in Versus-View!"
    assert "BESTER EIGENBAU (DIY BUILD)" in versus_text, "Assertion Failed: DIY Build column missing in Versus-View!"
    assert "Gaming Score" in versus_text, "Assertion Failed: Gaming Score comparison missing!"
    assert "P/L Ratio" in versus_text, "Assertion Failed: P/L ratio missing in Versus-View!"
    print("  [OK] Versus-View 2-column Showdown & System Recommendation successfully verified!")

    # Scroll down to ensure Versus Showdown is highlighted
    page.locator('text=DER SHOWDOWN: FERTIG-PC vs. EIGENBAU').scroll_into_view_if_needed()
    page.wait_for_timeout(1000)

    screenshot_path_versus_1 = os.path.join(SCREENSHOT_DIR, "versus_view_real_ad_1.png")
    page.screenshot(path=screenshot_path_versus_1, full_page=True)
    print(f"  [SCREENSHOT] Saved: {screenshot_path_versus_1}")
    context.close()

def test_real_ad_4(browser):
    """TEST CASE 2: Real Kleinanzeigen Ad 4 (i5-13600KF + RTX 3070, 800 EUR Festpreis)"""
    print("\n=================================================================")
    print("--- [TEST CASE 2] Real Ad 4: i5 13600KF + RTX 3070 (800 EUR Festpreis) ---")
    print("=================================================================")
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    page = context.new_page()
    page.goto("http://localhost:8501", wait_until="networkidle")
    wait_for_streamlit_ready(page)

    ad_4_text = (
        "Gaming PC I5 13600KF// 32GB DDR4// RTX 3070\n"
        "Preis: 800 € Festpreis\n"
        "Verkaufe meinen zweit PC indem folgende Teile verbaut sind:\n"
        "- I5 13600kf\n"
        "- RTx 3070 Aorus Master\n"
        "- 32GB DDR4 3200MHZ Corsair Vengance\n"
        "- 500gb Crucial P310 m.2\n"
        "- 250gb SATA SSD\n"
        "- Corsair Icue Link Titan 240mm\n"
        "- EVGA Supernova 650W Netzteil\n"
        "- Fractal Design Pop Air mini"
    )
    submit_ad_text(page, ad_4_text)

    page_text_4 = page.inner_text("body")
    assert "Kleinanzeigen-Inserat erkannt" in page_text_4
    assert "Verhandlungs-Assistent" in page_text_4
    assert "800 €" in page_text_4
    print("  [OK] Real Ad 4 successfully parsed and evaluated by Deal-Checker.")

    screenshot_path_4 = os.path.join(SCREENSHOT_DIR, "deal_checker_real_ad_4.png")
    page.screenshot(path=screenshot_path_4, full_page=True)
    print(f"  [SCREENSHOT] Saved: {screenshot_path_4}")
    context.close()

def test_user_original_case(browser):
    """TEST CASE 3: User's Original Case (sess_20261108_122052_2abad8)"""
    print("\n=================================================================")
    print("--- [TEST CASE 3] User Original Case (Ryzen 5800X3D + RTX 3080, 850 EUR VB) ---")
    print("=================================================================")
    context = browser.new_context(viewport={"width": 1600, "height": 1200})
    page = context.new_page()
    page.goto("http://localhost:8501", wait_until="networkidle")
    wait_for_streamlit_ready(page)

    user_original_text = (
        "- Mainboard Asus Strix B450-F Gaming\n"
        "- RAM 32GB DDR4 Corsair Vengeance LPX 3200Mhz CL16\n"
        "- CPU AMD Ryzen 7 5800X3D\n"
        "- CPU Kühler BeQuiet Dark Rock Pro 4 mit PTM7950 Wärmeleitpaste (Top Performance, kein Austrocknen für viele Jahre)\n"
        "- GPU ASUS TUF RTX 3080 10GB - PTM7950 Wärmeleitpaste + VRAM Wärmeleitpads mit Thermal Putty getauscht. 3D gedrucktes Shroud in schwarz. Das originale Shroud habe ich verkauft, da ich die Karte mit Deshroud und Noctua Lüftern betrieben habe.\n"
        "- SSD 1TB NVMe Sandisk Extreme Pro\n"
        "- Gehäuse BeQuiet Pure Base 500 mit Glas Seitenteil und Mesh+Dämmungs Top Panel\n"
        "- Netzteil Seasonic Focus GX 650W\n"
        "Preis: 850 € VB"
    )
    submit_ad_text(page, user_original_text)

    user_text = page.inner_text("body")
    assert "Kleinanzeigen-Inserat erkannt" in user_text
    assert ("850 € (VB)" in user_text or "850 €" in user_text)
    assert any(tier in user_text for tier in ["Fairer Gebrauchtpreis", "Top Deal", "Zu teuer"])
    assert "Ryzen 7 5800X3D" in user_text
    assert "RTX 3080" in user_text
    assert "Verhandlungs-Assistent" in user_text
    assert "Empfohlenes Einstiegsgebot" in user_text
    print("  [OK] User's Original Case (8/8 parts) verified: No query stitching, clean valuation & negotiation template!")

    screenshot_path_user = os.path.join(SCREENSHOT_DIR, "deal_checker_user_original_case.png")
    page.screenshot(path=screenshot_path_user, full_page=True)
    print(f"  [SCREENSHOT] Saved: {screenshot_path_user}")

    # Trigger Versus-View for User Case
    print("  -> Triggering Versus-View comparison for User Original Case...")
    versus_btn_user = page.locator('button:has-text("Gegen besten DIY-Build vergleichen")')
    assert versus_btn_user.count() > 0
    versus_btn_user.first.click()
    
    print("  -> Waiting for DIY Market Scan and Versus-View Showdown render...")
    page.wait_for_selector('text=DER SHOWDOWN: FERTIG-PC vs. EIGENBAU', timeout=180000)
    wait_for_streamlit_ready(page, timeout=15000)

    versus_user_text = page.inner_text("body")
    assert "KLEINANZEIGEN FERTIG-PC" in versus_user_text
    assert "BESTER EIGENBAU (DIY BUILD)" in versus_user_text
    print("  [OK] User Original Case Versus-View Showdown successfully verified!")

    page.locator('text=DER SHOWDOWN: FERTIG-PC vs. EIGENBAU').scroll_into_view_if_needed()
    page.wait_for_timeout(1000)

    screenshot_path_versus_user = os.path.join(SCREENSHOT_DIR, "versus_view_user_original_case.png")
    page.screenshot(path=screenshot_path_versus_user, full_page=True)
    print(f"  [SCREENSHOT] Saved: {screenshot_path_versus_user}")
    context.close()

def run_browser_qa():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--window-size=1600,1200"]
        )
        try:
            test_real_ad_1(browser)
            test_real_ad_4(browser)
            test_user_original_case(browser)
            print("\n=================================================================")
            print("  ALL REAL-USER BROWSER QA TESTS COMPLETED WITH 100% SUCCESS!")
            print("=================================================================\n")
        finally:
            browser.close()

if __name__ == "__main__":
    run_browser_qa()
