import sys
import os
import time

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import streamlit.components.v1 as components
from hardware_crawler.ui_components import (
    render_chat_message, render_sidebar_summary,
    render_component_list_md, render_scan_results_md,
    render_listing_details, render_build_details,
    render_build_listings, render_build_proposals,
    render_telemetry_summary
)
from hardware_crawler.orchestrator import HardwareOrchestrator

# Page Config
st.set_page_config(page_title="Hardware Agent 2.0", page_icon="🕵️", layout="wide")

def inject_browser_telemetry():
    """Lightweight client-side telemetry: captures window.onerror, unhandled rejections and resource timings."""
    components.html(
        """
        <script>
        (function() {
            if (window._hw_telemetry_installed) return;
            window._hw_telemetry_installed = true;

            // Global Error Logging
            window.onerror = function(message, source, lineno, colno, error) {
                console.error("[HardwareAgent Browser Error]", {
                    message: message,
                    source: source,
                    lineno: lineno,
                    colno: colno,
                    error: error ? error.stack : null,
                    timestamp: new Date().toISOString()
                });
            };

            window.addEventListener('unhandledrejection', function(event) {
                console.error("[HardwareAgent Unhandled Rejection]", {
                    reason: event.reason,
                    timestamp: new Date().toISOString()
                });
            });

            // Resource & Navigation Timing Profiling
            if (window.performance && window.performance.getEntriesByType) {
                window.addEventListener('load', function() {
                    setTimeout(function() {
                        const navEntries = performance.getEntriesByType('navigation');
                        const nav = navEntries.length > 0 ? navEntries[0] : null;
                        if (nav) {
                            console.info("[HardwareAgent Client Timing]", {
                                domReady: Math.round(nav.domContentLoadedEventEnd - nav.startTime) + "ms",
                                pageLoad: Math.round(nav.loadEventEnd - nav.startTime) + "ms",
                                transferSizeKB: (nav.transferSize / 1024).toFixed(1) + " KB"
                            });
                        }
                    }, 500);
                });
            }
        })();
        </script>
        """,
        height=0,
        width=0
    )

def get_orchestrator(api_key: str = None) -> HardwareOrchestrator:
    """Get or create the orchestrator in session state."""
    if "orchestrator" not in st.session_state or st.session_state.get("current_api_key") != api_key:
        st.session_state.orchestrator = HardwareOrchestrator(api_key=api_key)
        st.session_state.current_api_key = api_key
    return st.session_state.orchestrator

def main():
    # Inject browser-side telemetry
    inject_browser_telemetry()

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
    if st.session_state.scan_complete:
        # Telemetry Summary Card
        latest_report = st.session_state.get("latest_report")
        telemetry = latest_report.get("telemetry") if latest_report else None
        if not telemetry and getattr(orch, "session_logger", None):
            telemetry = {
                "traffic": orch.traffic_monitor.get_summary(),
                "performance": orch.perf_timer.get_summary()
            }
        render_telemetry_summary(telemetry)

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
        
        tab1, tab2, tab3, tab4 = st.tabs(["🏷️ Einzelteile-Börse", "💰 Preis-Leistung (Setups)", "🖥️ Komplett-PCs", "📜 Session Log"])
        
        with tab1:
            render_listing_details(orch.listings_map, orch.specs)
            
        with tab2:
            if orch.latest_build:
                render_build_details(orch.latest_build)
            else:
                st.info("Konnte kein vollständiges Setup generieren. Eventuell fehlen Schlüssel-Komponenten (GPU/CPU) in den Ergebnissen.")
                
        with tab3:
            render_build_listings(orch.build_listings)

        with tab4:
            st.markdown("### 📜 Session-Audit & Verifikations-Protokoll")
            if orch.session_logger and orch.session_logger.log_file.exists():
                from hardware_crawler.logging_session import SessionLogger
                events = SessionLogger.read_session_events(orch.session_logger.log_file)
                st.caption(f"Session-ID: `{orch.session_logger.session_id}` • {len(events)} protokollierte Ereignisse")
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    ts_raw = ev.get('timestamp')
                    ts_str = str(ts_raw or '')
                    ts_display = ts_str[11:19] if len(ts_str) >= 19 else ts_str
                    event_type = ev.get('event_type', 'unbekannt')
                    with st.expander(f"⏱️ {ts_display} — {event_type}", expanded=False):
                        st.json(ev.get("data", {}))
            else:
                st.info("Noch kein Session-Log aufgezeichnet.")
            
    # Scan Market Action Area (Proposals or Standard Scan)
    if orch.specs and not st.session_state.scan_complete:
        if orch.is_partial_intent and orch.build_proposals:
            selected_tier = render_build_proposals(orch.build_proposals)
            if selected_tier:
                orch.apply_build_proposal(selected_tier)
                run_scan(orch)
                st.rerun()

            st.markdown("---")
            st.caption("Oder ohne automatische Build-Vervollständigung direkt nach deinen angegebenen Teilen suchen:")
            if st.button("🔍 Nur meine eingegebenen Teile scannen", key="scan_raw_parts", use_container_width=True):
                run_scan(orch)
                st.rerun()
        else:
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
        
        # Reset Button (preserves API key)
        if col2.button("🔄 Neue Suche starten", type="primary", use_container_width=True):
            from hardware_crawler.orchestrator import HardwareOrchestrator
            st.session_state.orchestrator = HardwareOrchestrator(api_key=active_api_key)
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
                if orch.is_partial_intent and orch.build_proposals:
                    response_text = comp_md + "\n\n💡 **Einzelkomponente erkannt!** Wir haben 3 optimal abgestimmte Gaming-Setups (Budget, Mittelklasse, High-End) für dich kalkuliert. Wähle unten dein bevorzugtes Setup für den 1-Klick-Marktsuchlauf!"
                else:
                    response_text = comp_md + "\n\n*Klicke unten auf '🚀 Scan Market', um Kleinanzeigen zu durchsuchen!*"
            else:
                response_text = "I didn't detect specific hardware parts. Try listing components like 'RTX 5070 Ti' or 'Ryzen 7800X3D'."
                st.markdown(response_text)
            
            st.session_state.messages.append({"role": "assistant", "content": response_text})
        
        st.rerun()


def run_scan(orch: HardwareOrchestrator):
    """Run market scan with live elapsed time progress display and telemetry capture."""
    start_time = time.time()
    progress_bar = st.progress(0, text="⏱️ 0.0s | Starte Markt-Scan...")
    status_text = st.empty()
    
    def on_progress(pct, spec_name):
        elapsed = time.time() - start_time
        progress_bar.progress(min(pct, 1.0), text=f"⏱️ {elapsed:.1f}s | Scanne Kleinanzeigen für {spec_name}...")
    
    report = orch.run_market_scan(progress_callback=on_progress)
    elapsed_total = time.time() - start_time
    
    progress_bar.progress(1.0, text=f"✅ Scan abgeschlossen in {elapsed_total:.1f}s!")
    time.sleep(0.5)
    progress_bar.empty()
    status_text.empty()
    
    # Store latest report with telemetry for UI rendering
    st.session_state.latest_report = report
    
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
