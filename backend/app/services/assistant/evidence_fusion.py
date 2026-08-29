"""
NOVA — Unified Evidence Fusion Engine
Unifies heterogeneous evidence sources (Vector Knowledge Chunks, Security Findings,
FAQ Axioms, Web Fallbacks) into a structured provenance-tracked representation
with cross-source agreement calculation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import math
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class UnifiedEvidenceItem:
    """Unified representation of a single evidence item across all sources."""
    source_type: str  # "knowledge_doc" | "security_finding" | "faq_axiom" | "web_search"
    source_id: str
    title: str
    content: str
    similarity_score: float
    rerank_score: float
    reliability_weight: float
    timestamp: Optional[datetime] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    cwe_id: Optional[str] = None
    cve: Optional[str] = None
    severity: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_citation_dict(self) -> Dict[str, Any]:
        """Converts item to a citation format suitable for LLM prompt context."""
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity,
            "cwe_id": self.cwe_id,
            "cve": self.cve,
            "excerpt": self.content,
            "similarity_score": self.similarity_score,
            "rerank_score": self.rerank_score,
            "provenance": self.provenance,
        }


class EvidenceFusionEngine:
    """
    Deduplicates, scores, and fuses knowledge evidence and security finding evidence.
    """

    def calculate_cross_scanner_confidence(self, sources: List[str], base_confidence: float = 0.85) -> float:
        """
        Calculates evidence confidence boost for independent multi-scanner detections:
        C_finding = 1.0 - PROD(1.0 - c_i)
        """
        if not sources:
            return base_confidence
        unique_scanners = list(set(sources))
        unconfidence_product = 1.0
        for _ in unique_scanners:
            unconfidence_product *= (1.0 - base_confidence)
        boosted_confidence = round(1.0 - unconfidence_product, 4)
        logger.debug("fusion.cross_scanner_boost", sources=unique_scanners, boosted_confidence=boosted_confidence)
        return boosted_confidence

    def format_finding_as_evidence(self, finding: Any) -> UnifiedEvidenceItem:
        """Converts a database Finding model or dict into a UnifiedEvidenceItem."""
        finding_id = str(getattr(finding, "id", None) or finding.get("id", "finding-uuid"))
        title = getattr(finding, "title", None) or finding.get("title", "Security Finding")
        file_path = getattr(finding, "file_path", None) or finding.get("file_path", "")
        line_no = getattr(finding, "line_number", None) or finding.get("line_number")
        severity = str(getattr(finding, "severity", None) or finding.get("severity", "MEDIUM")).upper()
        cwe_id = getattr(finding, "cwe_id", None) or finding.get("cwe_id")
        cve = getattr(finding, "cve", None) or finding.get("cve")
        desc = getattr(finding, "description", None) or finding.get("description", "")
        remediation = getattr(finding, "ai_remediation", None) or finding.get("ai_remediation", "")
        sources = getattr(finding, "sources", None) or finding.get("sources", [getattr(finding, "source", "scanner")])

        boosted_conf = self.calculate_cross_scanner_confidence(sources)

        content = f"Security Vulnerability [{severity}]: {title}\nLocation: {file_path}:{line_no or 'N/A'}\n"
        if cwe_id:
            content += f"CWE ID: {cwe_id}\n"
        if cve:
            content += f"CVE: {cve}\n"
        content += f"Description: {desc}\n"
        if remediation:
            content += f"Remediation: {remediation}\n"

        provenance = {
            "scan_job_id": str(getattr(finding, "scan_job_id", None) or finding.get("scan_job_id", "")),
            "sources": sources,
            "scanner_confidence": boosted_conf,
            "cvss": getattr(finding, "cvss", 0.0) or finding.get("cvss", 0.0),
            "brs": getattr(finding, "brs", 0.0) or finding.get("brs", 0.0),
        }

        return UnifiedEvidenceItem(
            source_type="security_finding",
            source_id=finding_id,
            title=title,
            content=content,
            similarity_score=boosted_conf,
            rerank_score=boosted_conf,
            reliability_weight=0.95,
            timestamp=getattr(finding, "created_at", None),
            file_path=file_path,
            line_number=line_no,
            cwe_id=cwe_id,
            cve=cve,
            severity=severity,
            provenance=provenance,
        )

    def format_knowledge_chunk_as_evidence(
        self, chunk: Any, similarity_score: float, rerank_score: float = 0.0
    ) -> UnifiedEvidenceItem:
        """Converts a KnowledgeChunk model or candidate into a UnifiedEvidenceItem."""
        doc = getattr(chunk, "document", None)
        filename = getattr(doc, "filename", "document.txt") if doc else "document.txt"
        doc_id = str(getattr(chunk, "document_id", "doc-uuid"))
        heading = getattr(chunk, "heading", None)
        section_path = getattr(chunk, "section_path", None)
        page_no = getattr(chunk, "page_number", None)
        created_at = getattr(doc, "created_at", None) if doc else None

        provenance = {
            "document_id": doc_id,
            "filename": filename,
            "heading": heading,
            "section_path": section_path,
            "page_number": page_no,
        }

        return UnifiedEvidenceItem(
            source_type="knowledge_doc",
            source_id=doc_id,
            title=filename,
            content=getattr(chunk, "content", ""),
            similarity_score=round(similarity_score, 4),
            rerank_score=round(rerank_score, 4),
            reliability_weight=0.85,
            timestamp=created_at,
            file_path=filename,
            provenance=provenance,
        )

    def fuse_evidence(
        self,
        knowledge_items: List[UnifiedEvidenceItem],
        security_items: List[UnifiedEvidenceItem],
        top_k: int = 5,
    ) -> List[UnifiedEvidenceItem]:
        """
        Fuses, deduplicates, and ranks combined knowledge and security evidence items.
        """
        combined = knowledge_items + security_items
        if not combined:
            return []

        # Sort by weighted score: (rerank_score * reliability_weight)
        sorted_items = sorted(
            combined,
            key=lambda item: (item.rerank_score * item.reliability_weight),
            reverse=True,
        )

        # Deduplicate by (source_type, source_id, file_path)
        seen_keys = set()
        fused: List[UnifiedEvidenceItem] = []
        for item in sorted_items:
            key = f"{item.source_type}:{item.source_id}:{item.file_path}"
            if key not in seen_keys:
                seen_keys.add(key)
                fused.append(item)

        return fused[:top_k]


evidence_fusion_engine = EvidenceFusionEngine()
