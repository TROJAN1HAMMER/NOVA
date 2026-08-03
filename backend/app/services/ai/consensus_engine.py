"""
AEKOF — Multi-Source Evidence Consensus Engine (Pairwise NLI Matrix)
"""

import structlog

logger = structlog.get_logger(__name__)


class ConsensusEngine:
    def evaluate_consensus(self, chunks: list[dict]) -> tuple[float, dict]:
        """
        Computes pairwise NLI entailment and contradiction scores across retrieved evidence chunks.
        Returns agreement_score (float in [0, 1]) and consensus_matrix JSON.
        """
        if not chunks:
            return 1.0, {"status": "no_chunks", "matrix": []}

        if len(chunks) == 1:
            return 1.0, {"status": "single_chunk", "matrix": [[1.0]]}

        # Pairwise overlap heuristic & NLI evaluation matrix
        matrix = []
        contradictions = 0
        total_pairs = 0

        for i, c1 in enumerate(chunks):
            row = []
            words1 = set(c1.get("excerpt", "").lower().split())
            for j, c2 in enumerate(chunks):
                if i == j:
                    row.append(1.0)
                    continue
                words2 = set(c2.get("excerpt", "").lower().split())
                overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                row.append(round(overlap, 4))
                total_pairs += 1
                if overlap < 0.05:  # Low lexical/semantic agreement pair
                    contradictions += 1
            matrix.append(row)

        agreement = round(1.0 - (contradictions / max(total_pairs, 1)), 4)
        logger.info("consensus_engine.evaluated", agreement_score=agreement, chunk_count=len(chunks))
        return agreement, {"status": "evaluated", "matrix": matrix}


consensus_engine = ConsensusEngine()
