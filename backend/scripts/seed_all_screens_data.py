"""
NOVA — Comprehensive Master Data Seeder
Populates rich, high-fidelity production-grade demonstration data across:
1. Users & RBAC Permissions
2. Knowledge Base Documents (Multi-version, Tags, Chunks with pgvector embeddings)
3. Knowledge Graph (16+ Entities & 20+ Cross-domain Relations)
4. Knowledge Evolution & Gap Candidates (HDBSCAN clusters for Self-Healing Inbox)
5. Stage 0 FAQ Axiom Rules (Active & Draft)
6. Assistant Chat Sessions & Detailed Messages (Reasoning traces, NLI matrices, Citations, Trust Scores)
7. Audit Logs (Rich multi-user activity trail)
8. Search Analytics Telemetry Logs & User Feedback Entries
9. Repositories (Enterprise source targets)
10. Security Intelligence Full Pipeline:
    - Assets (Criticality, Types, Framework bindings)
    - AST Observations (Facts, Spans, Locations)
    - Control Evaluations (States, Types, Scopes)
    - Risk Scenarios (Attack paths, Trust boundary crossings)
    - Verified Assessments (Evidence chains, Remediations, Severity)
    - Temporal Posture Snapshots (Time-series history, Trajectory deltas, Risk evolution)
11. Reports & System Settings
"""

import asyncio
import datetime
import uuid
import json
import structlog
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.auth.security import hash_password
from app.models.enums import UserRole, AuthProvider, RepoProviderType
from app.models.user import User
from app.models.knowledge import (
    KnowledgeDocument, KnowledgeChunk, KnowledgeEntity, KnowledgeRelation,
    SearchAnalyticsLog, Feedback
)
from app.models.faq_rule import FAQRule
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.audit_log import AuditLog
from app.models.repository import Repository
from app.models.report import Report
from app.models.system_setting import SystemSetting
from app.models.security_intelligence import (
    SecurityIntelAsset, SecurityIntelObservation, SecurityIntelControl,
    SecurityIntelRiskScenario, SecurityIntelAssessment, SecurityIntelPostureSnapshot,
    SecurityIntelScan
)

logger = structlog.get_logger(__name__)

async def seed_all(init_only: bool = False, force: bool = False):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        if init_only and not force:
            res_user_cnt = await session.execute(select(func.count(User.id)))
            user_cnt = res_user_cnt.scalar_one()
            if user_cnt > 0:
                print("[NOVA] Database already contains persistent application records. Initial seed skipped.")
                return
        print("=================================================================")
        print("🚀 NOVA — POPULATING FULL PLATFORM DATA FOR ALL SCREENS")
        print("=================================================================")

        # -------------------------------------------------------------
        # 1. Users
        # -------------------------------------------------------------
        print("\n[1/11] Seeding Enterprise Users & Roles...")
        users_config = [
            {
                "email": "admin@nova.ai",
                "full_name": "NOVA Administrator",
                "role": UserRole.ADMIN,
                "password": "Admin@1234"
            },
            {
                "email": "security@nova.ai",
                "full_name": "Sarah Chen (Lead Security Architect)",
                "role": UserRole.SECURITY_ENGINEER,
                "password": "SecurityPass123!"
            },
            {
                "email": "dev@nova.ai",
                "full_name": "Alex Rivera (Senior Backend Engineer)",
                "role": UserRole.DEVELOPER,
                "password": "DevPassword123!"
            },
            {
                "email": "auditor@nova.ai",
                "full_name": "Elena Rostova (Chief Compliance Auditor)",
                "role": UserRole.AUDITOR,
                "password": "AuditorPass123!"
            },
            {
                "email": "harshith@nova.ai",
                "full_name": "Harshith (Platform Lead)",
                "role": UserRole.ADMIN,
                "password": "Password123!"
            },
        ]

        user_map = {}
        for u in users_config:
            res = await session.execute(select(User).where(User.email == u["email"]))
            user = res.scalars().first()
            if not user:
                user = User(
                    email=u["email"],
                    full_name=u["full_name"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                    auth_provider=AuthProvider.LOCAL,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                print(f"  + Created User: {u['email']} [{u['role'].value}]")
            else:
                # Idempotent: Preserve existing user data and credentials untouched
                print(f"  * Existing User Preserved: {u['email']} [{user.role.value}]")
            user_map[u["email"]] = user

        admin_user = user_map["admin@nova.ai"]
        sec_user = user_map["security@nova.ai"]
        dev_user = user_map["dev@nova.ai"]

        # -------------------------------------------------------------
        # 2. Repositories
        # -------------------------------------------------------------
        print("\n[2/11] Seeding Repositories for Source Studio...")
        repos_data = [
            {
                "name": "financial-backend-core",
                "url": "https://github.com/enterprise/financial-backend-core",
                "provider": RepoProviderType.GITHUB,
                "default_branch": "main",
                "scheduled_scan_enabled": True,
            },
            {
                "name": "nova-security-service",
                "url": "https://github.com/enterprise/nova-security-service",
                "provider": RepoProviderType.GITHUB,
                "default_branch": "main",
                "scheduled_scan_enabled": True,
            },
            {
                "name": "banking-gateway",
                "url": "https://github.com/enterprise/banking-gateway",
                "provider": RepoProviderType.GITLAB,
                "default_branch": "release/v2",
                "scheduled_scan_enabled": False,
            },
            {
                "name": "data/demo_repo",
                "url": "local://data/demo_repo",
                "provider": RepoProviderType.UPLOAD,
                "default_branch": "main",
                "scheduled_scan_enabled": True,
            }
        ]

        for r_data in repos_data:
            res = await session.execute(select(Repository).where(Repository.name == r_data["name"]))
            if not res.scalars().first():
                repo = Repository(
                    name=r_data["name"],
                    url=r_data["url"],
                    provider=r_data["provider"],
                    default_branch=r_data["default_branch"],
                    scheduled_scan_enabled=r_data["scheduled_scan_enabled"],
                    owner_id=admin_user.id
                )
                session.add(repo)
                print(f"  + Created Repository: {r_data['name']}")

        # -------------------------------------------------------------
        # 3. Knowledge Base Documents, Multi-version Evolution & Chunks
        # -------------------------------------------------------------
        print("\n[3/11] Seeding Knowledge Documents & Embeddings...")
        doc_group_pci = uuid.uuid4()
        doc_group_fapi = uuid.uuid4()
        doc_group_nist = uuid.uuid4()
        doc_group_zt = uuid.uuid4()

        docs_spec = [
            # PCI-DSS v3.2.1 (Historical version for Knowledge Evolution view)
            {
                "filename": "PCI_DSS_v3.2.1_Historical_Standard.pdf",
                "document_type": "pdf",
                "version": "3.2.1",
                "document_group_id": doc_group_pci,
                "is_latest": False,
                "author": "PCI Security Standards Council",
                "tags": ["pci-dss", "compliance", "banking", "deprecated"],
                "status": "archived",
                "health_status": "stale",
                "freshness_decay_factor": 0.45,
                "chunks": [
                    {
                        "heading": "Requirement 3.4: Legacy Cryptographic Protection",
                        "section_path": "PCI-DSS v3.2.1 > Requirement 3",
                        "content": "Render PAN unreadable anywhere it is stored using strong cryptography with associated key-management processes or index tokens.",
                    }
                ]
            },
            # PCI-DSS v4.0 (Latest active version)
            {
                "filename": "PCI_DSS_v4.0_Banking_Security_Standard.pdf",
                "document_type": "pdf",
                "version": "4.0",
                "document_group_id": doc_group_pci,
                "is_latest": True,
                "author": "PCI Security Standards Council",
                "tags": ["pci-dss", "compliance", "banking", "active-standard"],
                "status": "indexed",
                "health_status": "active",
                "freshness_decay_factor": 1.0,
                "chunks": [
                    {
                        "heading": "Requirement 3.4: Cardholder Data Cryptography",
                        "section_path": "PCI-DSS v4.0 > Section 3 > Req 3.4",
                        "content": "PCI-DSS Requirement 3.4: Protect sensitive cardholder data with strong cryptographic algorithms (AES-256-GCM or RSA-4096). Unencrypted PAN or credentials stored in plain text constitute a critical vulnerability.",
                    },
                    {
                        "heading": "Requirement 6.4.1: Public Web Application Defense",
                        "section_path": "PCI-DSS v4.0 > Section 6 > Req 6.4.1",
                        "content": "PCI-DSS Requirement 6.4.1: Protect public-facing web applications against automated attacks and injection flaws (SQLi, XSS, Command Injection). All input parameters must undergo strict schema validation and parameterization.",
                    },
                    {
                        "heading": "Requirement 7.1: Role-Based Access Control and MFA",
                        "section_path": "PCI-DSS v4.0 > Section 7 > Req 7.1",
                        "content": "PCI-DSS Requirement 7.1: Enforce Role-Based Access Control (RBAC) across all administrative APIs. Administrative functions must mandate multi-factor authentication and explicitly evaluate role privileges before execution.",
                    },
                    {
                        "heading": "Requirement 8.3: Strong Authentication Lifecycle",
                        "section_path": "PCI-DSS v4.0 > Section 8 > Req 8.3",
                        "content": "PCI-DSS Requirement 8.3: All access to system components must require multi-factor authentication (MFA). MFA cannot be bypassed for administrative accounts.",
                    }
                ]
            },
            # OWASP Financial API Security Guide
            {
                "filename": "OWASP_Financial_API_Security_Guide.md",
                "document_type": "md",
                "version": "2.0",
                "document_group_id": doc_group_fapi,
                "is_latest": True,
                "author": "OWASP Financial Security Taskforce",
                "tags": ["owasp", "api-security", "fapi", "authorization"],
                "status": "indexed",
                "health_status": "active",
                "freshness_decay_factor": 0.98,
                "chunks": [
                    {
                        "heading": "FAPI-01: Broken Object Level Authorization (BOLA)",
                        "section_path": "OWASP FAPI > Vulnerabilities > FAPI-01",
                        "content": "FAPI-01 Broken Object Level Authorization (BOLA): Ensure API endpoints verify that the requesting user owns or is authorized to access the specific resource identifier provided in request parameters.",
                    },
                    {
                        "heading": "FAPI-02: Unprotected Financial Transactions",
                        "section_path": "OWASP FAPI > Vulnerabilities > FAPI-02",
                        "content": "FAPI-02 Unprotected Financial Transactions: High-value payment transfers and fund movements must be protected by explicit permission checks and transaction limits to prevent unauthorized administrative escalation.",
                    },
                    {
                        "heading": "FAPI-03: Exposure of Sensitive API Tokens",
                        "section_path": "OWASP FAPI > Vulnerabilities > FAPI-03",
                        "content": "FAPI-03 Exposure of Sensitive API Tokens: Hardcoded credentials, database connection strings, or JWT signing secrets in source code repositories expose financial systems to immediate compromise.",
                    }
                ]
            },
            # NIST SP 800-53 Baseline
            {
                "filename": "NIST_SP_800_53_Control_Baselines.pdf",
                "document_type": "pdf",
                "version": "Rev 5",
                "document_group_id": doc_group_nist,
                "is_latest": True,
                "author": "National Institute of Standards and Technology",
                "tags": ["nist", "government", "security-controls"],
                "status": "indexed",
                "health_status": "active",
                "freshness_decay_factor": 0.95,
                "chunks": [
                    {
                        "heading": "AC-3: Access Enforcement Mechanisms",
                        "section_path": "NIST SP 800-53 > Access Control > AC-3",
                        "content": "NIST AC-3 Access Enforcement: The information system enforces approved authorizations for logical access to information and system resources in accordance with applicable access control policies.",
                    },
                    {
                        "heading": "SC-13: Cryptographic Protection",
                        "section_path": "NIST SP 800-53 > System and Communications Protection > SC-13",
                        "content": "NIST SC-13 Cryptographic Protection: The system implements cryptographic modules in accordance with applicable federal laws, directives, and policies using FIPS-validated cryptography.",
                    }
                ]
            },
            # Zero Trust Architecture Specification
            {
                "filename": "Zero_Trust_Network_Architecture_Policy.md",
                "document_type": "md",
                "version": "1.0",
                "document_group_id": doc_group_zt,
                "is_latest": True,
                "author": "Enterprise Architecture Board",
                "tags": ["zero-trust", "architecture", "microsegmentation"],
                "status": "indexed",
                "health_status": "active",
                "freshness_decay_factor": 0.92,
                "chunks": [
                    {
                        "heading": "ZT-01: Explicit Verification Principle",
                        "section_path": "Zero Trust Policy > Core Principles > ZT-01",
                        "content": "ZT-01: Never trust, always verify. Every access request must be fully authenticated, authorized, and encrypted before granting access across any network segment or microservice boundary.",
                    }
                ]
            }
        ]

        doc_objs = {}
        for d in docs_spec:
            res = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == d["filename"]))
            doc = res.scalars().first()
            if not doc:
                doc = KnowledgeDocument(
                    filename=d["filename"],
                    document_type=d["document_type"],
                    version=d["version"],
                    document_group_id=d["document_group_id"],
                    is_latest=d["is_latest"],
                    content_hash=str(uuid.uuid4()).replace("-", "")[:32],
                    author=d["author"],
                    tags=d["tags"],
                    status=d["status"],
                    health_status=d["health_status"],
                    freshness_decay_factor=d["freshness_decay_factor"],
                    file_path=f"data/knowledge_base/{d['filename']}",
                    file_size_bytes=sum(len(c["content"]) for c in d["chunks"]),
                    chunk_count=len(d["chunks"]),
                    page_count=len(d["chunks"]),
                    uploaded_by_id=admin_user.id
                )
                session.add(doc)
                await session.flush()

                for idx, c in enumerate(d["chunks"]):
                    # Generate normalized 384-dim dummy vector
                    dim = settings.knowledge_embedding_dim
                    vec = [((idx * 17 + i * 31) % 100) / 100.0 for i in range(dim)]
                    norm = sum(x*x for x in vec) ** 0.5 or 1.0
                    normalized_vec = [x / norm for x in vec]

                    chunk = KnowledgeChunk(
                        document_id=doc.id,
                        chunk_index=idx,
                        content=c["content"],
                        heading=c.get("heading"),
                        section_path=c.get("section_path"),
                        page_number=idx + 1,
                        token_count=len(c["content"].split()),
                        embedding=normalized_vec
                    )
                    session.add(chunk)
                print(f"  + Created Knowledge Doc: {d['filename']} (v{d['version']}) with {len(d['chunks'])} chunks")
            else:
                print(f"  * Existing Knowledge Doc: {d['filename']}")
            doc_objs[d["filename"]] = doc

        # -------------------------------------------------------------
        # 4. Knowledge Graph (Entities & Relations)
        # -------------------------------------------------------------
        print("\n[4/11] Seeding Knowledge Graph (Entities & Relations)...")
        pci_doc = doc_objs.get("PCI_DSS_v4.0_Banking_Security_Standard.pdf")
        owasp_doc = doc_objs.get("OWASP_Financial_API_Security_Guide.md")
        nist_doc = doc_objs.get("NIST_SP_800_53_Control_Baselines.pdf")

        if pci_doc and owasp_doc and nist_doc:
            entities_res = await session.execute(select(KnowledgeEntity))
            existing_entities = {e.entity_name: e for e in entities_res.scalars().all()}

            raw_entities = [
                (pci_doc.id, "PCI-DSS v4.0 Standard", "STANDARD", 8),
                (pci_doc.id, "Requirement 3.4 (Cardholder Cryptography)", "RULE", 6),
                (pci_doc.id, "Requirement 6.4.1 (AST Injection Prevention)", "RULE", 5),
                (pci_doc.id, "Requirement 7.1 (RBAC & MFA)", "RULE", 7),
                (pci_doc.id, "Requirement 8.3 (MFA Enforcement)", "RULE", 4),
                (pci_doc.id, "AES-256-GCM / RSA-4096", "ALGORITHM", 6),
                (pci_doc.id, "Multi-Factor Authentication (MFA)", "CONTROL", 9),
                (owasp_doc.id, "OWASP FAPI Framework", "FRAMEWORK", 10),
                (owasp_doc.id, "FAPI-01 (BOLA)", "VULNERABILITY", 7),
                (owasp_doc.id, "FAPI-02 (Unprotected Transactions)", "VULNERABILITY", 8),
                (owasp_doc.id, "FAPI-03 (Token Exposure)", "VULNERABILITY", 5),
                (owasp_doc.id, "Resource Ownership Check", "CONTROL", 6),
                (owasp_doc.id, "RequireRole('admin')", "CONTROL", 9),
                (nist_doc.id, "NIST SP 800-53 Standard", "STANDARD", 6),
                (nist_doc.id, "AC-3 Access Enforcement", "RULE", 5),
                (nist_doc.id, "SC-13 Cryptographic Protection", "RULE", 5),
            ]

            entity_lookup = {}
            for doc_id, name, etype, mentions in raw_entities:
                if name in existing_entities:
                    entity_lookup[name] = existing_entities[name]
                else:
                    ent = KnowledgeEntity(
                        document_id=doc_id,
                        entity_name=name,
                        entity_type=etype,
                        mention_count=mentions
                    )
                    session.add(ent)
                    await session.flush()
                    entity_lookup[name] = ent
                    print(f"  + Added Graph Entity: {name} ({etype})")

            relations_spec = [
                ("PCI-DSS v4.0 Standard", "Requirement 3.4 (Cardholder Cryptography)", "ENFORCES"),
                ("Requirement 3.4 (Cardholder Cryptography)", "AES-256-GCM / RSA-4096", "REQUIRES"),
                ("PCI-DSS v4.0 Standard", "Requirement 6.4.1 (AST Injection Prevention)", "ENFORCES"),
                ("PCI-DSS v4.0 Standard", "Requirement 7.1 (RBAC & MFA)", "ENFORCES"),
                ("Requirement 7.1 (RBAC & MFA)", "Multi-Factor Authentication (MFA)", "REQUIRES"),
                ("Requirement 7.1 (RBAC & MFA)", "RequireRole('admin')", "MANDATES"),
                ("OWASP FAPI Framework", "FAPI-01 (BOLA)", "DEFINES"),
                ("FAPI-01 (BOLA)", "Resource Ownership Check", "MITIGATED_BY"),
                ("OWASP FAPI Framework", "FAPI-02 (Unprotected Transactions)", "DEFINES"),
                ("FAPI-02 (Unprotected Transactions)", "RequireRole('admin')", "MITIGATED_BY"),
                ("OWASP FAPI Framework", "FAPI-03 (Token Exposure)", "DEFINES"),
                ("NIST SP 800-53 Standard", "AC-3 Access Enforcement", "SPECIFIES"),
                ("AC-3 Access Enforcement", "RequireRole('admin')", "ALIGNS_WITH"),
                ("NIST SP 800-53 Standard", "SC-13 Cryptographic Protection", "SPECIFIES"),
                ("SC-13 Cryptographic Protection", "AES-256-GCM / RSA-4096", "REQUIRES"),
            ]

            for src_name, tgt_name, rel_type in relations_spec:
                src_ent = entity_lookup.get(src_name)
                tgt_ent = entity_lookup.get(tgt_name)
                if src_ent and tgt_ent:
                    res_rel = await session.execute(
                        select(KnowledgeRelation).where(
                            KnowledgeRelation.source_entity_id == src_ent.id,
                            KnowledgeRelation.target_entity_id == tgt_ent.id,
                            KnowledgeRelation.relation_type == rel_type
                        )
                    )
                    if not res_rel.scalars().first():
                        rel = KnowledgeRelation(
                            source_entity_id=src_ent.id,
                            target_entity_id=tgt_ent.id,
                            relation_type=rel_type
                        )
                        session.add(rel)
                        print(f"  + Added Graph Edge: ({src_name}) --[{rel_type}]--> ({tgt_name})")

        # -------------------------------------------------------------
        # 5. FAQ Axioms (Stage 0 Instant Hits & Self-Healing Gap Candidates)
        # -------------------------------------------------------------
        print("\n[5/11] Seeding Stage 0 FAQ Rules & Knowledge Gap Inbox...")
        faq_items = [
            # Active Stage 0 Rules (0ms hit)
            {
                "keyword": "what is aekof",
                "response": "AEKOF (Adaptive Enterprise Knowledge Operating Framework) is the core architecture powering NOVA, featuring dynamic routing, pairwise NLI consensus, and 8-dimensional Platt confidence calibration.",
                "is_active": True,
                "is_draft": False
            },
            {
                "keyword": "how to reset password",
                "response": "To reset your password, navigate to Account Settings > Security or use the corporate SSO provider's self-service recovery options.",
                "is_active": True,
                "is_draft": False
            },
            {
                "keyword": "what is graphrag",
                "response": "GraphRAG extracts structured entities and semantic relations into a knowledge graph to answer multi-hop security queries that require cross-repository context.",
                "is_active": True,
                "is_draft": False
            },
            {
                "keyword": "how does pairwise nli consensus work",
                "response": "NOVA builds an N x N cross-encoder matrix across retrieved evidence to calculate consensus agreement C_agreement = (N_supports - N_contradicts) / N_total, blocking hallucinations when contradiction occurs.",
                "is_active": True,
                "is_draft": False
            },
            {
                "keyword": "what is platt trust calibration",
                "response": "Platt trust calibration maps an 8-dimensional evidence feature vector via logistic sigmoid P(Correct|C) = 1 / (1 + e^-z) into a calibrated trust probability subordinated to hard safety gates.",
                "is_active": True,
                "is_draft": False
            },
            # Draft / Knowledge Gap Candidates (Ready for 1-click promotion on /knowledge-evolution)
            {
                "keyword": "how to rotate jwt signing secrets",
                "response": "Candidate Auto-Generated: Rotate JWT secrets by deploying dual-key validation: sign new tokens with key_v2 while continuing to verify older tokens with key_v1 until TTL expiry.",
                "is_active": False,
                "is_draft": True
            },
            {
                "keyword": "can developers bypass role authorization in staging",
                "response": "Candidate Auto-Generated: No, staging environments enforce strict RBAC policies parity with production. Developer bypass flags are blocked by CI/CD security gates.",
                "is_active": False,
                "is_draft": True
            },
            {
                "keyword": "how to configure database connection pooling with pgvector",
                "response": "Candidate Auto-Generated: Configure SQLAlchemy async_sessionmaker with pool_size=20, max_overflow=10, and ensure HNSW vector indexes use vector_cosine_ops.",
                "is_active": False,
                "is_draft": True
            }
        ]

        for f in faq_items:
            res = await session.execute(select(FAQRule).where(FAQRule.keyword == f["keyword"]))
            if not res.scalars().first():
                rule = FAQRule(
                    keyword=f["keyword"],
                    response=f["response"],
                    is_active=f["is_active"],
                    is_draft=f["is_draft"],
                    created_by_id=admin_user.id
                )
                session.add(rule)
                print(f"  + Added FAQ Rule: '{f['keyword']}' (Draft: {f['is_draft']})")

        # -------------------------------------------------------------
        # 6. Assistant Chat Sessions & Detailed Messages
        # -------------------------------------------------------------
        print("\n[6/11] Seeding Assistant Chat Sessions & Multimodal Messages...")
        res_sess = await session.execute(select(ChatSession).where(ChatSession.user_id == admin_user.id))
        existing_sess = res_sess.scalars().all()
        if not existing_sess:
            sess1 = ChatSession(
                user_id=admin_user.id,
                title="Banking API Privilege Escalation Forensic Audit",
                context_summary="Comprehensive analysis of POST /admin/transactions and RequireRole('admin') authorization boundary.",
                active_entities={"asset": "POST /admin/transactions", "cwe": "CWE-285", "property": "AUTHORIZATION"}
            )
            session.add(sess1)
            await session.flush()

            # Chat Message 1 (User)
            m1 = ChatMessage(
                session_id=sess1.id,
                role="user",
                content="Is the POST /admin/transactions endpoint safe and protected against unauthorized access according to our security architecture?",
                citations=[],
                confidence_vector={},
                reasoning_trace={},
                consensus_matrix={}
            )
            session.add(m1)

            # Chat Message 2 (Assistant - with Full Reasoning Trace & Calibrated Trust Score)
            m2 = ChatMessage(
                session_id=sess1.id,
                role="assistant",
                content=(
                    "### Security Intelligence & Policy Evaluation\n\n"
                    "Based on NOVA's **Dual-Track Evidence Fusion** and **Pairwise NLI Reasoning Matrix**:\n\n"
                    "1. **AST Structural Observation**: Code analysis of `data/demo_repo/admin_transactions.py:42` confirms that `POST /admin/transactions` lacks the `@require_role('admin')` dependency decorator.\n"
                    "2. **Control Evaluation**: Control state for `AUTHORIZATION` is **`ABSENT`** on this administrative transaction asset.\n"
                    "3. **Threat Scenario**: Verified as **`PRIVILEGE_ESCALATION_RISK`** (Severity: `HIGH`, CWE-285).\n"
                    "4. **Remediation**: Attach `@router.post('/admin/transactions', dependencies=[Depends(RequireRole('admin'))])` to enforce role verification.\n\n"
                    "> [!IMPORTANT]\n"
                    "> **Safety Gate Verdict**: NOVA's Two-Stage Hard Safety Policy Gate verified agreement between AST code observations and OWASP FAPI guidelines with a **95.2% Calibrated Trust Score**."
                ),
                citations=[
                    {
                        "source_id": "sec-intel-001",
                        "title": "Verified Risk Assessment: PRIVILEGE_ESCALATION_RISK",
                        "file_path": "data/demo_repo/admin_transactions.py:42",
                        "cwe_id": "CWE-285",
                        "reliability_weight": 0.95
                    },
                    {
                        "source_id": "kb-fapi-02",
                        "title": "OWASP Financial API Security Guide",
                        "file_path": "data/knowledge_base/OWASP_Financial_API_Security_Guide.md",
                        "reliability_weight": 0.98
                    }
                ],
                confidence_vector={
                    "retrieval_confidence": 0.94,
                    "consensus_agreement": 0.96,
                    "citation_coverage": 1.0,
                    "reasoning_depth": 0.92,
                    "freshness_factor": 1.0,
                    "hallucination_risk": 0.02,
                    "source_reliability": 0.96,
                    "user_feedback_prior": 0.90
                },
                calibrated_trust_score=0.952,
                reasoning_trace={
                    "pipeline_stage": "STAGE_2_SAFETY_GATE_PASS",
                    "nli_consensus": "SUPPORTS",
                    "policy_gate": "GENERATE",
                    "stages_evaluated": ["RETRIEVAL", "NLI_MATRIX", "PLATT_CALIBRATION", "SAFETY_GATE"]
                },
                consensus_matrix={
                    "matrix_size": "2x2",
                    "supports_count": 1,
                    "contradicts_count": 0,
                    "c_agreement": 0.96
                }
            )
            session.add(m2)

            # Session 2: Cryptographic baseline
            sess2 = ChatSession(
                user_id=admin_user.id,
                title="PCI-DSS v4.0 Storage Cryptography Baseline",
                context_summary="Verification of AES-256-GCM encryption requirements for PAN records.",
                active_entities={"standard": "PCI-DSS v4.0", "req": "3.4"}
            )
            session.add(sess2)
            await session.flush()

            m3 = ChatMessage(
                session_id=sess2.id,
                role="user",
                content="What cryptographic algorithms are mandated by PCI-DSS v4.0 Requirement 3.4 for storing cardholder data?",
                citations=[],
                confidence_vector={},
                reasoning_trace={},
                consensus_matrix={}
            )
            m4 = ChatMessage(
                session_id=sess2.id,
                role="assistant",
                content=(
                    "**PCI-DSS v4.0 Requirement 3.4 Compliance Standard**:\n\n"
                    "- **Mandated Symmetric Encryption**: `AES-256-GCM` or `AES-256-CBC` with authenticated key management.\n"
                    "- **Mandated Asymmetric Encryption**: `RSA-4096` or `ECDSA P-384`.\n"
                    "- **Strict Prohibition**: Plain text storage of Primary Account Numbers (PAN), CVV/CVC, or authorization PIN blocks is strictly prohibited."
                ),
                citations=[
                    {
                        "source_id": "kb-pci-34",
                        "title": "PCI_DSS_v4.0_Banking_Security_Standard.pdf",
                        "file_path": "data/knowledge_base/PCI_DSS_v4.0_Banking_Security_Standard.pdf",
                        "reliability_weight": 1.0
                    }
                ],
                confidence_vector={"retrieval_confidence": 0.98, "consensus_agreement": 1.0},
                calibrated_trust_score=0.984,
                reasoning_trace={"pipeline_stage": "STAGE_2_SAFETY_GATE_PASS", "policy_gate": "GENERATE"},
                consensus_matrix={"supports_count": 1, "contradicts_count": 0, "c_agreement": 1.0}
            )
            session.add_all([m3, m4])
            print("  + Seeded 2 Active Assistant Chat Sessions with 4 Verified Multimodal Messages")

        # -------------------------------------------------------------
        # 7. Audit Logs (Rich Activity Trail for /my-activity)
        # -------------------------------------------------------------
        print("\n[7/11] Seeding Activity & Security Audit Logs...")
        now = datetime.datetime.now(datetime.timezone.utc)
        audit_entries = [
            {
                "user_id": admin_user.id,
                "user_email": admin_user.email,
                "action": "auth.login",
                "resource_type": "user",
                "resource_id": str(admin_user.id),
                "status": "success",
                "ip_address": "127.0.0.1",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"auth_method": "password", "session_issued": True},
                "created_at": now - datetime.timedelta(hours=4)
            },
            {
                "user_id": admin_user.id,
                "user_email": admin_user.email,
                "action": "knowledge.document.upload",
                "resource_type": "knowledge_document",
                "resource_id": "PCI_DSS_v4.0_Banking_Security_Standard.pdf",
                "status": "success",
                "ip_address": "127.0.0.1",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"chunks_extracted": 4, "embedding_dim": 384},
                "created_at": now - datetime.timedelta(hours=3, minutes=45)
            },
            {
                "user_id": sec_user.id,
                "user_email": sec_user.email,
                "action": "security.analysis.run",
                "resource_type": "security_pipeline",
                "resource_id": "data/demo_repo",
                "status": "success",
                "ip_address": "192.168.1.105",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"assets_discovered": 5, "posture_score": 95.0, "rating": "STRONG"},
                "created_at": now - datetime.timedelta(hours=2, minutes=30)
            },
            {
                "user_id": admin_user.id,
                "user_email": admin_user.email,
                "action": "faq.rule.promote",
                "resource_type": "faq_rule",
                "resource_id": "what is aekof",
                "status": "success",
                "ip_address": "127.0.0.1",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"previous_state": "draft", "promoted_to": "active_stage_0"},
                "created_at": now - datetime.timedelta(hours=1, minutes=15)
            },
            {
                "user_id": dev_user.id,
                "user_email": dev_user.email,
                "action": "benchmark.probe.executed",
                "resource_type": "rag_benchmark",
                "resource_id": "probe_run_01",
                "status": "success",
                "ip_address": "192.168.1.112",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"latency_ms": 780, "precision": 0.886, "recall": 0.912},
                "created_at": now - datetime.timedelta(minutes=30)
            },
            {
                "user_id": admin_user.id,
                "user_email": admin_user.email,
                "action": "remediation.patch.verify",
                "resource_type": "security_assessment",
                "resource_id": "sec-intel-001",
                "status": "success",
                "ip_address": "127.0.0.1",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "details": {"status_after": "VERIFIED_FIXED", "delta_posture": "+20.0%"},
                "created_at": now - datetime.timedelta(minutes=10)
            }
        ]

        res_audit = await session.execute(select(func.count(AuditLog.id)))
        if res_audit.scalar_one() == 0:
            for ae in audit_entries:
                audit = AuditLog(
                    user_id=ae["user_id"],
                    user_email=ae["user_email"],
                    action=ae["action"],
                    resource_type=ae["resource_type"],
                    resource_id=ae["resource_id"],
                    status=ae["status"],
                    ip_address=ae["ip_address"],
                    user_agent=ae["user_agent"],
                    details=ae["details"],
                    created_at=ae["created_at"]
                )
                session.add(audit)
            print(f"  + Seeded {len(audit_entries)} Audit Log Records")
        else:
            print(f"  * Audit log records already exist (preserved)")

        # -------------------------------------------------------------
        # 8. Search Analytics Telemetry & User Feedback Entries
        # -------------------------------------------------------------
        print("\n[8/11] Seeding RAG Telemetry & Feedback Data for /rag-operations...")
        telemetry_logs = [
            {
                "feature": "assistant",
                "query": "Is POST /admin/transactions protected by role checks?",
                "result_count": 4,
                "top_score": 0.952,
                "fallback_triggered": False,
                "latency_ms": 32.4,
                "user_id": admin_user.id
            },
            {
                "feature": "knowledge_base",
                "query": "PCI-DSS Requirement 3.4 encryption standards for cardholder PAN",
                "result_count": 3,
                "top_score": 0.981,
                "fallback_triggered": False,
                "latency_ms": 18.6,
                "user_id": sec_user.id
            },
            {
                "feature": "security_intelligence",
                "query": "AST observations for authentication boundary crossing",
                "result_count": 5,
                "top_score": 0.940,
                "fallback_triggered": False,
                "latency_ms": 24.1,
                "user_id": sec_user.id
            },
            {
                "feature": "executive_intelligence",
                "query": "Overall enterprise security posture trajectory deltas",
                "result_count": 3,
                "top_score": 0.995,
                "fallback_triggered": False,
                "latency_ms": 12.8,
                "user_id": admin_user.id
            },
            {
                "feature": "knowledge_gap",
                "query": "How to configure zero trust mutual TLS authentication",
                "result_count": 0,
                "top_score": 0.0,
                "fallback_triggered": True,
                "latency_ms": 45.2,
                "user_id": dev_user.id
            }
        ]

        res_tel = await session.execute(select(func.count(SearchAnalyticsLog.id)))
        if res_tel.scalar_one() == 0:
            for tl in telemetry_logs:
                s_log = SearchAnalyticsLog(
                    feature=tl["feature"],
                    query=tl["query"],
                    result_count=tl["result_count"],
                    top_score=tl["top_score"],
                    fallback_triggered=tl["fallback_triggered"],
                    latency_ms=tl["latency_ms"],
                    user_id=tl["user_id"]
                )
                session.add(s_log)
            print(f"  + Seeded {len(telemetry_logs)} Telemetry Logs")
        else:
            print("  * Telemetry logs already exist (preserved)")

        res_fb = await session.execute(select(func.count(Feedback.id)))
        if res_fb.scalar_one() == 0:
            for fb in feedbacks:
                f_entry = Feedback(
                    feature=fb["feature"],
                    reference_id=fb["reference_id"],
                    rating=fb["rating"],
                    comment=fb["comment"],
                    user_id=fb["user_id"]
                )
                session.add(f_entry)
            print(f"  + Seeded {len(feedbacks)} Feedback Ratings")
        else:
            print("  * Feedback ratings already exist (preserved)")

        # -------------------------------------------------------------
        # 9. Security Intelligence Assets, Observations, Controls, Scenarios, Assessments
        # -------------------------------------------------------------
        print("\n[9/11] Seeding Security Intelligence Context Graph & Assessments...")
        # Check if assets exist
        res_assets = await session.execute(select(SecurityIntelAsset))
        existing_assets = res_assets.scalars().all()
        if not existing_assets:
            # Asset 1: POST /admin/transactions
            a1 = SecurityIntelAsset(
                asset_name="POST /admin/transactions",
                asset_type="ENDPOINT",
                criticality="HIGH",
                owner="Payments Engineering Team",
                location="data/demo_repo/admin_transactions.py:42",
                attributes={"protocol": "HTTPS", "framework": "FastAPI", "category": "FINANCIAL_API"}
            )
            # Asset 2: Core Transaction Controller
            a2 = SecurityIntelAsset(
                asset_name="TransactionController",
                asset_type="SERVICE",
                criticality="CRITICAL",
                owner="Core Banking Architecture",
                location="data/demo_repo/transaction_controller.py:12",
                attributes={"language": "Python 3.10", "type": "Microservice"}
            )
            # Asset 3: User Authentication Service
            a3 = SecurityIntelAsset(
                asset_name="AuthService",
                asset_type="APPLICATION",
                criticality="CRITICAL",
                owner="IAM Security Team",
                location="data/demo_repo/auth_service.py:1",
                attributes={"auth_standard": "OAuth2 / JWT", "mfa": True}
            )
            # Asset 4: Primary PostgreSQL Store
            a4 = SecurityIntelAsset(
                asset_name="DATABASE: banking_core_db",
                asset_type="DATABASE",
                criticality="CRITICAL",
                owner="DBA Infrastructure Team",
                location="postgresql://core_db:5432/banking",
                attributes={"engine": "PostgreSQL 15", "encryption_at_rest": "AES-256"}
            )
            # Asset 5: Payment Gateway API
            a5 = SecurityIntelAsset(
                asset_name="POST /transfers/wire",
                asset_type="ENDPOINT",
                criticality="CRITICAL",
                owner="Wire Operations",
                location="data/demo_repo/wire_transfer.py:88",
                attributes={"limit_check": True, "dual_control": True}
            )
            session.add_all([a1, a2, a3, a4, a5])
            await session.flush()

            # Observations for a1
            obs1 = SecurityIntelObservation(
                asset_id=a1.id,
                observation_type="PUBLIC_ENDPOINT",
                location="data/demo_repo/admin_transactions.py:42",
                evidence_span="@router.post('/admin/transactions')",
                confidence=0.98,
                provenance="ast_decorator_visitor",
                attributes={"route": "/admin/transactions", "method": "POST"}
            )
            obs2 = SecurityIntelObservation(
                asset_id=a1.id,
                observation_type="AUTHORIZATION_BOUNDARY",
                location="data/demo_repo/admin_transactions.py:44",
                evidence_span="def process_admin_transaction(tx_payload: TransactionSchema):",
                confidence=0.95,
                provenance="ast_arg_visitor",
                attributes={"missing_role_decorator": True}
            )
            obs3 = SecurityIntelObservation(
                asset_id=a1.id,
                observation_type="DATABASE_ACCESS",
                location="data/demo_repo/admin_transactions.py:65",
                evidence_span="await db.execute(insert(TransactionModel)...)",
                confidence=0.92,
                provenance="ast_call_visitor",
                attributes={"target_table": "transactions"}
            )

            # Controls for a1
            c1 = SecurityIntelControl(
                asset_id=a1.id,
                control_type="AUTHORIZATION",
                scope="POST /admin/transactions",
                state="PRESENT", # Showing verified fixed after patch
                evidence="dependencies=[Depends(RequireRole('admin'))]",
                confidence=0.96
            )
            c2 = SecurityIntelControl(
                asset_id=a1.id,
                control_type="AUTHENTICATION",
                scope="POST /admin/transactions",
                state="PRESENT",
                evidence="Depends(get_current_active_user)",
                confidence=0.98
            )
            c3 = SecurityIntelControl(
                asset_id=a1.id,
                control_type="INPUT_VALIDATION",
                scope="POST /admin/transactions",
                state="PRESENT",
                evidence="tx_payload: TransactionSchema",
                confidence=0.95
            )

            # Risk Scenario for a1
            sc1 = SecurityIntelRiskScenario(
                asset_id=a1.id,
                scenario_type="PRIVILEGE_ESCALATION_RISK",
                trust_boundary_crossed="INTERNET -> APPLICATION_CORE",
                attack_path={
                    "steps": [
                        "1. Attacker authenticates with standard user credentials",
                        "2. Dispatches POST /admin/transactions request without admin role",
                        "3. Administrative transaction executed due to missing role barrier"
                    ]
                },
                exposure_signal="PUBLIC_ENDPOINT_WITH_ELEVATED_PRIVILEGE",
                control_status="AUTHORIZATION_PRESENT_VERIFIED",
                potential_impact="Unauthorized balance adjustment or privilege escalation across banking accounts.",
                verification_state="VERIFIED"
            )

            # Verified Assessment for a1
            ass1 = SecurityIntelAssessment(
                asset_id=a1.id,
                risk_type="PRIVILEGE_ESCALATION_RISK",
                severity="HIGH",
                confidence=0.95,
                affected_scope="data/demo_repo/admin_transactions.py:42-70",
                evidence_chain=[
                    {"fact": "POST endpoint discovered in AST", "line": 42},
                    {"fact": "No RequireRole('admin') dependency attached", "line": 44},
                    {"fact": "Direct write to transactions table", "line": 65}
                ],
                attack_path=[
                    "Client sends unprivileged HTTP request",
                    "Gateway checks authentication (passes)",
                    "Controller lacks role authorization check",
                    "Administrative funds transfer is executed"
                ],
                controls_evaluated=[
                    {"type": "AUTHORIZATION", "state": "PRESENT", "confidence": 0.96},
                    {"type": "AUTHENTICATION", "state": "PRESENT", "confidence": 0.98}
                ],
                reasoning="The administrative endpoint POST /admin/transactions was identified in AST analysis. Following remediation patch application, RequireRole('admin') is active and verified fixed.",
                remediation="Apply @router.post('/admin/transactions', dependencies=[Depends(RequireRole('admin'))])",
                status="VERIFIED_FIXED",
                commit_hash="f68521e"
            )

            session.add_all([obs1, obs2, obs3, c1, c2, c3, sc1, ass1])
            print("  + Seeded 5 Security Assets, 3 AST Observations, 3 Controls, 1 Risk Scenario, and 1 Verified Assessment")

        # Baseline Security Intel Scan
        res_scans = await session.execute(select(SecurityIntelScan))
        if not res_scans.scalars().first():
            demo_scan = SecurityIntelScan(
                project_name="data/demo_repo",
                source_type="LOCAL",
                source_identifier="data/demo_repo",
                status="COMPLETED",
                progress=100,
                stage="COMPLETED",
                posture_score=85.0,
                posture_rating="STRONG",
                delta_score=10.0,
                trend_direction="IMPROVED",
                result_summary={
                    "assets_count": 5,
                    "observations_count": 3,
                    "controls_count": 3,
                    "scenarios_count": 1,
                    "assessments_count": 1,
                    "critical_count": 0,
                    "high_count": 1,
                    "medium_count": 0,
                    "low_count": 0,
                    "verified_fixed_count": 1
                },
                started_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2),
                completed_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2),
                owner_id=admin_user.id
            )
            session.add(demo_scan)
            print("  + Seeded Baseline Completed Security Intelligence Scan")

        # -------------------------------------------------------------
        # 10. Temporal Security Posture Snapshots ($S_0 \to S_3$)
        # -------------------------------------------------------------
        print("\n[10/11] Seeding Temporal Posture Trajectory Snapshots for Executive Radar...")
        res_posture = await session.execute(select(SecurityIntelPostureSnapshot))
        existing_snaps = res_posture.scalars().all()
        if not existing_snaps:
            now = datetime.datetime.now(datetime.timezone.utc)
            posture_records = [
                {
                    "created_at": now - datetime.timedelta(days=14),
                    "analysis_run_id": str(uuid.uuid4()),
                    "target_scope": "data/demo_repo",
                    "commit_hash": "a1b2c3d",
                    "posture_score": 62.5,
                    "posture_rating": "NEEDS_ATTENTION",
                    "control_coverage_pct": 50.0,
                    "total_assets_count": 5,
                    "unresolved_risks_count": 3,
                    "critical_risks_count": 1,
                    "high_risks_count": 2,
                    "medium_risks_count": 0,
                    "low_risks_count": 0,
                    "verified_fixed_count": 0,
                    "delta_score": None,
                    "trend_direction": "FIRST_RUN",
                    "risk_evolution_summary": {"new_risks_count": 3, "resolved_risks_count": 0, "persistent_risks_count": 0}
                },
                {
                    "created_at": now - datetime.timedelta(days=7),
                    "analysis_run_id": str(uuid.uuid4()),
                    "target_scope": "data/demo_repo",
                    "commit_hash": "b2c3d4e",
                    "posture_score": 75.0,
                    "posture_rating": "MODERATE",
                    "control_coverage_pct": 75.0,
                    "total_assets_count": 5,
                    "unresolved_risks_count": 2,
                    "critical_risks_count": 0,
                    "high_risks_count": 2,
                    "medium_risks_count": 0,
                    "low_risks_count": 0,
                    "verified_fixed_count": 1,
                    "delta_score": 12.5,
                    "trend_direction": "IMPROVED",
                    "risk_evolution_summary": {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 2}
                },
                {
                    "created_at": now - datetime.timedelta(days=2),
                    "analysis_run_id": str(uuid.uuid4()),
                    "target_scope": "data/demo_repo",
                    "commit_hash": "c3d4e5f",
                    "posture_score": 85.0,
                    "posture_rating": "STRONG",
                    "control_coverage_pct": 85.0,
                    "total_assets_count": 5,
                    "unresolved_risks_count": 1,
                    "critical_risks_count": 0,
                    "high_risks_count": 1,
                    "medium_risks_count": 0,
                    "low_risks_count": 0,
                    "verified_fixed_count": 2,
                    "delta_score": 10.0,
                    "trend_direction": "IMPROVED",
                    "risk_evolution_summary": {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 1}
                },
                {
                    "created_at": now,
                    "analysis_run_id": str(uuid.uuid4()),
                    "target_scope": "data/demo_repo",
                    "commit_hash": "f68521e",
                    "posture_score": 95.0,
                    "posture_rating": "STRONG",
                    "control_coverage_pct": 100.0,
                    "total_assets_count": 5,
                    "unresolved_risks_count": 0,
                    "critical_risks_count": 0,
                    "high_risks_count": 0,
                    "medium_risks_count": 0,
                    "low_risks_count": 0,
                    "verified_fixed_count": 3,
                    "delta_score": 10.0,
                    "trend_direction": "IMPROVED",
                    "risk_evolution_summary": {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 0}
                }
            ]

            for s in posture_records:
                snap = SecurityIntelPostureSnapshot(
                    created_at=s["created_at"],
                    analysis_run_id=s["analysis_run_id"],
                    target_scope=s["target_scope"],
                    commit_hash=s["commit_hash"],
                    posture_score=s["posture_score"],
                    posture_rating=s["posture_rating"],
                    control_coverage_pct=s["control_coverage_pct"],
                    total_assets_count=s["total_assets_count"],
                    unresolved_risks_count=s["unresolved_risks_count"],
                    critical_risks_count=s["critical_risks_count"],
                    high_risks_count=s["high_risks_count"],
                    medium_risks_count=s["medium_risks_count"],
                    low_risks_count=s["low_risks_count"],
                    verified_fixed_count=s["verified_fixed_count"],
                    delta_score=s["delta_score"],
                    trend_direction=s["trend_direction"],
                    risk_evolution_summary=s["risk_evolution_summary"]
                )
                session.add(snap)
                print(f"  + Seeded Posture Snapshot: {s['posture_score']}/100 ({s['trend_direction']})")

        # -------------------------------------------------------------
        # 11. System Settings
        # -------------------------------------------------------------
        print("\n[11/11] Seeding System & RAG Configuration Settings...")
        settings_dict = {
            "platt_trust_threshold": "0.70",
            "nli_contradiction_cutoff": "0.20",
            "fastembed_model": "BAAI/bge-small-en-v1.5",
            "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "stage_0_cache_enabled": "true",
            "sliding_window_memory_turns": "10",
            "system_mode": "ENTERPRISE_PRODUCTION"
        }

        for key, val in settings_dict.items():
            res_s = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
            if not res_s.scalars().first():
                setting = SystemSetting(key=key, value=val)
                session.add(setting)
                print(f"  + Seeded Setting: {key} = {val}")

        await session.commit()

    await engine.dispose()
    print("\n=================================================================")
    print("✨ ALL PLATFORM DATA SEEDED SUCCESSFULLY FOR ALL SCREENS!")
    print("=================================================================")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NOVA Master Data Seeder")
    parser.add_argument("--init-only", action="store_true", help="Skip seeding if persistent data already exists")
    parser.add_argument("--force", action="store_true", help="Force seeding even if data already exists")
    args = parser.parse_args()
    asyncio.run(seed_all(init_only=args.init_only, force=args.force))
