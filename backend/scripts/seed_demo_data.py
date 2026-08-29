"""
NOVA — Comprehensive Demo Data Seeder

Seeds rich demonstration data across:
1. User Accounts & Enterprise Roles
2. Knowledge Base Security Policy Documents
3. Security Intelligence Asset Graph & Observations
4. Temporal Security Posture Snapshots & History Trajectory
"""

import asyncio
import datetime
import uuid
import structlog

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.models.security_intelligence import SecurityIntelPostureSnapshot
from app.auth.security import hash_password
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator

logger = structlog.get_logger(__name__)

async def seed_users(session):
    users_data = [
        {"email": "admin@nova.ai", "full_name": "Nova Enterprise Admin", "role": UserRole.ADMIN, "password": "AdminPassword123!"},
        {"email": "security@nova.ai", "full_name": "Sarah Chen (Lead Security Architect)", "role": UserRole.SECURITY_ENGINEER, "password": "SecurityPass123!"},
        {"email": "dev@nova.ai", "full_name": "Alex Rivera (Senior Backend Engineer)", "role": UserRole.DEVELOPER, "password": "DevPassword123!"},
        {"email": "harshith@nova.ai", "full_name": "Harshith (Platform Lead)", "role": UserRole.ADMIN, "password": "Password123!"},
    ]

    for u in users_data:
        res = await session.execute(select(User).where(User.email == u["email"]))
        existing = res.scalar_one_or_none()
        if not existing:
            user = User(
                email=u["email"],
                full_name=u["full_name"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                is_active=True,
            )
            session.add(user)
            print(f"Seeded user: {u['email']} ({u['role'].value})")
        else:
            print(f"User already exists: {u['email']}")

    await session.commit()

async def seed_knowledge_base(session):
    documents = [
        {
            "filename": "PCI_DSS_v4.0_Banking_Security_Standard.pdf",
            "document_type": "pdf",
            "status": "ready",
            "chunks": [
                "PCI-DSS Requirement 3.4: Protect sensitive cardholder data with strong cryptographic algorithms (AES-256-GCM or RSA-4096). Unencrypted PAN or credentials stored in plain text constitute a critical vulnerability.",
                "PCI-DSS Requirement 6.4.1: Protect public-facing web applications against automated attacks and injection flaws (SQLi, XSS, Command Injection). All input parameters must undergo strict schema validation and parameterization.",
                "PCI-DSS Requirement 7.1: Enforce Role-Based Access Control (RBAC) across all administrative APIs. Administrative functions must mandate multi-factor authentication and explicitly evaluate role privileges before execution.",
            ]
        },
        {
            "filename": "OWASP_Financial_API_Security_Guide.md",
            "document_type": "md",
            "status": "ready",
            "chunks": [
                "FAPI-01 Broken Object Level Authorization (BOLA): Ensure API endpoints verify that the requesting user owns or is authorized to access the specific resource identifier provided in request parameters.",
                "FAPI-02 Unprotected Financial Transactions: High-value payment transfers and fund movements must be protected by explicit permission checks and transaction limits to prevent unauthorized administrative escalation.",
                "FAPI-03 Exposure of Sensitive API Tokens: Hardcoded credentials, database connection strings, or JWT signing secrets in source code repositories expose financial systems to immediate compromise.",
            ]
        }
    ]

    for doc_info in documents:
        res = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == doc_info["filename"]))
        existing = res.scalar_one_or_none()
        if not existing:
            doc = KnowledgeDocument(
                filename=doc_info["filename"],
                document_type=doc_info["document_type"],
                file_path=f"data/knowledge_base/{doc_info['filename']}",
                version="1",
                document_group_id=uuid.uuid4(),
                is_latest=True,
                content_hash=str(uuid.uuid4()).replace("-", "")[:32],
                status="indexed",
                file_size_bytes=len("".join(doc_info["chunks"])),
                chunk_count=len(doc_info["chunks"]),
            )
            session.add(doc)
            await session.flush()

            dummy_embedding = [0.01 * (i % 10) for i in range(384)]
            for i, text in enumerate(doc_info["chunks"]):
                chunk = KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=text,
                    token_count=len(text.split()),
                    embedding=dummy_embedding,
                )
                session.add(chunk)

            print(f"Seeded Knowledge Base Document: {doc_info['filename']}")
        else:
            print(f"Document already exists: {doc_info['filename']}")

    await session.commit()

async def seed_knowledge_graph(session):
    from app.models.knowledge import KnowledgeEntity, KnowledgeRelation
    res = await session.execute(select(KnowledgeEntity))
    existing = res.scalars().all()
    if existing:
        print("Knowledge Graph entities already exist.")
        return

    doc_res = await session.execute(select(KnowledgeDocument))
    docs = {d.filename: d for d in doc_res.scalars().all()}

    pci_doc = docs.get("PCI_DSS_v4.0_Banking_Security_Standard.pdf")
    owasp_doc = docs.get("OWASP_Financial_API_Security_Guide.md")

    if not pci_doc or not owasp_doc:
        return

    # Seed PCI-DSS Entities & Relations
    e_pci_std = KnowledgeEntity(document_id=pci_doc.id, entity_name="PCI-DSS v4.0 Standard", entity_type="STANDARD", mention_count=5)
    e_pci_34 = KnowledgeEntity(document_id=pci_doc.id, entity_name="Requirement 3.4 (Cardholder Cryptography)", entity_type="RULE", mention_count=4)
    e_pci_64 = KnowledgeEntity(document_id=pci_doc.id, entity_name="Requirement 6.4.1 (AST Injection Prevention)", entity_type="RULE", mention_count=4)
    e_pci_71 = KnowledgeEntity(document_id=pci_doc.id, entity_name="Requirement 7.1 (RBAC & MFA)", entity_type="RULE", mention_count=4)
    e_aes = KnowledgeEntity(document_id=pci_doc.id, entity_name="AES-256-GCM / RSA-4096", entity_type="ALGORITHM", mention_count=3)
    e_mfa = KnowledgeEntity(document_id=pci_doc.id, entity_name="Multi-Factor Authentication (MFA)", entity_type="CONTROL", mention_count=3)

    session.add_all([e_pci_std, e_pci_34, e_pci_64, e_pci_71, e_aes, e_mfa])
    await session.flush()

    r1 = KnowledgeRelation(source_entity_id=e_pci_std.id, target_entity_id=e_pci_34.id, relation_type="ENFORCES")
    r2 = KnowledgeRelation(source_entity_id=e_pci_34.id, target_entity_id=e_aes.id, relation_type="REQUIRES")
    r3 = KnowledgeRelation(source_entity_id=e_pci_std.id, target_entity_id=e_pci_64.id, relation_type="ENFORCES")
    r4 = KnowledgeRelation(source_entity_id=e_pci_std.id, target_entity_id=e_pci_71.id, relation_type="ENFORCES")
    r5 = KnowledgeRelation(source_entity_id=e_pci_71.id, target_entity_id=e_mfa.id, relation_type="REQUIRES")

    session.add_all([r1, r2, r3, r4, r5])

    # Seed OWASP FAPI Entities & Relations
    e_fapi_std = KnowledgeEntity(document_id=owasp_doc.id, entity_name="OWASP FAPI Framework", entity_type="FRAMEWORK", mention_count=6)
    e_fapi_01 = KnowledgeEntity(document_id=owasp_doc.id, entity_name="FAPI-01 (BOLA)", entity_type="VULNERABILITY", mention_count=4)
    e_fapi_02 = KnowledgeEntity(document_id=owasp_doc.id, entity_name="FAPI-02 (Unprotected Transactions)", entity_type="VULNERABILITY", mention_count=4)
    e_fapi_03 = KnowledgeEntity(document_id=owasp_doc.id, entity_name="FAPI-03 (Token Exposure)", entity_type="VULNERABILITY", mention_count=5)
    e_rbac_chk = KnowledgeEntity(document_id=owasp_doc.id, entity_name="Resource Ownership Check", entity_type="CONTROL", mention_count=3)
    e_token_sec = KnowledgeEntity(document_id=owasp_doc.id, entity_name="JWT Signing & Connection Secret", entity_type="CONTROL", mention_count=3)

    session.add_all([e_fapi_std, e_fapi_01, e_fapi_02, e_fapi_03, e_rbac_chk, e_token_sec])
    await session.flush()

    r6 = KnowledgeRelation(source_entity_id=e_fapi_std.id, target_entity_id=e_fapi_01.id, relation_type="DEFINES")
    r7 = KnowledgeRelation(source_entity_id=e_fapi_01.id, target_entity_id=e_rbac_chk.id, relation_type="MITIGATED_BY")
    r8 = KnowledgeRelation(source_entity_id=e_fapi_std.id, target_entity_id=e_fapi_02.id, relation_type="DEFINES")
    r9 = KnowledgeRelation(source_entity_id=e_fapi_std.id, target_entity_id=e_fapi_03.id, relation_type="DEFINES")
    r10 = KnowledgeRelation(source_entity_id=e_fapi_03.id, target_entity_id=e_token_sec.id, relation_type="MITIGATED_BY")

    session.add_all([r6, r7, r8, r9, r10])
    await session.commit()
    print("Seeded Knowledge Graph: 12 Entities, 10 Relation Edges")

async def seed_posture_history(session):
    res = await session.execute(select(SecurityIntelPostureSnapshot))
    existing_snapshots = res.scalars().all()
    if not existing_snapshots:
        now = datetime.datetime.now(datetime.timezone.utc)
        snapshots = [
            {
                "created_at": now - datetime.timedelta(days=7),
                "analysis_run_id": str(uuid.uuid4()),
                "target_scope": "data/demo_repo",
                "posture_score": 62.5,
                "posture_rating": "NEEDS_ATTENTION",
                "control_coverage_pct": 50.0,
                "total_assets_count": 5,
                "unresolved_risks_count": 3,
                "critical_risks_count": 1,
                "high_risks_count": 2,
                "delta_score": None,
                "trend_direction": "FIRST_RUN",
                "risk_evolution_summary": {"new_risks_count": 3, "resolved_risks_count": 0, "persistent_risks_count": 0}
            },
            {
                "created_at": now - datetime.timedelta(days=3),
                "analysis_run_id": str(uuid.uuid4()),
                "target_scope": "data/demo_repo",
                "posture_score": 75.0,
                "posture_rating": "MODERATE",
                "control_coverage_pct": 75.0,
                "total_assets_count": 5,
                "unresolved_risks_count": 2,
                "critical_risks_count": 0,
                "high_risks_count": 2,
                "delta_score": 12.5,
                "trend_direction": "IMPROVED",
                "risk_evolution_summary": {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 2}
            },
            {
                "created_at": now,
                "analysis_run_id": str(uuid.uuid4()),
                "target_scope": "data/demo_repo",
                "posture_score": 95.0,
                "posture_rating": "STRONG",
                "control_coverage_pct": 100.0,
                "total_assets_count": 5,
                "unresolved_risks_count": 0,
                "critical_risks_count": 0,
                "high_risks_count": 0,
                "delta_score": 20.0,
                "trend_direction": "IMPROVED",
                "risk_evolution_summary": {"new_risks_count": 0, "resolved_risks_count": 2, "persistent_risks_count": 0}
            }
        ]

        for s in snapshots:
            snap = SecurityIntelPostureSnapshot(
                created_at=s["created_at"],
                analysis_run_id=s["analysis_run_id"],
                target_scope=s["target_scope"],
                posture_score=s["posture_score"],
                posture_rating=s["posture_rating"],
                control_coverage_pct=s["control_coverage_pct"],
                total_assets_count=s["total_assets_count"],
                unresolved_risks_count=s["unresolved_risks_count"],
                critical_risks_count=s["critical_risks_count"],
                high_risks_count=s["high_risks_count"],
                medium_risks_count=0,
                low_risks_count=0,
                verified_fixed_count=s["risk_evolution_summary"]["resolved_risks_count"],
                delta_score=s["delta_score"],
                trend_direction=s["trend_direction"],
                risk_evolution_summary=s["risk_evolution_summary"]
            )
            session.add(snap)
            print(f"Seeded Temporal Posture Snapshot: Score {s['posture_score']}/100 ({s['trend_direction']})")

        await session.commit()
    else:
        print("Posture snapshots already exist.")

async def run_security_intelligence_pipeline():
    print("Running Security Intelligence Analysis Pipeline...")

async def main():
    print("=================================================================")
    print("NOVA — SEEDING ENTERPRISE DEMONSTRATION DATA")
    print("=================================================================")
    async with AsyncSessionLocal() as session:
        await seed_users(session)
        await seed_knowledge_base(session)
        await seed_knowledge_graph(session)
        await seed_posture_history(session)
        await run_security_intelligence_pipeline()

    res = security_intelligence_orchestrator.run_full_analysis("data/demo_repo")
    print(f"Security Intelligence Analysis Completed: {res['posture']['posture_score']}/100 ({res['posture']['posture_rating']})")

    print("=================================================================")
    print("DATA SEEDING COMPLETED SUCCESSFULLY!")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(main())
