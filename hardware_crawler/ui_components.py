import streamlit as st
import pandas as pd
from typing import List, Optional, Dict, Any
from .models import CanonicalSpec, ComponentType, Listing, ValidationStatus, Build

def generate_csv_export(listings_map: Dict[str, List[Listing]]) -> str:
    """Creates a CSV string from all found listings."""
    data = []
    for spec_name, listings in listings_map.items():
        for l in listings:
            status = l.verification.status.value if getattr(l, 'verification', None) else "UNKNOWN"
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
        return "Such-Kategorie,Titel,Preis,Ort,Verifiziert,Alternative,Link\n"
        
    df = pd.DataFrame(data)
    return df.to_csv(index=False)

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
            
        # Filter for PASS
        valid = [l for l in cat_all_listings if l.verification and l.verification.status == ValidationStatus.PASS and l.price > 0.0]
        
        if valid:
            with st.expander(f"{icon} {cat_name} ({len(valid)} Angebote)"):
                # Sort by price
                for l in sorted(valid, key=lambda x: x.price)[:15]:
                    with st.container(border=True):
                        cols = st.columns([5, 2, 2])
                        is_alt = getattr(l, 'is_alternative', False)
                        color = "#007AFF" if is_alt else "#34C759"
                        marker = f"<span style='color:{color}; font-size:16px; margin-right:8px;'>●</span>"
                        
                        # Label if it's an alternative to what
                        alt_info = f"<br><small style='color:#888'>Alternative für {l.alternative_for}</small>" if is_alt else ""
                        
                        cols[0].markdown(f"{marker}**{l.title[:70]}**{alt_info}", unsafe_allow_html=True)
                        cols[1].markdown(f"**{l.price:.2f} €**")
                        cols[2].markdown(f"[Ansehen]({l.url})")
        else:
            with st.expander(f"{icon} {cat_name} (Keine validen Angebote gefunden)", expanded=False):
                st.info(f"Keine validen Angebote für {cat_name} gefunden.")

def render_build_details(build: Build):
    """Render a complete PC build recommendation in a premium card layout."""
    st.markdown(f"### 🛒 Empfohlenes Setup (Gesamt: ~{build.total_price:.0f} €)")
    
    with st.expander("Details zum Build", expanded=True):
        for idx, c in enumerate(build.components):
            with st.container(border=True):
                cols = st.columns([1, 5, 2, 2])
                icon = ICON_MAP.get(c.product_match.type, "❓") if c.product_match else "❓"
                cols[0].write(f"### {icon}")
                cols[1].markdown(f"**{c.title[:60]}**\n\n*{c.location}*")
                cols[2].markdown(f"### {c.price:.0f} €")
                cols[3].markdown(f"[Kaufen/Ansehen]({c.url})")
            
        if build.missing_components:
            st.warning(f"⚠️ **Fehlende Teile für einen kompletten PC:** {', '.join(build.missing_components)}")
        
        if build.compatibility_warnings:
            for w in build.compatibility_warnings:
                st.error(f"⚠️ {w}")

def render_build_listings(listings: List[Listing]):
    """Render found complete PC listings."""
    st.markdown("### 🖥️ Komplette PCs auf Kleinanzeigen")
    valid = [l for l in listings if l.verification and l.verification.status != ValidationStatus.REJECT and l.price > 0.0]
    
    if not valid:
        st.info("Keine passenden kompletten PCs gefunden.")
        return
        
    for l in sorted(valid, key=lambda x: x.price):
        with st.container(border=True):
            cols = st.columns([5, 2, 2])
            cols[0].markdown(f"**{l.title[:80]}**\n\n*{l.location}*")
            cols[1].markdown(f"### {l.price:.0f} €")
            cols[2].markdown(f"[Ansehen]({l.url})")

