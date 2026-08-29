"""
Streamlit Web Frontend for RegIntel RAG — Regulatory Intelligence & Change Analysis System.

Interacts with the FastAPI backend to provide:
1. Grounded Regulatory Q&A with Citation Validation
2. Direct Evidence-Grounded Regulatory Document Comparison (Phases 39–41)
3. Latest Circulars & Version Lineage Graph
4. Multi-Method Search & Evidence Inspection
"""

import os
import json
import streamlit as st
from typing import Dict, Any, List, Optional

from frontend.api_client import RegIntelAPIClient

# Page configuration
st.set_page_config(
    page_title="RegIntel RAG — Regulatory Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished, authoritative interface
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 9999px;
        margin-right: 0.4rem;
        margin-bottom: 0.3rem;
    }
    .badge-blue { background-color: #DBEAFE; color: #1E40AF; }
    .badge-green { background-color: #DCFCE7; color: #166534; }
    .badge-amber { background-color: #FEF3C7; color: #92400E; }
    .badge-red { background-color: #FEE2E2; color: #991B1B; }
    .badge-gray { background-color: #F3F4F6; color: #374151; }
    .badge-purple { background-color: #F3E8FF; color: #6B21A8; }
    .doc-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .diff-box-old {
        background-color: #FFF5F5;
        border-left: 4px solid #E53E3E;
        padding: 0.75rem;
        border-radius: 4px;
        font-size: 0.88rem;
    }
    .diff-box-new {
        background-color: #F0FFF4;
        border-left: 4px solid #38A169;
        padding: 0.75rem;
        border-radius: 4px;
        font-size: 0.88rem;
    }
    .disclaimer-text {
        font-size: 0.82rem;
        color: #6B7280;
        font-style: italic;
        margin-top: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize API Client
client = RegIntelAPIClient()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/scales.png", width=64)
    st.title("RegIntel RAG")
    st.caption("Grounded Regulatory Intelligence & Compliance Delta Engine")
    st.divider()

    # Health check
    health = client.health_check()
    status_color = "🟢" if health.get("status") == "ok" else ("🟡" if health.get("status") == "degraded" else "🔴")
    st.markdown(f"**Backend Status**: {status_color} `{health.get('status', 'unavailable').upper()}`")
    st.markdown(f"* MongoDB: `{'Online' if health.get('mongodb') else 'Offline/Local'}`")
    st.markdown(f"* Embeddings: `{'Active' if health.get('embedding_service') else 'Inactive'}`")

    st.divider()
    st.subheader("Retrieval Settings")
    retrieval_mode = st.selectbox(
        "Retrieval Engine",
        options=["hybrid", "hybrid_reranked", "bm25", "vector"],
        index=0,
        help="Select multi-method retrieval algorithm"
    )
    top_k_val = st.slider("Evidence Top-K", min_value=1, max_value=15, value=5)
    st.divider()
    st.caption("RegIntel v1.0.0 | SEBI Regulatory Corpus")


# Header
st.markdown('<div class="main-header">⚖️ RegIntel RAG</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Regulatory Intelligence, Structural Comparison & Version Tracking</div>', unsafe_allow_html=True)

# Main Navigation Tabs
tab_ask, tab_compare, tab_latest, tab_search = st.tabs([
    "💬 Regulatory Q&A",
    "⚖️ Compare Documents",
    "📜 Latest Circulars & Version Lineage",
    "🔎 Evidence Search"
])


# =========================================================================
# TAB 1: REGULATORY Q&A
# =========================================================================
with tab_ask:
    st.subheader("Grounded Regulatory Question Answering")
    st.caption("Ask compliance queries grounded strictly in SEBI circulars with deterministic citations.")

    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        sample_queries = [
            "",
            "What are the latest SEBI requirements for investment advisers regarding fees and client agreements?",
            "What is the required qualification and net worth for Investment Advisers under SEBI regulations?",
            "What is the maximum timeline for mutual fund dividend payouts according to SEBI?",
            "How long must investment advisers maintain client records and books of account?"
        ]
        selected_sample = st.selectbox("💡 Sample Regulatory Queries:", options=sample_queries, index=0)

    question_input = st.text_area(
        "Enter your regulatory question:",
        value=selected_sample if selected_sample else "",
        height=90,
        placeholder="e.g. What are the audit obligations and submission deadlines for SEBI registered investment advisers?"
    )

    col_f1, col_f2, col_btn = st.columns([2, 2, 2])
    with col_f1:
        category_filter = st.selectbox(
            "Category Filter (Optional)",
            options=["", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories"],
            index=0
        )
    with col_f2:
        source_filter = st.selectbox("Regulatory Authority", options=["All", "SEBI"], index=0)
    with col_btn:
        st.write("")
        st.write("")
        ask_btn = st.button("🚀 Analyze Regulation", type="primary", use_container_width=True)

    if ask_btn:
        if not question_input.strip():
            st.warning("Please enter a regulatory question.")
        else:
            with st.spinner("Searching regulatory sources & synthesizing grounded answer..."):
                try:
                    res = client.ask_question(
                        question=question_input.strip(),
                        top_k=top_k_val,
                        retrieval_mode=retrieval_mode,
                        category=category_filter if category_filter else None,
                        source=source_filter if source_filter != "All" else None
                    )

                    # Intent & Classification
                    intent = res.get("query_intent")
                    if intent:
                        st.markdown("#### 🎯 Query Intent Analysis")
                        st.markdown(
                            f'<span class="badge badge-blue">Type: {intent.get("query_type")}</span>'
                            f'<span class="badge badge-amber">Time: {intent.get("time_intent")}</span>'
                            f'<span class="badge badge-green">Category: {intent.get("category") or "General"}</span>'
                            f'<span class="badge badge-gray">Authority: {intent.get("source") or "SEBI"}</span>',
                            unsafe_allow_html=True
                        )
                        st.write("")

                    # Grounded Answer
                    st.markdown("### 💡 Grounded Regulatory Answer")
                    st.markdown(res.get("answer", "No answer generated."))
                    st.markdown(f'<div class="disclaimer-text">ℹ️ {res.get("disclaimer", "")}</div>', unsafe_allow_html=True)
                    st.divider()

                    # Sources & Citations
                    sources = res.get("sources", [])
                    st.markdown(f"### 📚 Retrieved Evidence Sources ({len(sources)})")
                    if sources:
                        for s in sources:
                            with st.expander(f"[{s.get('source_id')}] {s.get('title')} — Section: {s.get('section', 'General')}"):
                                c1, c2, c3 = st.columns(3)
                                c1.markdown(f"**Authority**: `{s.get('source')}`")
                                c2.markdown(f"**Published Date**: `{s.get('published_date')}`")
                                c3.markdown(f"**Relevance Score**: `{s.get('score')}`")
                                st.markdown(f"**Document ID**: `{s.get('document_id')}`")
                                if s.get("url"):
                                    st.markdown(f"🔗 [Open Official SEBI Circular]({s.get('url')})")
                    else:
                        st.info("No specific citation sources attached.")

                except Exception as e:
                    st.error(f"Backend Error: {e}")
                    st.info("Please verify that the FastAPI backend server is running (`uvicorn app.main:app --port 8000`).")


# =========================================================================
# TAB 2: COMPARE DOCUMENTS (PHASES 39–41)
# =========================================================================
with tab_compare:
    st.subheader("Direct Regulatory Document Comparison Engine")
    st.caption("Select two regulatory circulars to perform 4-tier structural alignment, delta classification, and evidence-grounded difference analysis.")

    # Fetch available documents for interactive selection
    available_docs = []
    try:
        available_docs = client.get_latest(limit=30)
    except Exception:
        pass

    doc_options = {"": "-- Select from corpus --"}
    for d in available_docs:
        d_id = d.get("document_id", "")
        d_title = d.get("title", "Untitled")
        d_date = d.get("published_date", "")
        doc_options[d_id] = f"{d_title} ({d_date}) [{d_id[:10]}...]"

    st.markdown("##### ⚡ Quick Actions & Corpus Selection")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("📋 Load Sample IA Circular Comparison Pair (2020 vs 2024)"):
            st.session_state["doc_a_id"] = "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
            st.session_state["doc_b_id"] = "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"

    col_sel_a, col_sel_b = st.columns(2)
    with col_sel_a:
        sel_a = st.selectbox("Choose Document A from Corpus:", options=list(doc_options.keys()), format_func=lambda x: doc_options.get(x, x), key="sel_doc_a")
        if sel_a:
            st.session_state["doc_a_id"] = sel_a
        doc_a_input = st.text_input(
            "Document A ID (or enter SHA-256 ID):",
            value=st.session_state.get("doc_a_id", ""),
            placeholder="e.g. af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
        )

    with col_sel_b:
        sel_b = st.selectbox("Choose Document B from Corpus:", options=list(doc_options.keys()), format_func=lambda x: doc_options.get(x, x), key="sel_doc_b")
        if sel_b:
            st.session_state["doc_b_id"] = sel_b
        doc_b_input = st.text_input(
            "Document B ID (or enter SHA-256 ID):",
            value=st.session_state.get("doc_b_id", ""),
            placeholder="e.g. 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"
        )

    compare_clicked = st.button("⚖️ Execute Regulatory Comparison", type="primary", use_container_width=True)

    if compare_clicked:
        if not doc_a_input.strip() or not doc_b_input.strip():
            st.warning("Please provide both Document A and Document B IDs.")
        else:
            with st.spinner("Aligning sections, classifying regulatory deltas & synthesizing evidence..."):
                try:
                    comp_res = client.compare_documents(doc_a_input.strip(), doc_b_input.strip())

                    # 1. Comparison Header & Chronology Metadata
                    older_doc = comp_res.get("older_document") or comp_res.get("document_a", {})
                    newer_doc = comp_res.get("newer_document") or comp_res.get("document_b", {})
                    order_conf = comp_res.get("document_order_confidence", "unknown").upper()
                    rel_type = comp_res.get("version_relationship", "UNKNOWN")
                    rel_conf = comp_res.get("relationship_confidence", "unknown").upper()

                    st.markdown("### 📜 Comparative Document Context")
                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                        st.markdown(f"**Older Version (Baseline)**: {older_doc.get('title', 'Untitled')}")
                        st.caption(f"📅 Published: `{older_doc.get('published_date', 'N/A')}` | Type: `{older_doc.get('document_type', 'Circular')}` | Status: `{older_doc.get('status', 'historical').upper()}`")
                        if older_doc.get("url"):
                            st.markdown(f"🔗 [Official Circular Link]({older_doc.get('url')})")
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col_h2:
                        st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                        st.markdown(f"**Newer Version (Revised)**: {newer_doc.get('title', 'Untitled')}")
                        st.caption(f"📅 Published: `{newer_doc.get('published_date', 'N/A')}` | Type: `{newer_doc.get('document_type', 'Circular')}` | Status: `{newer_doc.get('status', 'current').upper()}`")
                        if newer_doc.get("url"):
                            st.markdown(f"🔗 [Official Circular Link]({newer_doc.get('url')})")
                        st.markdown('</div>', unsafe_allow_html=True)

                    # Relationship and Confidence Badges
                    rel_color = "badge-green" if rel_type == "SUPERSEDES" else ("badge-amber" if rel_type == "UPDATE" else "badge-gray")
                    st.markdown(
                        f'<span class="badge {rel_color}">Relationship: {rel_type} (Confidence: {rel_conf})</span>'
                        f'<span class="badge badge-blue">Chronology Confidence: {order_conf}</span>'
                        f'{"<span class=\"badge badge-purple\">⚡ CACHE HIT</span>" if comp_res.get("cached") else ""}',
                        unsafe_allow_html=True
                    )

                    # Uncertainty warnings
                    if rel_conf in ("LOW", "UNKNOWN"):
                        st.warning("⚠️ **Notice**: The relationship between these documents was determined with low confidence. Verify specific regulatory applicability.")
                    if order_conf in ("LOW", "UNKNOWN"):
                        st.info("ℹ️ **Notice**: Chronological ordering could not be determined with high confidence due to identical or missing publication dates.")

                    st.divider()

                    # 2. Executive Change Summary
                    st.markdown("### 📊 Executive Change Summary")
                    exec_summary = comp_res.get("executive_summary") or comp_res.get("summary", "Comparison completed.")
                    st.markdown(exec_summary)

                    # Key Changes Bullet Points
                    key_changes = comp_res.get("key_changes", [])
                    if key_changes:
                        st.markdown("##### 📌 Key Substantive Changes:")
                        for k in key_changes:
                            st.markdown(f"* {k}")

                    # 3. Section Statistics Metric Boxes
                    stats = comp_res.get("statistics", {})
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Total Analyzed", comp_res.get("total_changes", 0))
                    m2.metric("🟢 Added", comp_res.get("added_count", 0))
                    m3.metric("🔴 Removed", comp_res.get("removed_count", 0))
                    m4.metric("🟡 Modified", comp_res.get("modified_count", 0))
                    m5.metric("⚪ Unchanged", comp_res.get("unchanged_count", 0))
                    st.divider()

                    # 4. Detailed Section Changes & Side-by-Side View
                    changes = comp_res.get("changes", [])
                    st.markdown(f"### 📋 Section-by-Section Delta Breakdown ({len(changes)})")

                    filter_ctype = st.radio(
                        "Filter Changes by Type:",
                        options=["ALL", "MODIFIED", "ADDED", "REMOVED", "UNCHANGED"],
                        horizontal=True
                    )

                    filtered_changes = [
                        ch for ch in changes
                        if filter_ctype == "ALL" or ch.get("change_type") == filter_ctype
                    ]

                    for ch in filtered_changes:
                        ctype = ch.get("change_type", "MODIFIED")
                        heading = ch.get("heading", "Untitled Section")
                        sec_num = ch.get("section") or ""
                        badge_cls = {
                            "ADDED": "badge-green",
                            "REMOVED": "badge-red",
                            "MODIFIED": "badge-amber",
                            "UNCHANGED": "badge-gray"
                        }.get(ctype, "badge-blue")

                        title_display = f"[{ctype}] {f'Sec {sec_num}: ' if sec_num else ''}{heading}"

                        with st.expander(title_display, expanded=(ctype == "MODIFIED")):
                            st.markdown(
                                f'<span class="badge {badge_cls}">{ctype}</span>'
                                f'<span class="badge badge-gray">{ch.get("modification_category", "GENERAL").upper()}</span>',
                                unsafe_allow_html=True
                            )
                            if ch.get("summary"):
                                st.markdown(f"**Change Summary**: {ch.get('summary')}")
                            if ch.get("impact") or ch.get("compliance_impact"):
                                st.markdown(f"**Compliance Impact**: `{ch.get('impact') or ch.get('compliance_impact')}`")

                            # Side-by-Side Text Comparison for Modified Sections
                            if ctype == "MODIFIED" and (ch.get("previous_text") or ch.get("current_text")):
                                st.markdown("##### 🔍 Side-by-Side Comparison")
                                col_old, col_new = st.columns(2)
                                with col_old:
                                    st.markdown("**Previous Text (Older)**")
                                    st.markdown(f'<div class="diff-box-old">{ch.get("previous_text", "N/A")}</div>', unsafe_allow_html=True)
                                with col_new:
                                    st.markdown("**Current Text (Newer)**")
                                    st.markdown(f'<div class="diff-box-new">{ch.get("current_text", "N/A")}</div>', unsafe_allow_html=True)

                            elif ctype == "ADDED" and ch.get("current_text"):
                                st.markdown("##### ➕ Newly Introduced Text")
                                st.markdown(f'<div class="diff-box-new">{ch.get("current_text")}</div>', unsafe_allow_html=True)

                            elif ctype == "REMOVED" and ch.get("previous_text"):
                                st.markdown("##### ➖ Omitted / Repealed Text")
                                st.markdown(f'<div class="diff-box-old">{ch.get("previous_text")}</div>', unsafe_allow_html=True)

                            # Evidence References
                            old_s = ch.get("old_source")
                            new_s = ch.get("new_source")
                            if old_s or new_s:
                                st.markdown("##### 📚 Evidence Sources:")
                                if old_s:
                                    st.caption(f"• **Older Source**: `{old_s.get('document_id', '')[:12]}` | Section: `{old_s.get('heading')}`")
                                if new_s:
                                    st.caption(f"• **Newer Source**: `{new_s.get('document_id', '')[:12]}` | Section: `{new_s.get('heading')}`")

                    # 5. Export Report
                    st.divider()
                    st.markdown("### 📥 Export Comparison Report")
                    report_json = json.dumps(comp_res, indent=2)
                    st.download_button(
                        label="Download Report as JSON",
                        data=report_json,
                        file_name=f"regintel_comparison_{older_doc.get('document_id', 'docA')[:8]}_{newer_doc.get('document_id', 'docB')[:8]}.json",
                        mime="application/json"
                    )

                except Exception as e:
                    st.error(f"Comparison Error: {e}")
                    st.info("Please verify the document IDs or check backend status.")


# =========================================================================
# TAB 3: LATEST CHANGES & VERSION LINEAGE
# =========================================================================
with tab_latest:
    st.subheader("Latest Regulatory Circulars & Version Lineage Graph")

    col_l1, col_l2, col_l3 = st.columns([2, 3, 2])
    with col_l1:
        latest_src = st.selectbox("Authority Filter", options=["", "SEBI"], index=0, key="latest_src")
    with col_l2:
        latest_cat = st.selectbox("Category Filter", options=["", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories"], index=0, key="latest_cat")
    with col_l3:
        latest_lim = st.slider("Limit", min_value=5, max_value=30, value=15, key="latest_lim")

    refresh_latest = st.button("🔄 Refresh Regulatory List")

    try:
        docs = client.get_latest(
            source=latest_src if latest_src else None,
            category=latest_cat if latest_cat else None,
            limit=latest_lim
        )

        st.markdown(f"**Found {len(docs)} Recent Regulatory Documents**")

        for d in docs:
            d_id = d.get("document_id", "")
            d_title = d.get("title") or "Regulatory Circular"
            d_status = d.get("status", "unknown").upper()
            badge_color = "badge-green" if d_status == "CURRENT" else ("badge-amber" if d_status == "HISTORICAL" else "badge-gray")

            with st.container():
                st.markdown(f"#### {d_title}")
                st.markdown(
                    f'<span class="badge {badge_color}">Status: {d_status}</span>'
                    f'<span class="badge badge-blue">{d.get("source", "SEBI")}</span>'
                    f'<span class="badge badge-gray">{d.get("category") or "General"}</span>'
                    f'<span class="badge badge-gray">Version {d.get("document_version", "1.0")}</span>',
                    unsafe_allow_html=True
                )
                col_i1, col_i2, col_i3 = st.columns(3)
                col_i1.caption(f"**Published**: {d.get('published_date', 'N/A')}")
                col_i2.caption(f"**Effective**: {d.get('effective_date', 'N/A')}")
                col_i3.caption(f"**Circular No**: `{d.get('circular_number', 'N/A')}`")

                # Version relationship & Timeline details
                with st.expander(f"🔍 Version Lineage & Timeline for {d_id[:12]}..."):
                    st.code(f"Document ID: {d_id}")
                    try:
                        v_info = client.get_document_versions(d_id)
                        st.markdown(f"- **Relationship Type**: `{v_info.get('relationship_type', 'NEW')}` (Confidence: `{v_info.get('relationship_confidence', 'low')}`)")
                        if v_info.get("predecessor"):
                            st.markdown(f"- **Supersedes (Predecessor)**: {v_info['predecessor'].get('title')} (`{v_info['predecessor'].get('published_date')}`)")
                        if v_info.get("successor"):
                            st.markdown(f"- **Superseded By (Successor)**: {v_info['successor'].get('title')} (`{v_info['successor'].get('published_date')}`)")

                        timeline = v_info.get("timeline", [])
                        if timeline:
                            st.markdown("**Chronological Lineage Timeline:**")
                            for node in timeline:
                                status_ico = "🟢" if node.get("status") == "current" else "📜"
                                is_curr = "👈 (This Document)" if node.get("document_id") == d_id else ""
                                st.markdown(f"  {status_ico} **{node.get('title')}** ({node.get('published_date', 'N/A')}) — `[{node.get('status').upper()}]` {is_curr}")
                    except Exception as ex:
                        st.caption(f"Version graph metadata error: {ex}")
                st.divider()

    except Exception as e:
        st.error(f"Error loading latest documents: {e}")


# =========================================================================
# TAB 4: SEARCH EVIDENCE
# =========================================================================
with tab_search:
    st.subheader("Multi-Method Evidence Search")
    st.caption("Search across regulatory chunks without LLM answer generation.")

    search_query = st.text_input("Search Query:", placeholder="e.g. Investment advisory agreement client obligations")
    search_btn = st.button("🔎 Execute Search", type="primary")

    if search_btn and search_query.strip():
        with st.spinner("Searching regulatory evidence..."):
            try:
                s_res = client.search_documents(
                    query=search_query.strip(),
                    top_k=top_k_val,
                    retrieval_mode=retrieval_mode
                )

                st.markdown(f"**Retrieved {s_res.get('total_results', 0)} chunks using `{s_res.get('retrieval_mode')}` mode:**")

                for item in s_res.get("results", []):
                    with st.expander(f"Rank #{item.get('rank')} — {item.get('title')} (Score: {item.get('score')})"):
                        st.markdown(f"**Section**: `{item.get('section')}` | **Category**: `{item.get('category')}`")
                        st.markdown(f"**Snippet**: {item.get('content_snippet')}")
                        if item.get("url"):
                            st.markdown(f"🔗 [Open Document Link]({item.get('url')})")

            except Exception as e:
                st.error(f"Search Error: {e}")
