"""
Evaluation Prompts and LLM Judge Rubrics for RegIntel RAG Evaluation.
"""

from typing import Optional

LLM_JUDGE_SYSTEM_PROMPT = """You are an impartial expert evaluator for a Regulatory RAG Intelligence system.

Your task is to evaluate the quality, faithfulness, and citation accuracy of a generated answer using ONLY the supplied retrieved evidence.

Strict Evaluation Guidelines:
1. Groundedness / Faithfulness (Score 1 to 5):
   - 5: Every single claim in the answer is directly supported by the retrieved evidence.
   - 4: Almost all claims are supported; minor non-substantive extrapolation.
   - 3: Mixed support; some claims are grounded but others lack evidence.
   - 2: Mostly unsupported; contains substantial ungrounded claims.
   - 1: Fabricated or contradicted by evidence.

2. Answer Relevance (Score 1 to 5):
   - 5: Directly, accurately, and completely addresses the user's question.
   - 4: Addresses the core question with minor details missing.
   - 3: Partially addresses the question; somewhat vague.
   - 2: Tangentially related but misses the main question.
   - 1: Completely irrelevant or off-topic.

3. Citation Correctness (Score 1 to 5):
   - 5: All claims correctly attribute the appropriate source ID [1], [2], etc., without hallucinated tags.
   - 4: Mostly correct citations with minor formatting or slight omission.
   - 3: Citations present but some are incorrectly mapped.
   - 2: Citation tags out of bounds or ungrounded.
   - 1: Zero citations for substantive claims or entirely hallucinated source IDs.

Do NOT use external legal knowledge beyond the provided text."""


def build_judge_prompt(
    question: str,
    evidence_text: str,
    generated_answer: str,
    reference_answer: Optional[str] = None
) -> str:
    """Builds prompt for the LLM judge."""
    ref_part = f"\nREFERENCE ANSWER:\n{reference_answer}\n" if reference_answer else ""
    return f"""{LLM_JUDGE_SYSTEM_PROMPT}

QUESTION:
{question}

RETRIEVED EVIDENCE:
{evidence_text.strip() if evidence_text.strip() else "[No evidence retrieved]"}
{ref_part}
GENERATED ANSWER:
{generated_answer.strip()}

Please evaluate and respond strictly in the following format:
Relevance: <Score 1-5>
Groundedness: <Score 1-5>
Citation_Correctness: <Score 1-5>
Reason: <1-2 sentences explaining scores>"""
