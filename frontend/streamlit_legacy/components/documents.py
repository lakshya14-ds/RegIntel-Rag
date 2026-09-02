"""
Document Catalog & Multi-Method Search Components for RegIntel Frontend.
"""

import streamlit as st
from typing import List, Dict, Any, Optional
from frontend.utils import format_date, get_status_badge
from frontend.api_client import RegIntelAPIClient


def render_latest_documents_page(client: RegIntelAPIClient) -> None:
    """
    Renders the Latest Regulations Catalog with filtering and document cards.
    """
    st.subheader("📜 Latest Regulatory Documents & Circulars")
    st.caption("Browse recently indexed regulatory circulars, master directions, and compliance notices.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        source_filter = st.selectbox("Authority Filter", options=["All", "SEBI"], index=0, key="latest_page_src")
    with col2:
        category_filter = st.selectbox(
            "Category Filter",
            options=["All", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories", "Securities Markets"],
            index=0,
            key="latest_page_cat"
        )
    with col3:
        doc_type_filter = st.selectbox(
            "Document Type",
            options=["All", "Circular", "Master Circular", "Notification", "Order", "Advisory"],
            index=0,
            key="latest_page_type"
        )
    with col4:
        limit_val = st.slider("Documents Limit", min_value=5, max_value=50, value=20, key="latest_page_limit")

    try:
        docs = client.get_latest(
            source=source_filter if source_filter != "All" else None,
            category=category_filter if category_filter != "All" else None,
            limit=limit_val
        )

        if doc_type_filter != "All":
            docs = [d for d in docs if (d.get("document_type") or "").lower() == doc_type_filter.lower()]

        st.markdown(f"**Displaying {len(docs)} Regulatory Documents**")

        if not docs:
            st.info("No documents found matching the specified filters.")
            return

        for doc in docs:
            doc_id = doc.get("document_id", "")
            title = doc.get("title") or "Regulatory Circular"
            pub_date = format_date(doc.get("published_date"))
            eff_date = format_date(doc.get("effective_date"))
            status = doc.get("status", "unknown")
            source = doc.get("source", "SEBI")
            category = doc.get("category", "General")
            circ_no = doc.get("circular_number", "N/A")
            url = doc.get("url", "")

            with st.container():
                st.markdown('<div class="doc-card">', unsafe_allow_html=True)
                st.markdown(f"#### {title}")
                st.markdown(
                    f'{get_status_badge(status)}'
                    f'<span class="badge badge-blue">{source}</span>'
                    f'<span class="badge badge-gray">{category}</span>'
                    f'<span class="badge badge-purple">{doc.get("document_type", "Circular")}</span>',
                    unsafe_allow_html=True
                )

                c1, c2, c3 = st.columns(3)
                c1.markdown(f"📅 **Published**: `{pub_date}`")
                c2.markdown(f"⚡ **Effective**: `{eff_date}`")
                c3.markdown(f"🔢 **Circular No**: `{circ_no}`")

                st.caption(f"Document ID: `{doc_id}`")
                if url:
                    st.markdown(f"🔗 [Open Official {source} Circular Link]({url})")
                st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error loading regulatory catalog: {e}")
        st.info("Please ensure the FastAPI backend is running.")


def render_search_page(client: RegIntelAPIClient, default_mode: str = "hybrid", default_top_k: int = 10) -> None:
    """
    Renders the Search Documents page exposing the /search multi-method API.
    """
    st.subheader("🔎 Search Indexed Regulatory Evidence")
    st.caption("Perform multi-method keyword (BM25), dense vector, or neural reranked candidate search across the indexed corpus.")

    col_q, col_btn = st.columns([4, 1])
    with col_q:
        search_query = st.text_input(
            "Enter compliance search terms:",
            placeholder="e.g. investment adviser client agreement fee limit segregation"
        )
    with col_btn:
        st.write("")
        st.write("")
        do_search = st.button("🔎 Search", type="primary", use_container_width=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        search_mode = st.selectbox(
            "Retrieval Method",
            options=["hybrid", "hybrid_reranked", "bm25", "vector"],
            index=0,
            key="search_tab_mode"
        )
    with col_m2:
        search_cat = st.selectbox(
            "Category Filter (Optional)",
            options=["All", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories"],
            index=0,
            key="search_tab_cat"
        )
    with col_m3:
        search_top_k = st.slider("Result Count", min_value=1, max_value=25, value=default_top_k, key="search_tab_k")

    if do_search and search_query.strip():
        with st.spinner("Searching regulatory evidence..."):
            try:
                res = client.search_documents(
                    query=search_query.strip(),
                    top_k=search_top_k,
                    retrieval_mode=search_mode,
                    category=search_cat if search_cat != "All" else None
                )

                results = res.get("results", [])
                st.markdown(f"**Found {len(results)} Evidence Chunks (Mode: `{res.get('retrieval_mode')}`):**")

                if not results:
                    st.info("No evidence chunks matched your query.")
                    return

                for item in results:
                    rank = item.get("rank", 1)
                    title = item.get("title", "Regulatory Chunk")
                    score = item.get("score", 0.0)
                    section = item.get("section", "General")
                    category = item.get("category", "General")
                    source = item.get("source", "SEBI")
                    pub_date = format_date(item.get("published_date"))
                    snippet = item.get("content_snippet", "")
                    url = item.get("url", "")
                    chunk_id = item.get("chunk_id", "")

                    with st.expander(f"Rank #{rank} | {title} (Score: {score})", expanded=(rank <= 3)):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f"**Section**: `{section}`")
                        c2.markdown(f"**Category**: `{category}`")
                        c3.markdown(f"**Authority**: `{source}`")
                        c4.markdown(f"**Published**: `{pub_date}`")

                        st.markdown("**Evidence Snippet:**")
                        st.info(snippet)

                        st.caption(f"Chunk ID: `{chunk_id}` | Document ID: `{item.get('document_id')}`")
                        if url:
                            st.markdown(f"🔗 [Open Original Circular]({url})")

            except Exception as e:
                st.error(f"Search failed: {e}")
                st.info("Please verify that the FastAPI backend server is accessible.")
