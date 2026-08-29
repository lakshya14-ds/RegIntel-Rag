"""
Streamlit Web Frontend for RegIntel RAG — Regulatory Intelligence & Change Analysis System.

Interacts with the FastAPI backend to provide:
1. Grounded Regulatory Q&A with Citation Validation
2. Side-by-Side Regulatory Document Comparison
3. Latest Circulars & Version Lineage Graph
4. Multi-Method Search & Evidence Inspection
"""

import os
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

# Custom CSS for polished interface
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
    }
    .badge-blue { background-color: #DBEAFE; color: #1E40AF; }
    .badge-green { background-color: #DCFCE7; color: #166534; }
    .badge-amber { background-color: #FEF3C7; color: #92400E; }
    .badge-red { background-color: #FEE2E2; color: #991B1B; }
    .badge-gray { background-color: #F3F4F6; color: #374151; }
    .metric-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
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

# Navigation Tabs
tab_ask, tab_compare, tab_latest, tab_search = st.tabs([
    "🔍 Ask Regulations",
    "⚖️ Compare Documents",
    "📰 Latest Changes & Versions",
    "🔎 Search Evidence"
])


# =========================================================================
# TAB 1: ASK REGULATIONS
# =========================================================================
with tab_ask:
    st.subheader("Ask a Regulatory Compliance Question")

    # Sample prompt buttons
    st.caption("Quick sample queries:")
    col_s1, col_s2, col_s3 = st.columns(3)
    sample_q = ""
    if col_s1.button("📌 IA Record Keeping Period", use_container_width=True):
        sample_q = "What are the record keeping requirements for Investment Advisers under SEBI regulations?"
    if col_s2.button("📌 IA Fee Limits (Reg 15A)", use_container_width=True):
        sample_q = "What is the fee limit mandated under Regulation 15A for investment advisers?"
    if col_s3.button("📌 Beta Version T+0 Settlement", use_container_width=True):
        sample_q = "What is the Beta Version of T+0 Settlement introduced by SEBI?"

    question_input = st.text_area(
        "Regulatory Question:",
        value=sample_q if sample_q else "",
        placeholder="Enter your regulatory or compliance question here...",
        height=100
    )

    col_btn, col_cat, col_src = st.columns([2, 3, 2])
    with col_cat:
        category_filter = st.selectbox(
            "Category Filter (Optional)",
            options=["", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories"],
            index=0
        )
    with col_src:
        source_filter = st.selectbox("Authority", options=["SEBI", "All"], index=0)

    ask_clicked = st.button("🚀 Ask RegIntel AI", type="primary", use_container_width=True)

    if ask_clicked:
        if not question_input.strip():
            st.warning("Please enter a question before submitting.")
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
# TAB 2: COMPARE DOCUMENTS
# =========================================================================
with tab_compare:
    st.subheader("Direct Regulatory Document Comparison")
    st.caption("Align sections between two circulars and inspect classified deltas.")

    if st.button("📋 Load Sample IA Comparison Pair"):
        st.session_state["doc_a_id"] = "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
        st.session_state["doc_b_id"] = "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"

    col_a, col_b = st.columns(2)
    with col_a:
        doc_a_input = st.text_input(
            "Document A ID (Predecessor):",
            value=st.session_state.get("doc_a_id", ""),
            placeholder="e.g. af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab"
        )
    with col_b:
        doc_b_input = st.text_input(
            "Document B ID (Current / Updated):",
            value=st.session_state.get("doc_b_id", ""),
            placeholder="e.g. 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"
        )

    compare_clicked = st.button("⚖️ Compare Regulatory Documents", type="primary")

    if compare_clicked:
        if not doc_a_input.strip() or not doc_b_input.strip():
            st.warning("Please provide both Document A and Document B IDs.")
        else:
            with st.spinner("Analyzing document sections and classifying regulatory deltas..."):
                try:
                    comp_res = client.compare_documents(doc_a_input.strip(), doc_b_input.strip())

                    st.markdown("### 📊 Executive Change Summary")
                    st.markdown(comp_res.get("summary", "Comparison completed."))

                    # Metric boxes
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Total Analyzed", comp_res.get("total_changes", 0))
                    m2.metric("🟢 Added", comp_res.get("added_count", 0))
                    m3.metric("🔴 Removed", comp_res.get("removed_count", 0))
                    m4.metric("🟡 Modified", comp_res.get("modified_count", 0))
                    m5.metric("⚪ Unchanged", comp_res.get("unchanged_count", 0))
                    st.divider()

                    # Section changes
                    changes = comp_res.get("changes", [])
                    st.markdown(f"### 📋 Section-by-Section Delta Breakdown ({len(changes)})")

                    for ch in changes:
                        ctype = ch.get("change_type", "MODIFIED")
                        heading = ch.get("heading", "Untitled Section")
                        badge_cls = {
                            "ADDED": "badge-green",
                            "REMOVED": "badge-red",
                            "MODIFIED": "badge-amber",
                            "UNCHANGED": "badge-gray"
                        }.get(ctype, "badge-blue")

                        with st.expander(f"[{ctype}] {heading} ({ch.get('category', 'GENERAL')})"):
                            st.markdown(f'<span class="badge {badge_cls}">{ctype}</span>', unsafe_allow_html=True)
                            st.markdown(f"**Change Summary**: {ch.get('summary')}")
                            if ch.get("compliance_impact"):
                                st.markdown(f"**Compliance Impact**: `{ch.get('compliance_impact')}`")
                            if ch.get("similarity_score") is not None:
                                st.markdown(f"*Structural Similarity*: `{ch.get('similarity_score')}`")

                except Exception as e:
                    st.error(f"Comparison Error: {e}")


# =========================================================================
# TAB 3: LATEST CHANGES & VERSION LINEAGE
# =========================================================================
with tab_latest:
    st.subheader("Latest Regulatory Circulars & Version Lineage")

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

                # Version relationship details
                with st.expander(f"🔍 Version Relationships & Lineage for {d_id[:12]}..."):
                    st.code(f"Document ID: {d_id}")
                    try:
                        v_info = client.get_document_versions(d_id)
                        st.markdown(f"- **Relationship Type**: `{v_info.get('relationship_type', 'NEW')}` (Confidence: `{v_info.get('relationship_confidence', 'low')}`)")
                        st.markdown(f"- **Predecessor (Supersedes)**: `{v_info.get('supersedes') or 'None identified'}`")
                        st.markdown(f"- **Successor (Superseded By)**: `{v_info.get('superseded_by') or 'None (Current version)'}`")
                    except Exception:
                        st.caption("Version graph metadata not loaded.")
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
