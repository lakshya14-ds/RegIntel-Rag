"""
Citation Display Component for RegIntel Streamlit Frontend.
"""

import streamlit as st
from typing import List, Dict, Any


def render_citations_section(sources: List[Dict[str, Any]]) -> None:
    """
    Renders expandable citation sources corresponding directly to the final retrieved evidence.
    """
    st.markdown(f"### 📚 SOURCES ({len(sources)})")

    if not sources:
        st.info("No specific regulatory sources cited.")
        return

    for s in sources:
        source_id = s.get("source_id", 1)
        title = s.get("title", "Regulatory Document")
        section = s.get("section", "General")
        published_date = s.get("published_date", "N/A")
        effective_date = s.get("effective_date", "N/A")
        score = s.get("score", 0.0)
        authority = s.get("source", "SEBI")
        doc_id = s.get("document_id", "")
        url = s.get("url", "")

        header_title = f"[{source_id}] {title} — Section: {section}"

        with st.expander(header_title, expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Regulatory Authority**: `{authority}`")
            c2.markdown(f"**Published Date**: `{published_date}`")
            c3.markdown(f"**Effective Date**: `{effective_date}`")

            st.markdown(f"**Relevance Score**: `{score}` | **Document ID**: `{doc_id}`")

            if url:
                st.markdown(f"🔗 [Open Official {authority} Circular]({url})")
            else:
                st.caption("Official URL not available.")
