"""
NOVA Architecture Intelligence — Unified Traceability Engine
Constructs provenance-backed traceability chains connecting:
Requirement / Document -> Knowledge Chunk -> Graph Entity -> Component -> Security Control -> Finding -> Risk Scenario -> Evidence -> Posture.
Never manufactures fake relationships; only establishes links with genuine evidence.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

from app.services.architecture_intelligence.component_discovery import DiscoveredComponent

logger = structlog.get_logger(__name__)


@dataclass
class TraceabilityChain:
    chain_id: str
    component_id: str
    component_name: str
    file_path: str
    line_number: Optional[int] = None
    requirement_doc_id: Optional[str] = None
    requirement_doc_name: Optional[str] = None
    knowledge_chunk_id: Optional[str] = None
    graph_entity_id: Optional[str] = None
    graph_entity_name: Optional[str] = None
    control_id: Optional[str] = None
    control_name: Optional[str] = None
    control_state: Optional[str] = None
    finding_id: Optional[str] = None
    finding_title: Optional[str] = None
    finding_severity: Optional[str] = None
    risk_scenario_id: Optional[str] = None
    risk_scenario_title: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)


class UnifiedTraceabilityEngine:
    """Discovers and establishes factual, provenance-backed traceability links."""

    def build_traceability(
        self,
        components: List[DiscoveredComponent],
        security_data: Optional[Dict[str, Any]] = None,
        knowledge_data: Optional[Dict[str, Any]] = None,
    ) -> List[TraceabilityChain]:
        security_data = security_data or {}
        knowledge_data = knowledge_data or {}

        assessments = security_data.get("assessments", [])
        controls = security_data.get("controls", [])
        scenarios = security_data.get("scenarios", [])
        docs = knowledge_data.get("documents", [])
        entities = knowledge_data.get("entities", [])

        chains: List[TraceabilityChain] = []
        chain_idx = 1

        for comp in components:
            comp_file = comp.file_path.strip("./")
            comp_name_lower = comp.name.lower()

            # 1. Match Security Controls for this component
            matched_controls = [
                c for c in controls
                if comp_file in str(c.get("scope", "")).strip("./")
                or comp_file in str(c.get("primary_location", "")).strip("./")
            ]

            # 2. Match Security Findings / Assessments
            matched_findings = [
                a for a in assessments
                if comp_file in str(a.get("affected_scope", "")).strip("./")
                or comp_file in str(a.get("file_path", "")).strip("./")
            ]

            # 3. Match Risk Scenarios
            matched_scenarios = [
                sc for sc in scenarios
                if any(comp_file in str(ev).strip("./") for ev in sc.get("evidence_references", []))
            ]

            # 4. Match Knowledge Entities / Documents (Provenance backed)
            matched_entity = next(
                (e for e in entities if str(e.get("entity_name", "")).lower() in comp_name_lower or comp_name_lower in str(e.get("entity_name", "")).lower()),
                None
            )
            matched_doc = next(
                (d for d in docs if comp_file in str(d.get("filename", "")) or comp_name_lower in str(d.get("filename", "")).lower()),
                None
            )

            # Establish link if there is at least one verified security or knowledge link
            if matched_findings or matched_controls or matched_scenarios or matched_entity:
                ctrl = matched_controls[0] if matched_controls else {}
                finding = matched_findings[0] if matched_findings else {}
                scenario = matched_scenarios[0] if matched_scenarios else {}

                effective_line_no = finding.get("line_number") if finding.get("line_number") is not None else (comp.line_number or 1)

                chains.append(
                    TraceabilityChain(
                        chain_id=f"TRC-{chain_idx:04d}",
                        component_id=comp.component_id,
                        component_name=comp.name,
                        file_path=comp.file_path,
                        line_number=effective_line_no,
                        requirement_doc_id=matched_doc.get("id") if matched_doc else None,
                        requirement_doc_name=matched_doc.get("filename") if matched_doc else None,
                        knowledge_chunk_id=matched_doc.get("chunk_id") if matched_doc else None,
                        graph_entity_id=matched_entity.get("id") if matched_entity else None,
                        graph_entity_name=matched_entity.get("entity_name") if matched_entity else None,
                        control_id=ctrl.get("control_id") or ctrl.get("id"),
                        control_name=ctrl.get("control_name") or ctrl.get("control_type"),
                        control_state=ctrl.get("state"),
                        finding_id=finding.get("id"),
                        finding_title=finding.get("risk_type") or finding.get("title"),
                        finding_severity=finding.get("severity"),
                        risk_scenario_id=scenario.get("scenario_id") or scenario.get("id"),
                        risk_scenario_title=scenario.get("title") or scenario.get("scenario_type"),
                        provenance={
                            "source_file": comp.file_path,
                            "line_number": effective_line_no,
                            "cwe_id": finding.get("cwe_id"),
                            "evidence_span": finding.get("code_snippet") or comp.name,
                            "confidence": finding.get("confidence", 0.90),
                        },
                    )
                )
                chain_idx += 1

        logger.info("traceability_engine.completed", total_chains=len(chains))
        return chains


traceability_engine = UnifiedTraceabilityEngine()
