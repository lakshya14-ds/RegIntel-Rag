"""
Streamlit Web Frontend for RegIntel RAG — Regulatory Intelligence & Change Analysis System.

Interacts exclusively with the FastAPI REST backend:
1. Ask RegIntel (Grounded Regulatory Q&A with Citation Validation & Intent Analysis)
2. Compare Regulations (4-Tier Structural Alignment & Compliance Delta Engine)
3. Latest Regulations (Regulatory Catalog with Category/Authority Filtering)
4. Search Documents (Multi-Method BM25/Vector/Hybrid Evidence Search)
5. Document Timeline (Regulatory Version Lineage & Predecessor/Successor Graph)
"""

import streamlit as st
from frontend.api_client import RegIntelAPIClient
from frontend.components.answer import render_answer_section, render_query_intent
from frontend.components.citations import render_citations_section
from frontend.components.documents import render_latest_documents_page, render_search_page
from frontend.components.comparison import render_comparison_page
from frontend.components.timeline import render_timeline_page

# Page configuration
st.set_page_config(
    page_title="RegIntel RAG — Regulatory Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Polished styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .badge {
        display: inline-block;
        padding: 0.22rem 0.55rem;
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
        margin-bottom: 0.8rem;
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

# -------------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/scales.png", width=56)
    st.title("RegIntel RAG")
    st.caption("Regulatory Intelligence & Compliance Delta Engine")
    st.divider()

    # Health check
    health = client.health_check()
    status_str = health.get("status", "unavailable")
    status_icon = "🟢" if status_str == "ok" else ("🟡" if status_str == "degraded" else "🔴")
    st.markdown(f"**Backend Status**: {status_icon} `{status_str.upper()}`")
    st.markdown(f"* MongoDB: `{'Online' if health.get('mongodb') else 'Offline/Local'}`")
    st.markdown(f"* Embeddings: `{'Active' if health.get('embedding_service') else 'Inactive'}`")

    if status_str == "unavailable":
        st.warning("⚠️ RegIntel backend is currently unavailable. Please start the FastAPI service (`uvicorn app.main:app --port 8000`).")

    st.divider()
    st.subheader("Retrieval Engine Settings")
    sidebar_mode = st.selectbox(
        "Default Mode",
        options=["hybrid", "hybrid_reranked", "bm25", "vector"],
        index=0,
        help="Select default retrieval algorithm for Q&A and search"
    )
    sidebar_top_k = st.slider("Evidence Top-K", min_value=1, max_value=15, value=5)
    st.divider()
    st.caption("RegIntel RAG v1.0.0 | SEBI Corpus")


# -------------------------------------------------------------------------
# Header & Navigation
# -------------------------------------------------------------------------
st.markdown('<div class="main-header">⚖️ RegIntel RAG</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Regulatory Intelligence, Structural Comparison & Version Tracking</div>', unsafe_allow_html=True)

tab_ask, tab_compare, tab_latest, tab_search, tab_timeline = st.tabs([
    "💬 Ask RegIntel",
    "⚖️ Compare Regulations",
    "📜 Latest Regulations",
    "🔎 Search Documents",
    "⏳ Document Timeline"
])

# -------------------------------------------------------------------------
# TAB 1: ASK REGINTEL
# -------------------------------------------------------------------------
with tab_ask:
    st.subheader("Grounded Regulatory Question Answering")
    st.caption("Ask compliance queries grounded strictly in SEBI circulars with deterministic citations.")

    col_q1, col_q2 = st.columns([3, 1])
    with col_q1:
        sample_queries = [
            "",
            "What are the latest SEBI requirements for investment advisers?",
            "What is the effective date of this circular?",
            "What changed in the latest regulation?",
            "What is the required qualification and net worth for Investment Advisers under SEBI regulations?",
            "How long must investment advisers maintain client records and books of account?"
        ]
        selected_sample = st.selectbox("💡 Example starter questions:", options=sample_queries, index=0)

    question_input = st.text_area(
        "Enter your regulatory question:",
        value=selected_sample if selected_sample else "",
        height=85,
        placeholder="e.g. What are the audit obligations and submission deadlines for SEBI registered investment advisers?"
    )

    col_f1, col_f2, col_btn = st.columns([2, 2, 2])
    with col_f1:
        cat_filter = st.selectbox(
            "Category Filter (Optional)",
            options=["", "Investment Adviser", "Mutual Funds", "Stock Brokers", "Research Analysts", "Depositories"],
            index=0,
            key="ask_cat_filter"
        )
    with col_f2:
        src_filter = st.selectbox("Regulatory Authority", options=["All", "SEBI"], index=0, key="ask_src_filter")
    with col_btn:
        st.write("")
        st.write("")
        ask_button = st.button("🚀 Ask RegIntel", type="primary", use_container_width=True)

    if ask_button:
        if not question_input.strip():
            st.error("Validation Error: Please enter a regulatory question before submitting.")
        else:
            with st.spinner("Analyzing query & searching regulatory sources..."):
                try:
                    res = client.ask_question(
                        question=question_input.strip(),
                        top_k=sidebar_top_k,
                        retrieval_mode=sidebar_mode,
                        category=cat_filter if cat_filter else None,
                        source=src_filter if src_filter != "All" else None
                    )

                    # 1. Answer & Key Evidence
                    render_answer_section(res)

                    # 2. Citations
                    render_citations_section(res.get("sources", []))

                    # 3. Query Intent
                    render_query_intent(res.get("query_intent"))

                except Exception as e:
                    st.error("RegIntel backend is currently unavailable.")
                    st.caption(f"Details: {e}")

# -------------------------------------------------------------------------
# TAB 2: COMPARE REGULATIONS
# -------------------------------------------------------------------------
with tab_compare:
    render_comparison_page(client)

# -------------------------------------------------------------------------
# TAB 3: LATEST REGULATIONS
# -------------------------------------------------------------------------
with tab_latest:
    render_latest_documents_page(client)

# -------------------------------------------------------------------------
# TAB 4: SEARCH DOCUMENTS
# -------------------------------------------------------------------------
with tab_search:
    render_search_page(client, default_mode=sidebar_mode, default_top_k=sidebar_top_k)

# -------------------------------------------------------------------------
# TAB 5: DOCUMENT TIMELINE
# -------------------------------------------------------------------------
with tab_timeline:
    render_timeline_page(client)
