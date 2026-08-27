import streamlit as st
import sys
import os

# Ensure app root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.rag.pipeline import RAGPipeline

st.set_page_config(
    page_title="RegIntel RAG | Indian Regulatory Intelligence",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ RegIntel RAG: Indian Financial Regulatory Intelligence")
st.caption("AI-powered compliance and regulatory intelligence search across SEBI & RBI circulars.")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    top_k_retrieve = st.slider("Top K Retrieved", min_value=3, max_value=20, value=10)
    top_k_rerank = st.slider("Top K Reranked", min_value=1, max_value=10, value=5)
    st.divider()
    st.markdown("**System Information**")
    st.write("• Vector DB: MongoDB Atlas")
    st.write("• Keyword Search: BM25")
    st.write("• Hybrid Strategy: Reciprocal Rank Fusion (RRF)")
    st.write("• Reranker: Cohere Rerank-3")

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📚 View Regulatory Sources"):
                for src in msg["sources"]:
                    st.markdown(f"- **{src.get('title', 'Unknown')}** ({src.get('source', 'Unknown')})")
                    st.caption(src.get("text", "")[:300] + "...")

# Chat Input
if prompt := st.chat_input("Ask a question about SEBI circulars, FPI regulations, LODR amendments..."):
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process Query with RAG Pipeline
    with st.chat_message("assistant"):
        with st.spinner("Analyzing regulatory corpus and synthesizing answer..."):
            try:
                pipeline = RAGPipeline()
                result = pipeline.run(
                    query=prompt,
                    top_k_retrieval=top_k_retrieve,
                    top_k_rerank=top_k_rerank
                )
                answer = result.get("answer", "No answer generated.")
                sources = result.get("sources", [])
                
                st.markdown(answer)
                if sources:
                    with st.expander("📚 View Regulatory Sources"):
                        for src in sources:
                            st.markdown(f"- **{src.get('title', 'Unknown')}** ({src.get('source', 'Unknown')})")
                            st.caption(src.get("text", "")[:300] + "...")
                            
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources
                })
            except Exception as e:
                error_msg = f"⚠️ An error occurred while processing: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
