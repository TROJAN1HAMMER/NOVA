"""
NOVA — Finding Intelligence Schemas
"""

from typing import Optional

from pydantic import BaseModel, Field


class FindingIntelligenceCitation(BaseModel):
    document_id: str
    filename: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    heading: Optional[str] = None
    similarity_score: float
    rerank_score: float
    excerpt: str


class FindingIntelligenceResponse(BaseModel):
    finding_id: str

    # Deterministic — never LLM-generated (see intelligence_service.py).
    cwe_id: Optional[str] = None
    cwe_name: Optional[str] = None
    owasp_category: Optional[str] = None
    owasp_name: Optional[str] = None
    mitre_technique_ids: list[str] = Field(default_factory=list)
    pci_clause: Optional[str] = None
    rbi_clause: Optional[str] = None
    swift_clause: Optional[str] = None
    why_detected: str

    # RAG-grounded, LLM-generated — null unless `grounded` is true.
    plain_english_explanation: Optional[str] = None
    business_impact: Optional[str] = None
    technical_impact: Optional[str] = None
    recommended_remediation: Optional[str] = None
    verification_steps: list[str] = Field(default_factory=list)
    code_example: Optional[str] = None

    citations: list[FindingIntelligenceCitation] = Field(default_factory=list)
    confidence: float
    retrieved_count: int
    grounded: bool
    note: Optional[str] = None
    latency_ms: float
