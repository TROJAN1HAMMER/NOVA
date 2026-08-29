"""
NOVA — Automatic Symbolic Graph Entity Extractor
Extracts entities and relation triples from document chunks during document ingestion
so that newly uploaded documents automatically update the GraphRAG Entity Explorer.
"""

import re
import uuid
import structlog
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge import KnowledgeEntity, KnowledgeRelation

logger = structlog.get_logger(__name__)

# Known entity extraction patterns for security, compliance, standards, and architecture
ENTITY_PATTERNS = [
    (r"\b(PCI-DSS|ISO 27001|NIST SP 800-\d+|SOC 2|GDPR|HIPAA|OWASP FAPI)\b", "STANDARD"),
    (r"\b(Requirement \d+(\.\d+)*|Section \d+(\.\d+)*|Control \w+-\d+)\b", "RULE"),
    (r"\b(AES-\d+-\w+|RSA-\d+|SHA-\d+|HMAC-SHA256|ECDSA|TLS 1\.[23])\b", "ALGORITHM"),
    (r"\b(Multi-Factor Authentication|MFA|RBAC|Rate Limit|Input Validation|Schema Parameterization|Encryption at Rest|TLS Encryption)\b", "CONTROL"),
    (r"\b(SQL Injection|SQLi|XSS|Cross-Site Scripting|BOLA|Broken Object Level Authorization|CSRF|Command Injection|Buffer Overflow)\b", "VULNERABILITY"),
    (r"\b(API Gateway|PostgreSQL|pgvector|FastAPI|Redis|Uvicorn|Docker|Kubernetes|JWT|OAuth2)\b", "PRODUCT"),
]

async def extract_and_save_graph_entities(db: AsyncSession, document_id: uuid.UUID, chunks: List[Dict[str, Any]]) -> int:
    """
    Scans chunk text for symbolic entities and generates relation triples.
    Saves KnowledgeEntity and KnowledgeRelation records to DB.
    """
    text_corpus = " ".join([c.get("content", "") for c in chunks])
    if not text_corpus:
        return 0

    found_entities: Dict[str, Dict[str, Any]] = {}

    for pattern, entity_type in ENTITY_PATTERNS:
        matches = re.findall(pattern, text_corpus, flags=re.IGNORECASE)
        for m in matches:
            name = m[0] if isinstance(m, tuple) else m
            name_clean = name.strip()
            if len(name_clean) < 3:
                continue
            key = name_clean.lower()
            if key not in found_entities:
                found_entities[key] = {
                    "name": name_clean,
                    "type": entity_type,
                    "count": 1,
                }
            else:
                found_entities[key]["count"] += 1

    if not found_entities:
        # Fallback generic entity from filename or heading
        first_heading = chunks[0].get("heading") if chunks else None
        entity_name = first_heading or "Ingested Architecture Document"
        found_entities[entity_name.lower()] = {
            "name": entity_name[:64],
            "type": "DOCUMENT",
            "count": 1,
        }

    db_entities: List[KnowledgeEntity] = []
    entity_map: Dict[str, KnowledgeEntity] = {}

    for key, data in found_entities.items():
        entity = KnowledgeEntity(
            id=uuid.uuid4(),
            document_id=document_id,
            entity_name=data["name"],
            entity_type=data["type"],
            mention_count=data["count"],
        )
        db_entities.append(entity)
        entity_map[key] = entity

    db.add_all(db_entities)
    await db.flush()

    # Generate relation edges between extracted entities
    db_relations: List[KnowledgeRelation] = []
    entity_keys = list(entity_map.keys())

    for i in range(len(entity_keys) - 1):
        src_key = entity_keys[i]
        tgt_key = entity_keys[i + 1]
        src_ent = entity_map[src_key]
        tgt_ent = entity_map[tgt_key]

        rel_type = "RELATED_TO"
        if src_ent.entity_type == "STANDARD":
            rel_type = "ENFORCES"
        elif src_ent.entity_type == "RULE":
            rel_type = "REQUIRES"
        elif src_ent.entity_type == "VULNERABILITY":
            rel_type = "MITIGATED_BY"

        relation = KnowledgeRelation(
            id=uuid.uuid4(),
            source_entity_id=src_ent.id,
            target_entity_id=tgt_ent.id,
            relation_type=rel_type,
        )
        db_relations.append(relation)

    if db_relations:
        db.add_all(db_relations)
        await db.flush()

    logger.info(
        "graph_builder.entities_extracted",
        document_id=str(document_id),
        entities_count=len(db_entities),
        relations_count=len(db_relations),
    )
    return len(db_entities)
