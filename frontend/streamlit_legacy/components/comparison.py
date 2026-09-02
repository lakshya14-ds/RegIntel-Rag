"""
Direct Regulatory Document Comparison Component for RegIntel Frontend.
"""

import json
import streamlit as st
from typing import Dict, Any, List, Optional
from frontend.utils import format_date, get_confidence_badge, get_change_type_badge
from frontend.api_client import RegIntelAPIClient


def render_comparison_page(client: RegIntelAPIClient) -> None:
    """
    Renders the Compare Regulations page with 4-tier structural alignment,
    delta classification, side-by-side diff boxes, and impact summaries.
    """
    st.subheader("⚖️ Compare Regulatory Documents")
    st.caption("Perform direct evidence-grounded comparison between two circular versions to isolate compliance modifications, additions, and repeals.")

    # 1. Fetch available documents for interactive selection
    available_docs = []
    try:
        available_docs = client.get_latest(limit=40)
    except Exception:
        pass

    doc_options = {"": "-- Select from indexed corpus --"}
    for d in available_docs:
        d_id = d.get("document_id", "")
        d_title = d.get("title", "Untitled")
        d_date = format_date(d.get("published_date"))
        doc_options[d_id] = f"{d_title} ({d_date}) [{d_id[:8]}...]"

    # Quick action helper
    st.markdown("##### ⚡ Quick Actions & Corpus Selection")
    if st.button("📋 Load Pre-Configured IA Circular Pair (2020 vs 2024)"):
        st.session_state["cmp_doc_a"] = "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
        st.session_state["cmp_doc_b"] = "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Document A (Baseline / Prior Version)**")
        sel_a = st.selectbox(
            "Select Document A:",
            options=list(doc_options.keys()),
            format_func=lambda x: doc_options.get(x, x),
            key="cmp_select_a"
        )
        if sel_a:
            st.session_state["cmp_doc_a"] = sel_a

        doc_a_val = st.text_input(
            "Document A ID (or SHA-256):",
            value=st.session_state.get("cmp_doc_a", ""),
            placeholder="e.g. af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab",
            key="cmp_input_a"
        )

    with col_b:
        st.markdown("**Document B (Revised / Newer Version)**")
        sel_b = st.selectbox(
            "Select Document B:",
            options=list(doc_options.keys()),
            format_func=lambda x: doc_options.get(x, x),
            key="cmp_select_b"
        )
        if sel_b:
            st.session_state["cmp_doc_b"] = sel_b

        doc_b_val = st.text_input(
            "Document B ID (or SHA-256):",
            value=st.session_state.get("cmp_doc_b", ""),
            placeholder="e.g. 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8",
            key="cmp_input_b"
        )

    st.write("")
    compare_btn = st.button("⚖️ Compare Documents", type="primary", use_container_width=True)

    if compare_btn:
        if not doc_a_val.strip() or not doc_b_val.strip():
            st.warning("Please provide both Document A and Document B IDs to compare.")
            return

        with st.spinner("Aligning regulatory sections, classifying deltas & generating compliance impact..."):
            try:
                comp_res = client.compare_documents(doc_a_val.strip(), doc_b_val.strip())

                older_doc = comp_res.get("older_document") or comp_res.get("document_a", {})
                newer_doc = comp_res.get("newer_document") or comp_res.get("document_b", {})
                order_conf = comp_res.get("document_order_confidence", "unknown").upper()
                rel_type = comp_res.get("version_relationship", "UNKNOWN")
                rel_conf = comp_res.get("relationship_confidence", "unknown").upper()

                # 1. Comparative Context Cards
                st.markdown("### 📜 Comparative Document Context")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                    st.markdown(f"**OLDER DOCUMENT (Baseline)**: {older_doc.get('title', 'Untitled')}")
                    st.caption(f"📅 Published: `{format_date(older_doc.get('published_date'))}` | Type: `{older_doc.get('document_type', 'Circular')}` | Status: `{older_doc.get('status', 'historical').upper()}`")
                    if older_doc.get("url"):
                        st.markdown(f"🔗 [Open Older Circular Link]({older_doc.get('url')})")
                    st.markdown('</div>', unsafe_allow_html=True)

                with c2:
                    st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                    st.markdown(f"**NEWER DOCUMENT (Revised)**: {newer_doc.get('title', 'Untitled')}")
                    st.caption(f"📅 Published: `{format_date(newer_doc.get('published_date'))}` | Type: `{newer_doc.get('document_type', 'Circular')}` | Status: `{newer_doc.get('status', 'current').upper()}`")
                    if newer_doc.get("url"):
                        st.markdown(f"🔗 [Open Newer Circular Link]({newer_doc.get('url')})")
                    st.markdown('</div>', unsafe_allow_html=True)

                # Relationship & Confidence Badges
                cache_badge = '<span class="badge badge-purple">⚡ CACHE HIT</span>' if comp_res.get("cached") else ""
                st.markdown(
                    f'<span class="badge badge-blue">Relationship: {rel_type}</span>'
                    f'{get_confidence_badge(rel_conf)}'
                    f'<span class="badge badge-gray">Chronology Confidence: {order_conf}</span>'
                    f'{cache_badge}',
                    unsafe_allow_html=True
                )

                if rel_conf in ("LOW", "UNKNOWN"):
                    st.warning("⚠️ **Notice**: The relationship between these documents was determined with low confidence. Verify the original regulatory documents.")
                if order_conf in ("LOW", "UNKNOWN"):
                    st.info("ℹ️ **Notice**: Chronological ordering is uncertain due to identical or missing publication dates.")

                st.divider()

                # 2. Executive Change Summary
                st.markdown("### 📊 Executive Summary")
                exec_summary = comp_res.get("executive_summary") or comp_res.get("summary", "Comparison completed.")
                st.markdown(exec_summary)

                key_changes = comp_res.get("key_changes", [])
                if key_changes:
                    st.markdown("##### 📌 Key Substantive Changes:")
                    for k in key_changes:
                        st.markdown(f"* {k}")

                # 3. Metrics Row
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Sections", comp_res.get("total_changes", 0))
                m2.metric("🟢 Added", comp_res.get("added_count", 0))
                m3.metric("🔴 Removed", comp_res.get("removed_count", 0))
                m4.metric("🟡 Modified", comp_res.get("modified_count", 0))
                m5.metric("⚪ Unchanged", comp_res.get("unchanged_count", 0))

                st.divider()

                # 4. Section-by-Section Delta Breakdown
                changes = comp_res.get("changes", [])
                st.markdown(f"### 📋 Section-by-Section Delta Breakdown ({len(changes)})")

                filter_opt = st.radio(
                    "Filter Changes by Classification:",
                    options=["ALL", "MODIFIED", "ADDED", "REMOVED", "UNCHANGED"],
                    horizontal=True,
                    key="cmp_filter_opt"
                )

                filtered = [
                    ch for ch in changes
                    if filter_opt == "ALL" or ch.get("change_type") == filter_opt
                ]

                for ch in filtered:
                    ctype = ch.get("change_type", "MODIFIED")
                    heading = ch.get("heading", "Untitled Section")
                    sec_num = ch.get("section") or ""
                    title_str = f"[{ctype}] {f'Sec {sec_num}: ' if sec_num else ''}{heading}"

                    with st.expander(title_str, expanded=(ctype == "MODIFIED")):
                        st.markdown(
                            f'{get_change_type_badge(ctype)}'
                            f'<span class="badge badge-gray">{ch.get("modification_category", "GENERAL").upper()}</span>',
                            unsafe_allow_html=True
                        )

                        if ch.get("summary"):
                            st.markdown(f"**WHAT CHANGED**: {ch.get('summary')}")
                        if ch.get("impact") or ch.get("compliance_impact"):
                            st.markdown(f"**COMPLIANCE IMPACT**: `{ch.get('impact') or ch.get('compliance_impact')}`")

                        # Side-by-Side Text Comparison for Modified Sections
                        if ctype == "MODIFIED" and (ch.get("previous_text") or ch.get("current_text")):
                            st.markdown("##### 🔍 Text Comparison")
                            col_old, col_new = st.columns(2)
                            with col_old:
                                st.markdown("**OLD Text (Baseline)**")
                                st.markdown(f'<div class="diff-box-old">{ch.get("previous_text", "N/A")}</div>', unsafe_allow_html=True)
                            with col_new:
                                st.markdown("**NEW Text (Revised)**")
                                st.markdown(f'<div class="diff-box-new">{ch.get("current_text", "N/A")}</div>', unsafe_allow_html=True)

                        elif ctype == "ADDED" and ch.get("current_text"):
                            st.markdown("##### ➕ NEW Text")
                            st.markdown(f'<div class="diff-box-new">{ch.get("current_text")}</div>', unsafe_allow_html=True)

                        elif ctype == "REMOVED" and ch.get("previous_text"):
                            st.markdown("##### ➖ OLD Text (Repealed)")
                            st.markdown(f'<div class="diff-box-old">{ch.get("previous_text")}</div>', unsafe_allow_html=True)

                        # Evidence References
                        old_s = ch.get("old_source")
                        new_s = ch.get("new_source")
                        if old_s or new_s:
                            st.markdown("##### 📚 EVIDENCE:")
                            if old_s:
                                st.caption(f"• **Older Source**: `{old_s.get('document_id', '')[:12]}` | Section: `{old_s.get('heading')}`")
                            if new_s:
                                st.caption(f"• **Newer Source**: `{new_s.get('document_id', '')[:12]}` | Section: `{new_s.get('heading')}`")

                # 5. Export Report
                st.divider()
                st.markdown("### 📥 Export Report")
                st.download_button(
                    label="Download Full Comparison Report (JSON)",
                    data=json.dumps(comp_res, indent=2),
                    file_name=f"comparison_{older_doc.get('document_id', 'A')[:8]}_{newer_doc.get('document_id', 'B')[:8]}.json",
                    mime="application/json"
                )

            except Exception as e:
                st.error(f"Comparison Error: {e}")
                st.info("Please verify the document IDs or ensure the FastAPI backend is running.")
