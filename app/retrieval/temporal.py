"""
Temporal Reasoning and Latest-Regulation Retrieval Module.

Calculates controlled recency adjustments, handles time intents (latest, current, date-specific, historical),
and identifies predecessor document relationships for regulatory change analysis.
"""

import re
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

from app.config import settings
from app.retrieval.mongodb_vector import RetrievedChunk
from app.retrieval.query_analyzer import QueryIntent

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def parse_date_safe(date_str: Optional[str]) -> Optional[date]:
    """Parses ISO date YYYY-MM-DD or returns None without guessing."""
    if not date_str or not isinstance(date_str, str):
        return None
    clean = date_str.strip()
    # YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", clean)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    # YYYY-MM
    match_ym = re.match(r"^(\d{4})-(\d{2})$", clean)
    if match_ym:
        try:
            return date(int(match_ym.group(1)), int(match_ym.group(2)), 1)
        except ValueError:
            return None
    return None


class TemporalRanker:
    """
    Applies bounded temporal adjustments to candidate relevance scores based on QueryIntent.
    """

    def __init__(self, boost_weight: Optional[float] = None):
        self.boost_weight = boost_weight if boost_weight is not None else settings.temporal_boost_weight

    def apply_temporal_ranking(
        self,
        intent: QueryIntent,
        candidates: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Adjusts chunk scores with controlled temporal weighting.
        Relevance remains dominant; temporal boost provides up to ±self.boost_weight adjustment.
        """
        if not candidates or intent.time_intent == "none":
            return candidates

        today = date.today()
        scored_candidates: List[RetrievedChunk] = []

        # Find newest publication date in candidate set as anchor
        dates_present = [parse_date_safe(c.published_date) for c in candidates if c.published_date]
        dates_present = [d for d in dates_present if d is not None]
        anchor_date = max(dates_present) if dates_present else today

        for chunk in candidates:
            c_date = parse_date_safe(chunk.published_date) or parse_date_safe(chunk.effective_date)
            base_score = chunk.score
            temporal_boost = 0.0

            if intent.time_intent in {"latest", "current", "recent"}:
                if c_date:
                    # Exponential or linear decay based on difference from anchor date
                    days_diff = (anchor_date - c_date).days
                    if days_diff <= 0:
                        # Newest candidate
                        temporal_boost = self.boost_weight
                    elif days_diff < 180:
                        temporal_boost = self.boost_weight * 0.8
                    elif days_diff < 365:
                        temporal_boost = self.boost_weight * 0.5
                    elif days_diff < 730:
                        temporal_boost = self.boost_weight * 0.2
                    else:
                        temporal_boost = 0.0
                else:
                    temporal_boost = 0.0

            elif intent.time_intent == "date_specific" and intent.target_date:
                t_date_str = intent.target_date
                if chunk.published_date and chunk.published_date.startswith(t_date_str):
                    temporal_boost = self.boost_weight
                elif chunk.effective_date and chunk.effective_date.startswith(t_date_str):
                    temporal_boost = self.boost_weight
                else:
                    temporal_boost = 0.0

            elif intent.time_intent == "historical":
                if c_date and (anchor_date - c_date).days > 365:
                    temporal_boost = self.boost_weight
                else:
                    temporal_boost = -self.boost_weight * 0.5

            adjusted_score = round(base_score + temporal_boost, 4)
            updated_chunk = chunk.model_copy(update={"score": adjusted_score})
            scored_candidates.append(updated_chunk)

        # Sort descending by temporally adjusted score
        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates

    def explain_temporal_ranking(
        self,
        intent: QueryIntent,
        candidates: List[RetrievedChunk]
    ) -> List[Dict[str, Any]]:
        """
        Diagnostics utility explaining temporal score adjustments.
        """
        ranked = self.apply_temporal_ranking(intent, candidates)
        explanations = []

        for orig, adj in zip(candidates, ranked):
            boost = round(adj.score - orig.score, 4)
            explanations.append({
                "chunk_id": adj.chunk_id,
                "title": adj.title,
                "published_date": adj.published_date or "N/A",
                "effective_date": adj.effective_date or "N/A",
                "base_relevance": orig.score,
                "temporal_boost": boost,
                "final_score": adj.score,
                "time_intent": intent.time_intent
            })

        return explanations


# Default singleton instance
_default_temporal_ranker = TemporalRanker()


def apply_temporal_ranking(intent: QueryIntent, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
    return _default_temporal_ranker.apply_temporal_ranking(intent, candidates)


def explain_temporal_ranking(intent: QueryIntent, candidates: List[RetrievedChunk]) -> List[Dict[str, Any]]:
    return _default_temporal_ranker.explain_temporal_ranking(intent, candidates)
