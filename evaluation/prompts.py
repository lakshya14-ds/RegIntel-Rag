"""
Evaluation Prompts and LLM Judge Rubrics for RegIntel RAG Evaluation.
"""

from typing import Optional, List, Dict, Any

LLM_JUDGE_SYSTEM_PROMPT = """You are an expert impartial evaluator for a Regulatory RAG Intelligence system (SEBI).

Your task is to evaluate the quality, completeness, and factual relevance of a generated answer using ONLY the supplied retrieved evidence.

Strict Evaluation Rubrics:
1. Answer Relevance (Score 1 to 5):
   - 5: Directly, accurately, and completely addresses the user's question.
   - 4: Addresses the core question with minor details missing.
   - 3: Partially addresses the question; somewhat vague.
   - 2: Tangentially related but misses the main question.
   - 1: Completely irrelevant or off-topic.

2. Answer Completeness (Score 1 to 5):
   - 5: Covers all major expected regulatory points without omission.
   - 4: Covers most key requirements; minor non-critical omission.
   - 3: Partially complete; covers some aspects but misses major requirements.
   - 2: Significant omissions of key regulatory requirements.
   - 1: Major expected information missing.

3. Groundedness / Faithfulness (Score 1 to 5):
   - 5: Every single claim in the answer is directly supported by the retrieved evidence.
   - 4: Almost all claims are supported; minor non-substantive extrapolation.
   - 3: Mixed support; some claims are grounded but others lack evidence.
   - 2: Mostly unsupported; contains substantial ungrounded claims.
   - 1: Fabricated or contradicted by evidence.

Do NOT use external legal knowledge beyond the provided text."""


def build_judge_prompt(
    question: str,
    evidence_text: str,
    generated_answer: str,
    reference_answer: Optional[str] = None
) -> str:
    """Builds prompt for the LLM answer quality judge."""
    ref_part = f"\nREFERENCE ANSWER:\n{reference_answer}\n" if reference_answer else "\nREFERENCE ANSWER:\n[Not available]\n"
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
Completeness: <Score 1-5>
Groundedness: <Score 1-5>
Reason: <1-2 sentences explaining scores>"""


CLAIM_EXTRACTION_PROMPT = """You are a regulatory claim extraction assistant.
Given a generated regulatory answer, break it down into atomic, substantive regulatory claims.

Rules:
1. Extract ONLY factual or normative regulatory statements (requirements, timelines, penalties, definitions, obligations).
2. Do NOT extract conversational phrases, greetings, apologies, or generic disclaimers (e.g. "Based on the provided documents...", "I hope this helps").
3. Preserve cited source tags like [1], [2] at the end of each claim if present.

Answer to extract claims from:
\"\"\"{answer}\"\"\"

Respond strictly in valid JSON format as a list of strings:
["Claim 1...", "Claim 2..."]"""


def build_claim_extraction_prompt(answer: str) -> str:
    """Builds prompt to extract substantive claims from an answer."""
    return CLAIM_EXTRACTION_PROMPT.format(answer=answer.strip())


STRICT_GROUNDING_JUDGE_PROMPT = """You are an expert regulatory auditor evaluating whether generated claims are supported by supplied evidence.

Rules:
1. Do NOT use outside knowledge. Use ONLY the provided EVIDENCE.
2. For each claim, determine if the provided evidence factually supports it:
   - SUPPORTED: The claim is directly and factually stated in or proven by the evidence.
   - PARTIALLY_SUPPORTED: The claim is partially mentioned or implied, but key details/numbers/conditions lack explicit support.
   - UNSUPPORTED: The claim is not found in the evidence, extrapolates facts, or is contradicted by the evidence.
3. Identify the supporting evidence ID(s) (e.g. ["1", "2"]) if supported, or empty list [] if unsupported.

QUESTION:
{question}

EVIDENCE:
{evidence_text}

CLAIMS TO EVALUATE:
{claims_formatted}

Respond strictly in valid JSON format matching this schema:
[
  {{
    "claim": "exact text of claim",
    "classification": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED",
    "evidence_ids": ["1"],
    "reason": "short explanation citing evidence"
  }}
]"""


def build_grounding_judge_prompt(question: str, evidence_text: str, claims: List[str]) -> str:
    """Builds prompt for claim-level grounding verification."""
    claims_formatted = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
    return STRICT_GROUNDING_JUDGE_PROMPT.format(
        question=question.strip(),
        evidence_text=evidence_text.strip() if evidence_text.strip() else "[No evidence provided]",
        claims_formatted=claims_formatted
    )
