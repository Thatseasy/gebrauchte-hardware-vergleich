import sys
import os
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from hardware_crawler.ui_components import (
    render_chat_message, render_sidebar_summary,
    render_component_list_md, render_scan_results_md,
    render_listing_details, render_build_details,
    render_build_listings
)
from hardware_crawler.orchestrator import HardwareOrchestrator

# Page Config
st.set_page_config(page_title="Hardware Agent 2.0", page_icon="🕵️", layout="wide")

def get_orchestrator(api_key: str = None) -> HardwareOrchestrator:
    """Get or create the orchestrator in session state."""
    if "orchestrator" not in st.session_state or st.session_state.get("current_api_key") != api_key:
        st.session_state.orchestrator = HardwareOrchestrator(api_key=api_key)
        st.session_state.current_api_key = api_key
    return st.session_state.orchestrator

def main():
    # --- Session State Initialization ---
    if "messages" not in st.session_state:
        intro_text = (
            "👋 Hi! Wir suchen jetzt nach den besten Angeboten zu den angegebenen Komponenten sowie Alternativen dazu, "
            "die genauso gut sind, kompatibel und möglicherweise zu besseren Preisen verfügbar sind.\n\n"
            "Dazu suchen wir komplette PCs, die deine gesuchten Komponenten zum Teil oder ganz haben, "
            "und aus den gefundenen Einzelteilen stellen wir dir die besten Preis-Leistungs-Setups zusammen."
        )
        st.session_state.messages = [
            {"role": "assistant", "content": intro_text}
        ]
    
    if "scan_complete" not in st.session_state:
        st.session_state.scan_complete = False

    # --- Sidebar: API Access & Status ---
    with st.sidebar:
        st.title("🔑 API Access")
        user_api_key = st.text_input(
            "Gemini API Key", 
            type="password", 
            help="Hole dir einen kostenlosen Key auf aistudio.google.com"
        )
        # Fallback to local .env if frontend input is empty
        active_api_key = user_api_key if user_api_key else os.getenv("GEMINI_API_KEY")
        
        orch = get_orchestrator(active_api_key)
        
        st.divider()
        st.title("🖥️ Build Status")
        build_price = orch.latest_build.total_price if orch.latest_build else 0.0
        render_sidebar_summary(orch.specs, build_price)
        
        if orch.specs:
            st.divider()
            st.caption("Components:")
            for s in orch.specs:
                st.caption(f"• {s.name}")
        
        st.divider()
        st.warning("🚨 **Sicherheitshinweis:**\nZahle NIEMALS per PayPal Freunde oder Banküberweisung! Viele Betrüger auf Kleinanzeigen unterwegs.")

    # --- Main Chat Interface ---
    st.header("💬 Hardware Expert Agent")
    
    # Optional Missing Key Blocker
    if not active_api_key:
        st.error("🔒 **Zugriff gesperrt:** Bitte trage deinen Gemini API Key in der linken Seitenleiste ein, um den Hardware Agenten zu nutzen.")
        return

    
    # Render History
    for msg in st.session_state.messages:
        render_chat_message(msg["role"], msg["content"])
    


    # Render scan results details after the last assistant message
    if st.session_state.scan_complete and (orch.listings_map or orch.build_listings):
        # Größere Tabs via CSS
        st.markdown(
            """
            <style>
            .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
                font-size: 1.5rem;
                font-weight: 600;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        tab1, tab2, tab3 = st.tabs(["🏷️ Einzelteile-Börse", "💰 Preis-Leistung (Setups)", "🖥️ Komplett-PCs"])
        
        with tab1:
            render_listing_details(orch.listings_map, orch.specs)
            
        with tab2:
            if orch.latest_build:
                render_build_details(orch.latest_build)
            else:
                st.info("Konnte kein vollständiges Setup generieren. Eventuell fehlen Schlüssel-Komponenten (GPU/CPU) in den Ergebnissen.")
                
        with tab3:
            render_build_listings(orch.build_listings)
            
    # Scan Market Button (only if specs exist and no scan yet)
    if orch.specs and not st.session_state.scan_complete:
        if st.button("🚀 Scan Market", type="primary", use_container_width=True):
            run_scan(orch)
            st.rerun()

    # User Action Area (Chat Input or Reset/Export Options)
    if st.session_state.scan_complete:
        st.divider()
        st.markdown("### 🎯 Suche abgeschlossen")
        st.info("Damit sich alte Suchergebnisse nicht mit neuen vermischen, ist die aktuelle Session abgeschlossen.")
        
        col1, col2 = st.columns(2)
        # CSV Export
        from hardware_crawler.ui_components import generate_csv_export
        csv_data = generate_csv_export(orch.listings_map)
        
        col1.download_button(
            label="📥 Ergebnisse als CSV herunterladen",
            data=csv_data,
            file_name="hardware_deals.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # Reset Button
        if col2.button("🔄 Neue Suche starten", type="primary", use_container_width=True):
            from hardware_crawler.orchestrator import HardwareOrchestrator
            st.session_state.orchestrator = HardwareOrchestrator()
            intro_text = (
                "👋 Hi! Wir suchen jetzt nach den besten Angeboten zu den angegebenen Komponenten sowie Alternativen dazu, "
                "die genauso gut sind, kompatibel und möglicherweise zu besseren Preisen verfügbar sind.\n\n"
                "Dazu suchen wir komplette PCs, die deine gesuchten Komponenten zum Teil oder ganz haben, "
                "und aus den gefundenen Einzelteilen stellen wir dir die besten Preis-Leistungs-Setups zusammen."
            )
            st.session_state.messages = [{"role": "assistant", "content": intro_text}]
            st.session_state.scan_complete = False
            st.rerun()
            
    elif prompt := st.chat_input("Describe your build or components..."):
        # Add User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        render_chat_message("user", prompt)
        
        # Process with Orchestrator
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your components..."):
                added_names = orch.process_user_intent(prompt)
            
            if added_names:
                # Show parsed components
                comp_md = render_component_list_md(orch.specs)
                st.markdown(comp_md)
                response_text = comp_md + "\n\n*Click '🚀 Scan Market' below to find deals!*"
            else:
                response_text = "I didn't detect specific hardware parts. Try listing components like 'RTX 5070 Ti' or 'Ryzen 7800X3D'."
                st.markdown(response_text)
            
            st.session_state.messages.append({"role": "assistant", "content": response_text})
        
        st.rerun()


def run_scan(orch: HardwareOrchestrator):
    """Run market scan with progress display."""
    progress_bar = st.progress(0, text="Starting scan...")
    status_text = st.empty()
    
    def on_progress(pct, spec_name):
        progress_bar.progress(min(pct, 1.0), text=f"Scanning: {spec_name}...")
    
    report = orch.run_market_scan(progress_callback=on_progress)
    
    progress_bar.progress(1.0, text="✅ Scan Complete!")
    time.sleep(0.5)
    progress_bar.empty()
    status_text.empty()
    
    # Build results message
    results_md = render_scan_results_md(orch.listings_map, orch.specs, orch.latest_build)
    
    # Add alternatives info if any
    alts = report.get("alternatives_found", {})
    if alts:
        results_md += "\n\n**💡 Alternative Suggestions:**\n"
        for spec_name, alt_list in alts.items():
            results_md += f"- {spec_name}: {', '.join(alt_list)}\n"
    
    st.session_state.messages.append({"role": "assistant", "content": results_md})
    st.session_state.scan_complete = True


if __name__ == "__main__":
    main()
