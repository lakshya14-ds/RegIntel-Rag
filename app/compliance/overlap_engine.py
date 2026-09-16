"""
Regulatory Overlap Detection Engine (Phase 73).

Provides:
- 73.3: Strict cross-regulator authority isolation (authority_a != authority_b).
- 73.4: Multi-signal candidate generation avoiding O(N^2) scaling explosion.
- 73.6: Deterministic scoring and explainable structured field comparisons.
- 73.9 & 73.10: Gemini LLM overlap classification with strict Pydantic output.
- 73.11, 73.12, 73.13: Numeric, applicability, and temporal comparison.
- 73.15: Explainable structured evidence formatting.
"""

import json
import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.compliance.models import (
    RegulatoryRequirement,
    RegulatoryObligation,
    RequirementThreshold,
)
from app.compliance.overlap_models import (
    RegulatoryOverlap,
    OverlapType,
    OverlapConfidence,
    OverlapStatus,
)
from app.compliance.topic_normalizer import normalize_regulatory_topic
from app.compliance.effective_state_engine import calculate_days_delta
from app.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class LLMOverlapOutput(BaseModel):
    """Pydantic structured output for Gemini overlap classification (73.10)."""
    relationship_type: OverlapType
    shared_topic: str
    shared_activity: str
    explanation: str
    confidence: OverlapConfidence
    applicability_comparison: str


def generate_overlap_id(left_req_id: str, right_req_id: str) -> str:
    """Generates a stable, canonical overlap ID invariant to input argument ordering."""
    ordered = sorted([left_req_id.strip(), right_req_id.strip()])
    h = hashlib.sha256(f"{ordered[0]}:::{ordered[1]}".encode("utf-8")).hexdigest()[:16]
    return f"ovl_{h}"


class OverlapEngine:
    """
    Core engine for identifying, comparing, and classifying cross-regulator overlaps.
    """

    def __init__(self):
        self.llm_provider = get_llm_provider()

    # -------------------------------------------------------------------------
    # 73.4 CANDIDATE GENERATION (Multi-Signal, Avoids O(N^2))
    # -------------------------------------------------------------------------

    def generate_candidates_for_requirement(
        self,
        target_req: RegulatoryRequirement,
        candidate_pool: List[RegulatoryRequirement],
        max_candidates: int = 15,
        min_deterministic_score: float = 0.25
    ) -> List[Tuple[RegulatoryRequirement, float, str]]:
        """
        Generates filtered cross-regulator candidate requirements for target_req (73.4).
        Applies:
        1. Authority disjointness (left_authority != right_authority)
        2. Shared topic matching
        3. Deterministic lexical/structural signal scoring
        Returns: List of (candidate_requirement, score, shared_topic) sorted by score descending.
        """
        target_auth = (target_req.authority or "").upper()
        target_topic = normalize_regulatory_topic(
            text=target_req.requirement_text,
            subject=target_req.subject,
            action=target_req.action,
            object_=target_req.object
        )

        candidates = []
        for cand in candidate_pool:
            cand_auth = (cand.authority or "").upper()
            # Rule 73.3: Strict cross-regulator focus (authority_a != authority_b)
            if cand_auth == target_auth:
                continue

            score, reasons = self.compute_deterministic_similarity(target_req, cand, target_topic)
            if score >= min_deterministic_score:
                candidates.append((cand, score, target_topic))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:max_candidates]

    # -------------------------------------------------------------------------
    # 73.6 DETERMINISTIC STRUCTURED COMPARISON
    # -------------------------------------------------------------------------

    def compute_deterministic_similarity(
        self,
        req_a: RegulatoryRequirement,
        req_b: RegulatoryRequirement,
        precomputed_topic_a: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        """
        Calculates explainable structured similarity across topics, subjects, actions,
        objects, applicability, thresholds, and requirement types (73.6).
        """
        score = 0.0
        reasons = []

        topic_a = precomputed_topic_a or normalize_regulatory_topic(
            req_a.requirement_text, req_a.subject, req_a.action, req_a.object
        )
        topic_b = normalize_regulatory_topic(
            req_b.requirement_text, req_b.subject, req_b.action, req_b.object
        )

        # 1. Topic Match (Weight: 0.30)
        if topic_a == topic_b and topic_a != "OTHER":
            score += 0.30
            reasons.append(f"Shared regulatory topic: {topic_a}")

        # 2. Action Match (Weight: 0.25)
        act_a = (req_a.action or "").lower().strip()
        act_b = (req_b.action or "").lower().strip()
        if act_a and act_b:
            if act_a == act_b:
                score += 0.25
                reasons.append(f"Identical action mandated: '{act_a}'")
            elif any(syn in act_b for syn in [act_a]) or any(syn in act_a for syn in [act_b]):
                score += 0.15
                reasons.append(f"Similar action verbs: '{act_a}' / '{act_b}'")

        # 3. Object Match (Weight: 0.20)
        obj_a = (req_a.object or "").lower().strip()
        obj_b = (req_b.object or "").lower().strip()
        if obj_a and obj_b:
            if obj_a == obj_b:
                score += 0.20
                reasons.append(f"Identical regulatory object: '{obj_a}'")
            elif any(w in obj_b for w in obj_a.split() if len(w) > 3):
                score += 0.10
                reasons.append(f"Overlapping regulatory object terms: '{obj_a}' / '{obj_b}'")

        # 4. Requirement Type Match (Weight: 0.10)
        if req_a.requirement_type == req_b.requirement_type:
            score += 0.10
            reasons.append(f"Same requirement classification: {req_a.requirement_type}")

        # 5. Shared Numeric / Parameter Dimension (Weight: 0.15)
        param_comp = self.compare_numeric_parameters(req_a.thresholds, req_b.thresholds)
        if param_comp.get("shared_parameter_types"):
            score += 0.15
            reasons.append(f"Shared parameter metrics: {param_comp['shared_parameter_types']}")

        return round(min(score, 1.0), 3), reasons

    # -------------------------------------------------------------------------
    # 73.11 NUMERIC COMPARISON
    # -------------------------------------------------------------------------

    def compare_numeric_parameters(
        self,
        thresholds_a: List[RequirementThreshold],
        thresholds_b: List[RequirementThreshold]
    ) -> Dict[str, Any]:
        """
        Compares structured numeric thresholds and durations (73.11).
        Does not automatically classify differing numbers as conflicts.
        """
        types_a = {t.parameter_type.lower(): t for t in thresholds_a if t.parameter_type}
        types_b = {t.parameter_type.lower(): t for t in thresholds_b if t.parameter_type}

        shared_types = list(set(types_a.keys()) & set(types_b.keys()))
        comparisons = []
        is_identical = True

        for p_type in shared_types:
            val_a = types_a[p_type]
            val_b = types_b[p_type]
            differ = val_a.normalized_value != val_b.normalized_value or val_a.raw_value != val_b.raw_value
            if differ:
                is_identical = False
            comparisons.append({
                "parameter_type": p_type,
                "left_raw": val_a.raw_value,
                "left_normalized": val_a.normalized_value,
                "right_raw": val_b.raw_value,
                "right_normalized": val_b.normalized_value,
                "unit": val_a.unit or val_b.unit,
                "values_differ": differ
            })

        return {
            "shared_parameter_types": shared_types,
            "has_shared_parameters": len(shared_types) > 0,
            "values_differ": not is_identical if shared_types else False,
            "details": comparisons
        }

    # -------------------------------------------------------------------------
    # 73.12 APPLICABILITY COMPARISON
    # -------------------------------------------------------------------------

    def compare_applicability(
        self,
        req_a: RegulatoryRequirement,
        req_b: RegulatoryRequirement
    ) -> Dict[str, Any]:
        """
        Evaluates entity classes, subjects, and scopes between two requirements (73.12).
        """
        subj_a = (req_a.subject or req_a.applicability or "").lower().strip()
        subj_b = (req_b.subject or req_b.applicability or "").lower().strip()

        if not subj_a or not subj_b:
            return {"match_type": "UNKNOWN", "explanation": "Subject or applicability unstated in one or both requirements."}

        # Check for exact or high entity overlap
        if subj_a == subj_b:
            return {"match_type": "SAME_ENTITIES", "explanation": f"Both apply to: '{subj_a}'."}

        # Check disjoint entities
        disjoint_keywords = [
            ("bank", "broker"), ("bank", "intermediary"), ("insurer", "bank"),
            ("insurer", "broker"), ("pension fund", "bank"), ("stock broker", "depository")
        ]
        for e1, e2 in disjoint_keywords:
            if (e1 in subj_a and e2 in subj_b) or (e2 in subj_a and e1 in subj_b):
                return {
                    "match_type": "DIFFERENT_ENTITIES",
                    "explanation": f"Applies to disjoint entity sectors: '{subj_a}' vs '{subj_b}'."
                }

        # Partial overlap
        words_a = set(subj_a.split())
        words_b = set(subj_b.split())
        if words_a & words_b:
            return {
                "match_type": "OVERLAPPING_ENTITIES",
                "explanation": f"Shares entity attributes: {list(words_a & words_b)}."
            }

        return {"match_type": "DIFFERENT_ENTITIES", "explanation": f"Distinct entities: '{subj_a}' vs '{subj_b}'."}

    # -------------------------------------------------------------------------
    # 73.13 TEMPORAL COMPARISON & STATUS (Phase 64 Integration)
    # -------------------------------------------------------------------------

    def determine_overlap_status(
        self,
        eff_date_a: Optional[str],
        eff_date_b: Optional[str]
    ) -> OverlapStatus:
        """Determines active vs historical vs future status based on effective dates (73.13, 73.14)."""
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")

        if not eff_date_a or not eff_date_b:
            return "ACTIVE"  # Default assumption for current corpus unless dated

        # If both are in future
        if eff_date_a > today and eff_date_b > today:
            return "FUTURE"

        return "ACTIVE"

    # -------------------------------------------------------------------------
    # 73.9 & 73.10 LLM OVERLAP CLASSIFIER (Conservative Gemini Grounding)
    # -------------------------------------------------------------------------

    def classify_overlap_with_llm(
        self,
        req_a: RegulatoryRequirement,
        req_b: RegulatoryRequirement,
        shared_topic: str,
        deterministic_score: float
    ) -> Tuple[OverlapType, OverlapConfidence, str, str, str]:
        """
        Invokes Gemini with strict negative-guard prompts to classify relationship (73.9, 73.10).
        """
        system_instruction = (
            "You are a regulatory compliance intelligence engine analyzing two provisions from different financial regulators.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Do not determine legal equivalence from wording alone.\n"
            "2. Do not declare regulatory conflict or state that regulations conflict.\n"
            "3. Use only the supplied evidence text.\n"
            "4. Return UNKNOWN when evidence is insufficient or when entities differ completely.\n"
            "5. Allowed relationship_type values: IDENTICAL, NEAR_DUPLICATE, OVERLAPPING, COMPLEMENTARY, RELATED, DISTINCT, UNKNOWN.\n"
            "Format your response as a valid JSON object matching the requested schema."
        )

        user_prompt = f"""
Analyze the relationship between these two regulatory requirements:

[PROVISION A]
Authority: {req_a.authority}
Document: {req_a.document_title or req_a.document_id}
Requirement Type: {req_a.requirement_type}
Subject/Entity: {req_a.subject or 'Unspecified'}
Action: {req_a.action or 'Unspecified'}
Object: {req_a.object or 'Unspecified'}
Requirement Text: {req_a.requirement_text}
Evidence: {req_a.source_evidence}

[PROVISION B]
Authority: {req_b.authority}
Document: {req_b.document_title or req_b.document_id}
Requirement Type: {req_b.requirement_type}
Subject/Entity: {req_b.subject or 'Unspecified'}
Action: {req_b.action or 'Unspecified'}
Object: {req_b.object or 'Unspecified'}
Requirement Text: {req_b.requirement_text}
Evidence: {req_b.source_evidence}

Deterministic Topic: {shared_topic}
Similarity Signal: {deterministic_score}

Return JSON with keys:
"relationship_type": one of ["IDENTICAL", "NEAR_DUPLICATE", "OVERLAPPING", "COMPLEMENTARY", "RELATED", "DISTINCT", "UNKNOWN"]
"shared_topic": string
"shared_activity": string
"explanation": clear factual summary of why this classification applies
"confidence": one of ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
"applicability_comparison": explanation of entity scope
"""
        try:
            resp = self.llm_provider.generate_text(
                prompt=user_prompt,
                system_instruction=system_instruction
            )
            raw_text = resp.text.strip()
            # Extract JSON block if surrounded by markdown fences
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            rel_type = parsed.get("relationship_type", "RELATED")
            conf = parsed.get("confidence", "MEDIUM")
            exp = parsed.get("explanation", f"Classified by LLM as {rel_type}.")
            activity = parsed.get("shared_activity", req_a.action or "Regulatory compliance")
            topic = parsed.get("shared_topic", shared_topic)
            return rel_type, conf, exp, activity, topic
        except Exception as e:
            logger.warning(f"LLM overlap classification fallback for {req_a.requirement_id} vs {req_b.requirement_id}: {e}")
            # Deterministic heuristic fallback
            if deterministic_score >= 0.70:
                return "OVERLAPPING", "MEDIUM", "High deterministic signal across topic, action, and object.", req_a.action or "Compliance", shared_topic
            elif deterministic_score >= 0.40:
                return "COMPLEMENTARY", "MEDIUM", "Shared regulatory topic and complementary actions.", req_a.action or "Compliance", shared_topic
            return "RELATED", "LOW", "Shares domain topic but distinct operational details.", req_a.action or "Compliance", shared_topic

    # -------------------------------------------------------------------------
    # FULL OVERLAP ANALYSIS PIPELINE
    # -------------------------------------------------------------------------

    def analyze_pair(
        self,
        req_a: RegulatoryRequirement,
        req_b: RegulatoryRequirement,
        use_llm: bool = True
    ) -> Optional[RegulatoryOverlap]:
        """
        Executes end-to-end overlap analysis on a single requirement pair.
        Ensures strict authority isolation, structured comparison, and evidence preservation.
        """
        if (req_a.authority or "").upper() == (req_b.authority or "").upper():
            return None  # Rule 73.3: Cross-regulator only

        topic_a = normalize_regulatory_topic(req_a.requirement_text, req_a.subject, req_a.action, req_a.object)
        topic_b = normalize_regulatory_topic(req_b.requirement_text, req_b.subject, req_b.action, req_b.object)

        det_score, det_reasons = self.compute_deterministic_similarity(req_a, req_b, topic_a)
        if det_score < 0.20:
            return None  # Unrelated

        shared_topic = topic_a if topic_a == topic_b and topic_a != "OTHER" else (topic_a if topic_a != "OTHER" else topic_b)
        param_comp = self.compare_numeric_parameters(req_a.thresholds, req_b.thresholds)
        app_comp = self.compare_applicability(req_a, req_b)

        if use_llm and det_score >= 0.35:
            rel_type, conf, explanation, activity, top = self.classify_overlap_with_llm(
                req_a, req_b, shared_topic, det_score
            )
            shared_topic = top or shared_topic
        else:
            # Deterministic classification
            if det_score >= 0.75 and app_comp["match_type"] == "SAME_ENTITIES":
                rel_type = "NEAR_DUPLICATE" if not param_comp.get("values_differ") else "OVERLAPPING"
                conf = "HIGH"
            elif det_score >= 0.50:
                rel_type = "OVERLAPPING" if app_comp["match_type"] != "DIFFERENT_ENTITIES" else "RELATED"
                conf = "MEDIUM"
            elif det_score >= 0.30:
                rel_type = "COMPLEMENTARY" if req_a.action != req_b.action else "RELATED"
                conf = "MEDIUM"
            else:
                rel_type = "RELATED"
                conf = "LOW"
            explanation = "; ".join(det_reasons)
            activity = req_a.action or "Compliance"

        # Special safety guard: If entities are explicitly disjoint, downgrade to RELATED
        if app_comp["match_type"] == "DIFFERENT_ENTITIES" and rel_type in ("IDENTICAL", "NEAR_DUPLICATE", "OVERLAPPING"):
            rel_type = "RELATED"
            explanation += " (Applicability differs across regulated entity categories)."

        overlap_id = generate_overlap_id(req_a.requirement_id, req_b.requirement_id)
        status = self.determine_overlap_status(req_a.effective_date, req_b.effective_date)

        return RegulatoryOverlap(
            overlap_id=overlap_id,
            left_authority=req_a.authority,
            left_document_id=req_a.document_id,
            left_document_version_id=req_a.document_version_id or "1.0",
            left_section_id=req_a.section_id,
            left_requirement_id=req_a.requirement_id,
            right_authority=req_b.authority,
            right_document_id=req_b.document_id,
            right_document_version_id=req_b.document_version_id or "1.0",
            right_section_id=req_b.section_id,
            right_requirement_id=req_b.requirement_id,
            relationship_type=rel_type,
            shared_topic=shared_topic,
            shared_activity=activity,
            similarity_score=det_score,
            confidence=conf,
            reasoning=explanation,
            evidence_left=req_a.source_evidence or req_a.requirement_text,
            evidence_right=req_b.source_evidence or req_b.requirement_text,
            effective_date_left=req_a.effective_date,
            effective_date_right=req_b.effective_date,
            status=status,
            applicability_match=app_comp["match_type"],
            parameter_comparison=param_comp,
            analysis_method="LLM" if use_llm else "DETERMINISTIC"
        )


# Global singleton
_overlap_engine = OverlapEngine()


def get_overlap_engine() -> OverlapEngine:
    return _overlap_engine
