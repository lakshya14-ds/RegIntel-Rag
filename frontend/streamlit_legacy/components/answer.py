"""
Answer and Query Intent Display Component for RegIntel Streamlit Frontend.
"""

import streamlit as st
from typing import Dict, Any, List, Optional


def render_query_intent(intent: Optional[Dict[str, Any]]) -> None:
    """
    Renders an optional expandable 'How the system interpreted your query' section.
    """
    if not intent:
        return

    with st.expander("🔍 How the system interpreted your query", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Authority (Source)**: `{intent.get('source') or 'SEBI'}`")
        c2.markdown(f"**Category**: `{intent.get('category') or 'General'}`")
        c3.markdown(f"**Query Type**: `{intent.get('query_type') or 'general_search'}`")
        c4.markdown(f"**Time Intent**: `{intent.get('time_intent') or 'none'}`")

        if intent.get("circular_number"):
            st.caption(f"Target Circular No: `{intent.get('circular_number')}`")
        if intent.get("document_type"):
            st.caption(f"Document Type: `{intent.get('document_type')}`")


def render_answer_section(response_data: Dict[str, Any]) -> None:
    """
    Renders the grounded regulatory answer along with query intent and key evidence summary.
    """
    answer_text = response_data.get("answer", "No response generated.")
    sufficient_evidence = response_data.get("sufficient_evidence", True)

    if not sufficient_evidence or "could not find sufficient evidence" in answer_text.lower():
        st.warning("⚠️ **Limited Evidence in Index**: The system refrained from fabricating compliance details.")

    # 1. Grounded Answer
    st.markdown("### 💡 ANSWER")
    st.markdown(answer_text)

    # 2. Key Evidence Summary (if sources present)
    sources: List[Dict[str, Any]] = response_data.get("sources", [])
    if sources:
        st.markdown("### 🔍 KEY EVIDENCE")
        for s in sources:
            sid = s.get("source_id", 1)
            title = s.get("title", "Regulatory Circular")
            section = s.get("section", "General")
            pub_date = s.get("published_date", "N/A")
            st.markdown(f"**[{sid}]** `{title}` — *Section: {section}* (Published: `{pub_date}`)")

    st.divider()
