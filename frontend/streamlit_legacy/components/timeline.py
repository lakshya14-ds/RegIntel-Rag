"""
Regulatory Version Tracking and Timeline Component for RegIntel Frontend.
"""

import streamlit as st
from typing import Dict, Any, List, Optional
from frontend.utils import format_date, get_status_badge, get_confidence_badge
from frontend.api_client import RegIntelAPIClient


def render_timeline_page(client: RegIntelAPIClient) -> None:
    """
    Renders the Document Timeline & Version Lineage page.
    """
    st.subheader("⏳ Document Timeline & Version Lineage")
    st.caption("Inspect how regulatory circulars evolve over time, tracking predecessors, successors, and supersession chains.")

    # 1. Fetch available documents
    available_docs = []
    try:
        available_docs = client.get_latest(limit=40)
    except Exception:
        pass

    doc_options = {"": "-- Select a regulatory document --"}
    for d in available_docs:
        d_id = d.get("document_id", "")
        d_title = d.get("title", "Untitled")
        d_date = format_date(d.get("published_date"))
        doc_options[d_id] = f"{d_title} ({d_date}) [{d_id[:8]}...]"

    col_s, col_btn = st.columns([3, 1])
    with col_s:
        sel_doc = st.selectbox(
            "Select Document from Corpus:",
            options=list(doc_options.keys()),
            format_func=lambda x: doc_options.get(x, x),
            key="timeline_select_doc"
        )
        doc_id_input = st.text_input(
            "Or enter Document ID (SHA-256):",
            value=sel_doc if sel_doc else "",
            placeholder="e.g. 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8",
            key="timeline_input_id"
        )

    with col_btn:
        st.write("")
        st.write("")
        inspect_btn = st.button("🔍 Load Timeline", type="primary", use_container_width=True)

    target_id = doc_id_input.strip()

    if (inspect_btn or sel_doc) and target_id:
        with st.spinner("Loading regulatory version history and lineage graph..."):
            try:
                v_info = client.get_document_versions(target_id)

                status_val = v_info.get("status", "unknown")
                rel_type = v_info.get("relationship_type", "UNKNOWN")
                rel_conf = (v_info.get("relationship_confidence") or "UNKNOWN").upper()
                doc_version = v_info.get("document_version", "1.0")

                st.markdown("### 📄 Target Document Overview")
                st.markdown(
                    f"**Title**: {v_info.get('title', 'Regulatory Document')}<br>"
                    f"**Status**: {get_status_badge(status_val)} | "
                    f"<span class=\"badge badge-purple\">Version {doc_version}</span> | "
                    f"<span class=\"badge badge-blue\">Type: {rel_type}</span> | "
                    f"{get_confidence_badge(rel_conf)}",
                    unsafe_allow_html=True
                )
                st.caption(f"Document ID: `{target_id}`")

                # Warning for uncertain relationships
                if rel_conf in ("LOW", "UNKNOWN"):
                    st.warning("⚠️ **Notice**: Possible predecessor — verify the original regulatory documents before relying on legal certainty.")

                st.divider()

                # 2. Predecessor & Successor Summary Cards
                c_pred, c_succ = st.columns(2)
                with c_pred:
                    st.markdown("#### ⬅️ Predecessor (Supersedes)")
                    pred_doc = v_info.get("predecessor")
                    if pred_doc:
                        st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                        st.markdown(f"**{pred_doc.get('title')}**")
                        st.caption(f"📅 Published: `{format_date(pred_doc.get('published_date'))}` | Status: `{pred_doc.get('status', 'historical').upper()}`")
                        st.caption(f"Document ID: `{pred_doc.get('document_id')}`")
                        if pred_doc.get("url"):
                            st.markdown(f"🔗 [Official Link]({pred_doc.get('url')})")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.info("No prior predecessor recorded (Baseline Regulation).")

                with c_succ:
                    st.markdown("#### ➡️ Successor (Superseded By)")
                    succ_doc = v_info.get("successor")
                    if succ_doc:
                        st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                        st.markdown(f"**{succ_doc.get('title')}**")
                        st.caption(f"📅 Published: `{format_date(succ_doc.get('published_date'))}` | Status: `{succ_doc.get('status', 'current').upper()}`")
                        st.caption(f"Document ID: `{succ_doc.get('document_id')}`")
                        if succ_doc.get("url"):
                            st.markdown(f"🔗 [Official Link]({succ_doc.get('url')})")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.success("No successor identified — this regulation is actively **CURRENT**.")

                st.divider()

                # 3. Chronological Vertical Timeline
                timeline = v_info.get("timeline", [])
                st.markdown(f"### 📈 Version Evolution Timeline ({len(timeline)} events)")

                if timeline:
                    for idx, node in enumerate(timeline, start=1):
                        is_target = node.get("document_id") == target_id
                        n_status = node.get("status", "unknown")
                        n_date = format_date(node.get("published_date"))
                        n_title = node.get("title", "Regulatory Document")

                        card_bg = "#EFF6FF" if is_target else "#F8FAFC"
                        border_color = "#3B82F6" if is_target else "#E2E8F0"

                        st.markdown(f"""
                        <div style="background-color: {card_bg}; border: 2px solid {border_color}; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem;">
                            <span style="font-size: 1.1rem; font-weight: 600;">{idx}. {n_title}</span> {'<span class="badge badge-blue">📍 SELECTED</span>' if is_target else ''}<br>
                            <span style="font-size: 0.88rem; color: #4B5563;">📅 <b>Published</b>: <code>{n_date}</code> | <b>Status</b>: {get_status_badge(n_status)}</span><br>
                            <span style="font-size: 0.8rem; color: #6B7280;">Document ID: <code>{node.get('document_id')}</code></span>
                        </div>
                        """, unsafe_allow_html=True)

                        if idx < len(timeline):
                            st.markdown("<div style='text-align: center; font-size: 1.5rem; color: #9CA3AF; margin: -0.3rem 0;'>↓ superseded by</div>", unsafe_allow_html=True)
                else:
                    st.info("No timeline events mapped for this document.")

            except Exception as e:
                st.error(f"Error retrieving document version graph: {e}")
                st.info("Please ensure the document exists and the FastAPI backend is running.")
