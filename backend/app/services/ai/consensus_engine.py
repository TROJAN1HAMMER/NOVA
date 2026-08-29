"""
AEKOF — Multi-Source Evidence Consensus Engine (Pairwise NLI Matrix & Entailment Analysis)
"""

from typing import Any, Dict, List, Tuple
import structlog

from app.services.ai.nli_engine import nli_engine, EvidenceRelationship

logger = structlog.get_logger(__name__)


class ConsensusEngine:
    """Evaluates pairwise evidence agreement, support, and contradiction using NLI & metadata."""

    def evaluate_consensus(self, chunks: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        """
        Computes pairwise NLI entailment and contradiction scores across retrieved evidence chunks.
        Returns agreement_score (float in [0, 1]) and consensus_matrix JSON.
        """
        if not chunks:
            return 1.0, {"status": "no_chunks", "matrix": [], "relationships": []}

        if len(chunks) == 1:
            return 1.0, {"status": "single_chunk", "matrix": [[1.0]], "relationships": []}

        try:
            # 1. NLI Pairwise Structural Analysis
            relationships: List[EvidenceRelationship] = nli_engine.analyze_evidence_set(chunks)

            n_supports = sum(1 for r in relationships if r.relationship == "SUPPORTS")
            n_contradicts = sum(1 for r in relationships if r.relationship == "CONTRADICTS")
            n_related = sum(1 for r in relationships if r.relationship == "RELATED")
            n_unrelated = sum(1 for r in relationships if r.relationship == "UNRELATED")

            # 2. Compute Lexical/Overlap Matrix for Backward Compatibility
            matrix = []
            for i, c1 in enumerate(chunks):
                row = []
                excerpt1 = str(c1.get("excerpt") or c1.get("content") or "")
                words1 = set(excerpt1.lower().split())
                for j, c2 in enumerate(chunks):
                    if i == j:
                        row.append(1.0)
                        continue
                    excerpt2 = str(c2.get("excerpt") or c2.get("content") or "")
                    words2 = set(excerpt2.lower().split())
                    overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                    row.append(round(overlap, 4))
                matrix.append(row)

            # 3. Calculate Dynamic Agreement Score (C_agreement)
            if n_contradicts > 0:
                # Contradiction drops agreement severely below decision thresholds
                agreement = max(0.0, round(0.50 - (0.40 * n_contradicts), 4))
            else:
                base_agreement = 0.85
                support_boost = min(0.15, 0.05 * n_supports)
                agreement = min(1.0, round(base_agreement + support_boost, 4))

            consensus_mat = {
                "status": "evaluated",
                "agreement_score": agreement,
                "support_count": n_supports,
                "contradiction_count": n_contradicts,
                "related_count": n_related,
                "unrelated_count": n_unrelated,
                "relationships": [r.to_dict() for r in relationships],
                "matrix": matrix,
            }

            logger.info(
                "consensus_engine.evaluated",
                agreement_score=agreement,
                chunk_count=len(chunks),
                supports=n_supports,
                contradictions=n_contradicts,
            )
            return agreement, consensus_mat

        except Exception as exc:
            logger.warning("consensus_engine.nli_fallback_triggered", error=str(exc))
            # Fallback to lexical consensus without breaking assistant path
            return self._fallback_lexical_consensus(chunks)

    def _fallback_lexical_consensus(self, chunks: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
        """Fallback lexical consensus calculation if NLI inference fails."""
        matrix = []
        contradictions = 0
        total_pairs = 0

        for i, c1 in enumerate(chunks):
            row = []
            words1 = set(str(c1.get("excerpt") or "").lower().split())
            for j, c2 in enumerate(chunks):
                if i == j:
                    row.append(1.0)
                    continue
                words2 = set(str(c2.get("excerpt") or "").lower().split())
                overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                row.append(round(overlap, 4))
                total_pairs += 1
                if overlap < 0.05:
                    contradictions += 1
            matrix.append(row)

        agreement = round(1.0 - (contradictions / max(total_pairs, 1)), 4)
        return agreement, {"status": "evaluated_fallback", "matrix": matrix, "relationships": []}


consensus_engine = ConsensusEngine()
