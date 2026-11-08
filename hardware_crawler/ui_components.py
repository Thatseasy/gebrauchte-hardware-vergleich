import html
import math
import streamlit as st
import pandas as pd
from typing import List, Optional, Dict, Any
from .models import CanonicalSpec, ComponentType, Listing, ValidationStatus, Build

def generate_csv_export(listings_map: Dict[str, List[Listing]]) -> str:
    """Creates a CSV string from all found listings with UTF-8 BOM for German Excel."""
    data = []
    for spec_name, listings in listings_map.items():
        for l in listings:
            if getattr(l, 'verification', None):
                status = l.verification.status.value
            elif getattr(l, 'is_scam_suspected', False):
                status = ValidationStatus.SCAM_SUSPECT.value
            else:
                status = "UNKNOWN"
            is_alt = getattr(l, 'is_alternative', False)
            data.append({
                "Such-Kategorie": spec_name,
                "Titel": l.title,
                "Preis": l.price,
                "Ort": l.location,
                "Verifiziert": status,
                "Alternative": "Ja" if is_alt else "Nein",
                "Link": l.url
            })
    
    if not data:
        return "\ufeffSuch-Kategorie;Titel;Preis;Ort;Verifiziert;Alternative;Link\n"
        
    df = pd.DataFrame(data)
    csv_str = df.to_csv(index=False, sep=';')
    if not csv_str.startswith('\ufeff'):
        csv_str = '\ufeff' + csv_str
    return csv_str

# Icon map for component types
ICON_MAP = {
    ComponentType.GPU: "🎮",
    ComponentType.CPU: "🧠",
    ComponentType.MOTHERBOARD: "🔌",
    ComponentType.RAM: "💾",
    ComponentType.PSU: "⚡",
    ComponentType.CASE: "📦",
    ComponentType.COOLER: "❄️",
    ComponentType.STORAGE: "💿",
    ComponentType.FAN: "🌀",
    ComponentType.CABLE: "🔗",
    ComponentType.PERIPHERAL: "🖱️",
    ComponentType.ACCESSORY: "🎒",
}

def render_chat_message(role: str, content: str, avatar: str = None):
    """Renders a single chat message."""
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)

def render_sidebar_summary(specs: List[CanonicalSpec], total_price: float):
    """Minimal sidebar: just a status badge."""
    st.metric("Components", f"{len(specs)} / 8")
    if total_price > 0:
        st.metric("Best Build Price", f"~{total_price:.0f} €")
    progress_val = min(len(specs) / 8.0, 1.0)
    st.progress(progress_val)

def render_component_list_md(specs: List[CanonicalSpec]) -> str:
    """Returns a markdown string listing all parsed components."""
    if not specs:
        return "No components detected."
    
    lines = ["**Parsed Components:**\n"]
    for spec in specs:
        icon = ICON_MAP.get(spec.type, "❓")
        lines.append(f"- {icon} **{spec.name}** ({spec.type.value})")
    
    lines.append(f"\n*{len(specs)} components ready to scan.*")
    return "\n".join(lines)

def render_scan_results_md(listings_map: Dict[str, List[Listing]], specs: List[CanonicalSpec], build: Optional[Build] = None) -> str:
    """Returns a markdown string with scan results for the chat."""
    lines = ["**📊 Market Scan Results:**\n"]
    
    for spec in specs:
        icon = ICON_MAP.get(spec.type, "❓")
        listings = listings_map.get(spec.name, [])
        valid = [l for l in listings if l.verification and l.verification.status == ValidationStatus.PASS]
        
        if valid:
            best = min(valid, key=lambda x: x.price)
            lines.append(f"- {icon} **{spec.name}**: {len(valid)} hits, best **{best.price:.0f}€** → [Link]({best.url})")
        elif listings:
            lines.append(f"- {icon} **{spec.name}**: {len(listings)} found, ⚠️ none verified")
        else:
            lines.append(f"- {icon} **{spec.name}**: ❌ No listings found")
    
    # Build summary
    if build and build.total_price > 0:
        lines.append(f"\n---\n**💰 Best Build Total: ~{build.total_price:.0f}€** ({len(build.components)} components priced)")
        
        if build.missing_components:
            lines.append(f"⚠️ Missing: {', '.join(build.missing_components)}")
        if build.compatibility_warnings:
            for w in build.compatibility_warnings:
                lines.append(f"⚠️ {w}")
    
    return "\n".join(lines)

def render_listing_details(listings_map: Dict[str, List[Listing]], specs: List[CanonicalSpec]):
    """Render listing details grouped by Category (GPU, CPU, etc.)."""
    st.markdown("### 🏷️ Einzelteile nach Kategorie")
    
    # 1. Group specs by type
    from collections import defaultdict
    categories = defaultdict(list)
    for s in specs:
        categories[s.type].append(s)
        
    # 2. Sort categories logically
    order = [ComponentType.GPU, ComponentType.CPU, ComponentType.MOTHERBOARD, ComponentType.RAM, ComponentType.PSU, ComponentType.STORAGE, ComponentType.CASE]
    sorted_cat_keys = sorted(categories.keys(), key=lambda x: order.index(x) if x in order else 99)

    # Friendly names
    CAT_NAMES = {
        ComponentType.GPU: "Grafikkarten",
        ComponentType.CPU: "Prozessoren (CPU)",
        ComponentType.MOTHERBOARD: "Mainboards",
        ComponentType.RAM: "Arbeitsspeicher (RAM)",
        ComponentType.PSU: "Netzteile",
        ComponentType.CASE: "Gehäuse",
        ComponentType.STORAGE: "Speicher (SSD/HDD)",
    }

    for cat_key in sorted_cat_keys:
        cat_name = CAT_NAMES.get(cat_key, cat_key.value)
        icon = ICON_MAP.get(cat_key, "❓")
        
        # Collect ALL listings for this category (Original + Alternatives)
        cat_all_listings = []
        for s in categories[cat_key]:
            listings = listings_map.get(s.name, [])
            cat_all_listings.extend(listings)
            
        # Filter for PASS (without scam suspect)
        valid = [
            l for l in cat_all_listings 
            if l.verification and l.verification.status == ValidationStatus.PASS 
            and not getattr(l, 'is_scam_suspected', False)
            and (l.price is None or l.price >= 0.0)
        ]
        scam_listings = [
            l for l in cat_all_listings
            if getattr(l, 'is_scam_suspected', False)
            or (l.verification and l.verification.status == ValidationStatus.SCAM_SUSPECT)
        ]
        
        if valid:
            with st.expander(f"{icon} {cat_name} ({len(valid)} Angebote)"):
                # Sort priced items first, then pure VB
                for l in sorted(valid, key=lambda x: (x.price is None or x.price == 0.0, x.price if x.price is not None else float('inf')))[:15]:
                    with st.container(border=True):
                        cols = st.columns([5, 2, 2])
                        is_alt = getattr(l, 'is_alternative', False)
                        color = "#007AFF" if is_alt else "#34C759"
                        marker = f"<span style='color:{color}; font-size:16px; margin-right:8px;'>●</span>"
                        
                        # Label if it's an alternative to what
                        alt_info = f"<br><small style='color:#888'>Alternative für {l.alternative_for}</small>" if is_alt else ""
                        
                        # VB badge & Trust badges
                        vb_badge = " *(VB)*" if l.is_vb else ""
                        trust_badges = ""
                        if getattr(l, 'has_buyer_protection', False):
                            trust_badges += " <span style='background:#0d3820; color:#4ade80; font-size:11px; padding:2px 6px; border-radius:4px;'>🛡️ Käuferschutz</span>"
                        if getattr(l, 'shipping_available', False):
                            trust_badges += " <span style='background:#1e293b; color:#94a3b8; font-size:11px; padding:2px 6px; border-radius:4px;'>📦 Versand</span>"
                        
                        safe_title = html.escape((l.title or "")[:70])
                        cols[0].markdown(f"{marker}**{safe_title}**{trust_badges}{alt_info}", unsafe_allow_html=True)
                        
                        price_display = f"{l.price:.2f} €" if (l.price is not None and l.price > 0.0) else "VB"
                        cols[1].markdown(f"**{price_display}**{vb_badge}")
                        cols[2].markdown(f"[Ansehen]({l.url or '#'})")
                        
                        # 1-Click Negotiation Template for VB Listings (finite numbers >= 10€)
                        if l.is_vb and l.price is not None and math.isfinite(l.price) and 10.0 <= l.price <= 100000.0:
                            offer_price = max(10, int(round(l.price * 0.88 / 5.0) * 5))
                            short_title = html.escape((l.title or "")[:45])
                            msg = f"Hallo, ich interessiere mich für Ihr Angebot '{short_title}'. Wären {offer_price} € für Sie vorstellbar? Bei Einigung nehme ich es gerne direkt. Viele Grüße"
                            with st.expander(f"💬 Verhandlungs-Vorlage ({offer_price} € Angebot)", expanded=False):
                                st.caption("Klicke rechts oben im Textfeld auf das Kopiersymbol:")
                                st.code(msg, language="text")
        else:
            with st.expander(f"{icon} {cat_name} (Keine validen Angebote gefunden)", expanded=False):
                st.info(f"Keine validen Angebote für {cat_name} gefunden.")

        # Collapsed warning section for suspected scam / defective / box-only offers
        if scam_listings:
            with st.expander(f"⚠️ Verdächtige Angebote / Scam-Verdacht ({len(scam_listings)})", expanded=False):
                for sl in scam_listings:
                    with st.container(border=True):
                        cols = st.columns([5, 2, 2])
                        reason_text = html.escape(getattr(sl, 'scam_reason', None) or "Verdacht auf OVP / Defekt / Fake-Platzhalter")
                        safe_title = html.escape((sl.title or "")[:70])
                        cols[0].markdown(
                            f"<span style='color:#ef4444; font-weight:600;'>⚠️ Grund: {reason_text}</span><br>"
                            f"**{safe_title}**",
                            unsafe_allow_html=True
                        )
                        price_display = f"{sl.price:.2f} €" if (sl.price is not None and sl.price > 0.0) else "VB"
                        vb_badge = " *(VB)*" if sl.is_vb else ""
                        cols[1].markdown(f"**{price_display}**{vb_badge}")
                        cols[2].markdown(f"[Ansehen]({sl.url or '#'})")

def render_build_details(build: Build):
    """Render a complete PC build recommendation in a premium card layout."""
    st.markdown(f"### 🛒 Empfohlenes Setup (Gesamt: ~{build.total_price:.0f} €)")
    
    with st.expander("Details zum Build", expanded=True):
        for idx, c in enumerate(build.components):
            with st.container(border=True):
                cols = st.columns([1, 5, 2, 2])
                icon = ICON_MAP.get(c.product_match.type, "❓") if c.product_match else "❓"
                vb_badge = " *(VB)*" if c.is_vb else ""
                cols[0].write(f"### {icon}")
                title_short = html.escape((c.title or "")[:60])
                price_str = f"{c.price:.0f} €" if c.price is not None else "Preis k.A."
                cols[1].markdown(f"**{title_short}**\n\n*{c.location}*")
                cols[2].markdown(f"### {price_str}{vb_badge}")
                cols[3].markdown(f"[Kaufen/Ansehen]({c.url or '#'})")
            
        if build.missing_components:
            st.warning(f"⚠️ **Fehlende Teile für einen kompletten PC:** {', '.join(build.missing_components)}")
        
        if build.compatibility_warnings:
            for w in build.compatibility_warnings:
                st.error(f"⚠️ {w}")

def render_build_listings(listings: List[Listing]):
    """Render found complete PC listings with BOM decomposition and arbitrage savings."""
    st.markdown("### 🖥️ Komplette PCs auf Kleinanzeigen & Arbitrage-Analyse")
    valid = [
        l for l in listings 
        if not getattr(l, 'is_scam_suspected', False)
        and (not l.verification or l.verification.status not in [ValidationStatus.REJECT, ValidationStatus.SCAM_SUSPECT]) 
        and (l.price is None or l.price >= 0.0)
    ]
    scam_pcs = [
        l for l in listings
        if getattr(l, 'is_scam_suspected', False)
        or (l.verification and l.verification.status == ValidationStatus.SCAM_SUSPECT)
    ]
    
    if not valid and not scam_pcs:
        st.info("Keine passenden kompletten PCs gefunden.")
        return
        
    for l in sorted(valid, key=lambda x: getattr(x, 'arbitrage_savings', 0), reverse=True):
        with st.container(border=True):
            cols = st.columns([5, 2, 2])
            vb_badge = " *(VB)*" if l.is_vb else ""
            
            # Arbitrage Highlight
            savings = getattr(l, 'arbitrage_savings', 0.0)
            savings_html = ""
            if savings > 0:
                savings_html = f"<div style='background-color:#1c3d24; color:#4ade80; padding:4px 8px; border-radius:4px; font-weight:600; display:inline-block; margin-bottom:6px;'>🔥 Spar-Vorteil: ~{savings:.0f} € günstiger als Einzelteilkauf!</div><br>"
            
            # Trust badges
            trust_badges = ""
            if getattr(l, 'has_buyer_protection', False):
                trust_badges += " <span style='background:#0d3820; color:#4ade80; font-size:11px; padding:2px 6px; border-radius:4px;'>🛡️ Käuferschutz</span>"
            if getattr(l, 'shipping_available', False):
                trust_badges += " <span style='background:#1e293b; color:#94a3b8; font-size:11px; padding:2px 6px; border-radius:4px;'>📦 Versand</span>"

            # BOM components display
            bom_html = ""
            if getattr(l, 'bom', None) and l.bom.get("components"):
                parts_str = " • ".join([f"**{k}**: {v}" for k, v in l.bom["components"].items() if v])
                bom_html = f"<div style='font-size:0.85rem; color:#aaa; margin-top:4px;'>📋 <b>Erfasste Hardware:</b> {parts_str}</div>"
                
            safe_title = html.escape((l.title or "")[:80])
            cols[0].markdown(f"{savings_html}**{safe_title}**{trust_badges}\n\n*{l.location}*{bom_html}", unsafe_allow_html=True)
            
            price_str = f"{l.price:.0f} €" if (l.price is not None and l.price > 0.0) else "VB"
            cols[1].markdown(f"### {price_str}{vb_badge}")
            cols[2].markdown(f"[Ansehen]({l.url or '#'})")
            
            # 1-Click Negotiation Template for Complete PC (finite numbers >= 50€)
            if l.is_vb and l.price is not None and math.isfinite(l.price) and 50.0 <= l.price <= 100000.0:
                offer_price = max(50, int(round(l.price * 0.90 / 10.0) * 10))
                short_title = html.escape((l.title or "")[:45])
                msg = f"Hallo, ich interessiere mich für Ihren PC '{short_title}'. Wären {offer_price} € für Sie in Ordnung? Ich könnte zeitnah abholen oder per sicherem Versand zahlen. Viele Grüße"
                with st.expander(f"💬 Verhandlungs-Vorlage ({offer_price} € Angebot)", expanded=False):
                    st.caption("Klicke rechts oben im Textfeld auf das Kopiersymbol:")
                    st.code(msg, language="text")

    if scam_pcs:
        with st.expander(f"⚠️ Verdächtige Komplett-PCs / Scam-Verdacht ({len(scam_pcs)})", expanded=False):
            for sp in scam_pcs:
                with st.container(border=True):
                    cols = st.columns([5, 2, 2])
                    reason_text = html.escape(getattr(sp, 'scam_reason', None) or "Verdacht auf OVP / Defekt / Fake-Angebot")
                    safe_title = html.escape((sp.title or "")[:80])
                    cols[0].markdown(
                        f"<span style='color:#ef4444; font-weight:600;'>⚠️ Grund: {reason_text}</span><br>"
                        f"**{safe_title}**\n\n*{sp.location}*",
                        unsafe_allow_html=True
                    )
                    price_str = f"{sp.price:.0f} €" if (sp.price is not None and sp.price > 0.0) else "VB"
                    vb_badge = " *(VB)*" if sp.is_vb else ""
                    cols[1].markdown(f"### {price_str}{vb_badge}")
                    cols[2].markdown(f"[Ansehen]({sp.url or '#'})")

def render_build_proposals(proposals: List[Any]) -> Optional[Any]:
    """
    Renders 3 interactive build proposal cards side-by-side with 1-click scan buttons.
    Returns the selected proposal if a button was clicked, or None.
    """
    if not proposals:
        return None

    st.markdown("### 🛠️ Automatische Build-Vervollständigung")
    st.info(
        "💡 **Teileingabe erkannt:** Wir haben 3 optimal abgestimmte, 100% kompatible Gaming-Setups "
        "für deine Komponente kalkuliert (0 ms, deterministisch über unsere 241-Teile-Matrix). "
        "Wähle dein bevorzugtes Tier, um direkt den kompletten Markt-Scan auf Kleinanzeigen zu starten:"
    )

    cols = st.columns(len(proposals))
    selected_proposal = None

    for idx, prop in enumerate(proposals):
        with cols[idx]:
            with st.container(border=True):
                # Header with Badge
                st.markdown(f"### {html.escape(prop.tier_name)}")
                st.caption(f"**{html.escape(prop.badge)}**")
                st.markdown(f"*{html.escape(prop.headline)}*")

                # Metrics: Price, Corridor, Gaming Index, P/L Ratio
                p_min, p_max = getattr(prop, 'price_range', (prop.total_price * 0.9, prop.total_price * 1.1))
                st.metric(
                    label="Geschätzter Gesamtpreis",
                    value=f"~{prop.total_price:.0f} €",
                    delta=f"{p_min:.0f} € – {p_max:.0f} €"
                )

                m_col1, m_col2 = st.columns(2)
                m_col1.markdown(f"🎮 **Gaming-Index:**\n### {prop.gaming_score}%")
                m_col2.markdown(f"💎 **P/L-Faktor:**\n### {html.escape(prop.pl_label)}")

                st.caption(html.escape(prop.description))
                st.divider()

                # Hardware BOM
                st.markdown("📋 **Konfiguration & Komponenten:**")
                for comp in prop.components:
                    comp_type = None
                    try:
                        comp_type = ComponentType(comp.category)
                    except Exception:
                        pass
                    icon = ICON_MAP.get(comp_type, "▫️") if comp_type else "▫️"
                    user_tag = " <span style='background:#1e3a5f; color:#60a5fa; font-size:11px; padding:2px 6px; border-radius:4px;'>Deine Eingabe</span>" if comp.is_user_input else ""
                    safe_name = html.escape(comp.name or "")
                    safe_summary = html.escape(comp.specs_summary or "")
                    st.markdown(
                        f"- {icon} **{safe_name}**{user_tag}<br>"
                        f"  *~{comp.estimated_price:.0f} €* <span style='color:#888; font-size:11px;'>({safe_summary})</span>",
                        unsafe_allow_html=True
                    )

                st.divider()

                # Compatibility Check Badge & Notes
                if getattr(prop, 'is_compatible', True):
                    st.success("✅ **100% Kompatibilität bestätigt**")
                else:
                    st.warning("⚠️ **Kompatibilitätshinweise vorhanden**")

                for note in getattr(prop, 'compatibility_notes', []):
                    st.caption(html.escape(str(note)))

                st.divider()

                # 1-Click Scan Button
                btn_type = "primary" if prop.tier_id == "sweetspot" else "secondary"
                if st.button(
                    "🚀 Dieses Setup scannen",
                    key=f"scan_prop_{prop.tier_id}_{idx}",
                    type=btn_type,
                    use_container_width=True
                ):
                    selected_proposal = prop

def render_telemetry_summary(telemetry_data: Optional[Dict[str, Any]]):
    """
    Renders a compact, high-visibility performance and traffic telemetry summary card:
    - Gesamtdauer (s)
    - Anzahl HTTP-Requests & Status-Codes
    - Datenvolumen (KB)
    - Durchschnittliche Latenz (s)
    - Pipeline-Phasen Aufschlüsselung
    """
    if not telemetry_data or not isinstance(telemetry_data, dict):
        return
    
    traffic = telemetry_data.get("traffic", {})
    perf = telemetry_data.get("performance", {})
    
    total_duration = perf.get("total_duration_s", 0.0)
    total_reqs = traffic.get("total_requests", 0)
    kb = traffic.get("data_volume_kb", 0.0)
    avg_latency = traffic.get("avg_latency_s", 0.0)
    cache_hits = traffic.get("cache_hits", 0)
    llm_calls = traffic.get("llm_calls", 0)
    status_codes = traffic.get("status_codes", {})
    
    with st.container(border=True):
        st.markdown("### ⚡ Performance & Traffic")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("⏱️ Gesamtdauer", f"{total_duration:.2f} s")
        c2.metric("🌐 HTTP Requests", f"{total_reqs}")
        c3.metric("📦 Datenvolumen", f"{kb:.1f} KB")
        c4.metric("⚡ Ø Latenz", f"{avg_latency:.2f} s")
        
        with st.expander("🔍 Telemetrie-Details & Pipeline-Phasen", expanded=False):
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                st.markdown("**⏱️ Pipeline-Phasen:**")
                durations_s = perf.get("durations_s", {})
                if durations_s:
                    for phase, dur in durations_s.items():
                        st.caption(f"• **{phase}**: `{dur:.2f} s`")
                else:
                    st.caption("Keine Phasen erfasst.")
            with t_col2:
                st.markdown("**🌐 Traffic & Cache:**")
                st.caption(f"• **0ms Katalog-Treffer (Cache Hits)**: `{cache_hits}`")
                st.caption(f"• **LLM API Aufrufe**: `{llm_calls}`")
                if status_codes:
                    codes_str = ", ".join(f"`{k}`: {v}" for k, v in status_codes.items())
                    st.caption(f"• **Status-Codes**: {codes_str}")
