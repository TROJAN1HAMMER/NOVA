import asyncio
import datetime
import uuid
import traceback
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
from app.models.system_setting import SystemSetting
from app.models.security_intelligence import (
    SecurityIntelAsset, SecurityIntelObservation, SecurityIntelControl,
    SecurityIntelRiskScenario, SecurityIntelAssessment, SecurityIntelPostureSnapshot
)

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # Step 1: Users
        try:
            print("Running Step 1: Users...")
            user_specs = [
                ("admin@nova.ai", "NOVA Administrator", UserRole.ADMIN, "Admin@1234"),
                ("security@nova.ai", "Sarah Chen (Security Architect)", UserRole.SECURITY_ENGINEER, "SecurityPass123!"),
                ("dev@nova.ai", "Alex Rivera (Senior Engineer)", UserRole.DEVELOPER, "DevPassword123!"),
                ("auditor@nova.ai", "Elena Rostova (Compliance Auditor)", UserRole.AUDITOR, "AuditorPass123!"),
                ("harshith@nova.ai", "Harshith (Platform Lead)", UserRole.ADMIN, "Password123!"),
            ]
            for email, name, role, pwd in user_specs:
                res = await session.execute(select(User).where(User.email == email))
                u = res.scalars().first()
                if not u:
                    u = User(
                        email=email, full_name=name,
                        hashed_password=hash_password(pwd),
                        role=role, auth_provider=AuthProvider.LOCAL,
                        is_active=True
                    )
                    session.add(u)
                else:
                    u.hashed_password = hash_password(pwd)
                    u.role = role
                    u.full_name = name
                    u.is_active = True
            await session.commit()
            print("Step 1 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 1 FAILED:", e)
            traceback.print_exc()

        # Step 2: Repositories
        try:
            print("Running Step 2: Repositories...")
            res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
            admin = res.scalars().first()
            repo_specs = [
                ("financial-backend-core", "https://github.com/enterprise/financial-backend-core", RepoProviderType.GITHUB, "main", True),
                ("nova-security-service", "https://github.com/enterprise/nova-security-service", RepoProviderType.GITHUB, "main", True),
                ("banking-gateway", "https://github.com/enterprise/banking-gateway", RepoProviderType.GITLAB, "release/v2", False),
                ("data/demo_repo", "local://data/demo_repo", RepoProviderType.UPLOAD, "main", True),
            ]
            for name, url, prov, branch, sched in repo_specs:
                res = await session.execute(select(Repository).where(Repository.name == name))
                r = res.scalars().first()
                if not r:
                    r = Repository(name=name, url=url, provider=prov, default_branch=branch, scheduled_scan_enabled=sched, owner_id=admin.id)
                    session.add(r)
                else:
                    r.owner_id = admin.id
            await session.commit()
            print("Step 2 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 2 FAILED:", e)
            traceback.print_exc()

        # Step 3: Knowledge Documents
        try:
            print("Running Step 3: Knowledge Docs...")
            res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
            admin = res.scalars().first()
            pci_grp = uuid.uuid4()
            fapi_grp = uuid.uuid4()
            nist_grp = uuid.uuid4()
            docs = [
                ("PCI_DSS_v4.0_Banking_Security_Standard.pdf", "pdf", "4.0", pci_grp, True, "PCI Security Council", ["pci-dss", "banking", "compliance"], [
                    ("Req 3.4: Cardholder Data Cryptography", "PCI-DSS v4.0 > Section 3", "Protect sensitive cardholder data with strong cryptographic algorithms (AES-256-GCM or RSA-4096). Unencrypted PAN or credentials stored in plain text constitute a critical vulnerability."),
                    ("Req 6.4.1: Public Web App Defense", "PCI-DSS v4.0 > Section 6", "Protect public-facing web applications against automated attacks and injection flaws (SQLi, XSS, Command Injection). All input parameters must undergo strict schema validation and parameterization."),
                    ("Req 7.1: RBAC & MFA Enforcement", "PCI-DSS v4.0 > Section 7", "Enforce Role-Based Access Control (RBAC) across all administrative APIs. Administrative functions must mandate multi-factor authentication and explicitly evaluate role privileges before execution."),
                ]),
                ("PCI_DSS_v3.2.1_Historical_Standard.pdf", "pdf", "3.2.1", pci_grp, False, "PCI Security Council", ["pci-dss", "historical", "deprecated"], [
                    ("Legacy Req 3.4 Cryptography", "PCI-DSS v3.2.1 > Section 3", "Render PAN unreadable anywhere it is stored using strong cryptography with associated key-management processes."),
                ]),
                ("OWASP_Financial_API_Security_Guide.md", "md", "2.0", fapi_grp, True, "OWASP Foundation", ["owasp", "fapi", "api-security"], [
                    ("FAPI-01: Broken Object Level Authorization", "OWASP FAPI > FAPI-01", "Ensure API endpoints verify that the requesting user owns or is authorized to access the specific resource identifier provided in request parameters."),
                    ("FAPI-02: Unprotected Financial Transactions", "OWASP FAPI > FAPI-02", "High-value payment transfers and fund movements must be protected by explicit permission checks and transaction limits to prevent unauthorized administrative escalation."),
                    ("FAPI-03: Exposure of Sensitive API Tokens", "OWASP FAPI > FAPI-03", "Hardcoded credentials, database connection strings, or JWT signing secrets in source code repositories expose financial systems to immediate compromise."),
                ]),
                ("NIST_SP_800_53_Control_Baselines.pdf", "pdf", "Rev 5", nist_grp, True, "NIST", ["nist", "access-control", "government"], [
                    ("AC-3: Access Enforcement Mechanisms", "NIST SP 800-53 > AC-3", "The information system enforces approved authorizations for logical access to information and system resources in accordance with applicable access control policies."),
                    ("SC-13: Cryptographic Protection", "NIST SP 800-53 > SC-13", "The system implements cryptographic modules in accordance with applicable federal laws, directives, and policies using FIPS-validated cryptography."),
                ]),
            ]
            for fname, dtype, ver, grp, is_lat, auth, tags, chunks_list in docs:
                res = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == fname))
                doc = res.scalars().first()
                if not doc:
                    doc = KnowledgeDocument(
                        filename=fname, document_type=dtype, version=ver,
                        document_group_id=grp, is_latest=is_lat,
                        content_hash=str(uuid.uuid4()).replace("-", "")[:32],
                        author=auth, tags=tags, status="indexed",
                        health_status="active" if is_lat else "stale",
                        freshness_decay_factor=1.0 if is_lat else 0.5,
                        file_path=f"data/knowledge_base/{fname}",
                        file_size_bytes=sum(len(c[2]) for c in chunks_list),
                        chunk_count=len(chunks_list), page_count=len(chunks_list),
                        uploaded_by_id=admin.id
                    )
                    session.add(doc)
                    await session.flush()
                else:
                    doc.uploaded_by_id = admin.id

                # Chunks
                res_c = await session.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
                if not res_c.scalars().all():
                    for idx, (head, spath, content) in enumerate(chunks_list):
                        dim = settings.knowledge_embedding_dim
                        vec = [((idx * 19 + i * 37) % 100) / 100.0 for i in range(dim)]
                        norm = sum(x*x for x in vec)**0.5 or 1.0
                        chunk = KnowledgeChunk(
                            document_id=doc.id, chunk_index=idx, content=content,
                            heading=head, section_path=spath, page_number=idx + 1,
                            token_count=len(content.split()), embedding=[x/norm for x in vec]
                        )
                        session.add(chunk)
            await session.commit()
            print("Step 3 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 3 FAILED:", e)
            traceback.print_exc()

        # Step 4: Knowledge Graph
        try:
            print("Running Step 4: Knowledge Graph...")
            res_pci = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == "PCI_DSS_v4.0_Banking_Security_Standard.pdf"))
            pci_d = res_pci.scalars().first()
            res_owasp = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == "OWASP_Financial_API_Security_Guide.md"))
            owasp_d = res_owasp.scalars().first()
            res_nist = await session.execute(select(KnowledgeDocument).where(KnowledgeDocument.filename == "NIST_SP_800_53_Control_Baselines.pdf"))
            nist_d = res_nist.scalars().first()

            entities_data = [
                (pci_d.id, "PCI-DSS v4.0 Standard", "STANDARD", 8),
                (pci_d.id, "Requirement 3.4 (Cardholder Cryptography)", "RULE", 6),
                (pci_d.id, "Requirement 6.4.1 (AST Injection Prevention)", "RULE", 5),
                (pci_d.id, "Requirement 7.1 (RBAC & MFA)", "RULE", 7),
                (pci_d.id, "Requirement 8.3 (MFA Enforcement)", "RULE", 4),
                (pci_d.id, "AES-256-GCM / RSA-4096", "ALGORITHM", 6),
                (pci_d.id, "Multi-Factor Authentication (MFA)", "CONTROL", 9),
                (owasp_d.id, "OWASP FAPI Framework", "FRAMEWORK", 10),
                (owasp_d.id, "FAPI-01 (BOLA)", "VULNERABILITY", 7),
                (owasp_d.id, "FAPI-02 (Unprotected Transactions)", "VULNERABILITY", 8),
                (owasp_d.id, "FAPI-03 (Token Exposure)", "VULNERABILITY", 5),
                (owasp_d.id, "Resource Ownership Check", "CONTROL", 6),
                (owasp_d.id, "RequireRole('admin')", "CONTROL", 9),
                (nist_d.id, "NIST SP 800-53 Standard", "STANDARD", 6),
                (nist_d.id, "AC-3 Access Enforcement", "RULE", 5),
                (nist_d.id, "SC-13 Cryptographic Protection", "RULE", 5),
            ]
            ent_lookup = {}
            for did, ename, etype, mcount in entities_data:
                res_e = await session.execute(select(KnowledgeEntity).where(KnowledgeEntity.entity_name == ename))
                ent = res_e.scalars().first()
                if not ent:
                    ent = KnowledgeEntity(document_id=did, entity_name=ename, entity_type=etype, mention_count=mcount)
                    session.add(ent)
                    await session.flush()
                ent_lookup[ename] = ent

            relations_data = [
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
            for src, tgt, rtype in relations_data:
                s_ent, t_ent = ent_lookup.get(src), ent_lookup.get(tgt)
                if s_ent and t_ent:
                    res_r = await session.execute(select(KnowledgeRelation).where(
                        KnowledgeRelation.source_entity_id == s_ent.id,
                        KnowledgeRelation.target_entity_id == t_ent.id,
                        KnowledgeRelation.relation_type == rtype
                    ))
                    if not res_r.scalars().first():
                        session.add(KnowledgeRelation(source_entity_id=s_ent.id, target_entity_id=t_ent.id, relation_type=rtype))
            await session.commit()
            print("Step 4 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 4 FAILED:", e)
            traceback.print_exc()

        # Step 5: FAQ Rules
        try:
            print("Running Step 5: FAQ Rules...")
            res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
            admin = res.scalars().first()
            faqs = [
                ("what is aekof", "AEKOF (Adaptive Enterprise Knowledge Operating Framework) is the core architecture powering NOVA, featuring dynamic routing, pairwise NLI consensus, and 8-dimensional Platt confidence calibration.", True, False),
                ("how to reset password", "To reset your password, navigate to Account Settings > Security or use the corporate SSO provider's self-service recovery options.", True, False),
                ("what is graphrag", "GraphRAG extracts structured entities and semantic relations into a knowledge graph to answer multi-hop security queries that require cross-repository context.", True, False),
                ("how does pairwise nli consensus work", "NOVA builds an N x N cross-encoder matrix across retrieved evidence to calculate consensus agreement C_agreement = (N_supports - N_contradicts) / N_total, blocking hallucinations when contradiction occurs.", True, False),
                ("what is platt trust calibration", "Platt trust calibration maps an 8-dimensional evidence feature vector via logistic sigmoid P(Correct|C) = 1 / (1 + e^-z) into a calibrated trust probability subordinated to hard safety gates.", True, False),
                ("how to rotate jwt signing secrets", "Candidate Auto-Generated: Rotate JWT secrets by deploying dual-key validation: sign new tokens with key_v2 while continuing to verify older tokens with key_v1 until TTL expiry.", False, True),
                ("can developers bypass role authorization in staging", "Candidate Auto-Generated: No, staging environments enforce strict RBAC policies parity with production. Developer bypass flags are blocked by CI/CD security gates.", False, True),
                ("how to configure database connection pooling with pgvector", "Candidate Auto-Generated: Configure SQLAlchemy async_sessionmaker with pool_size=20, max_overflow=10, and ensure HNSW vector indexes use vector_cosine_ops.", False, True),
            ]
            for kw, resp, active, draft in faqs:
                res_f = await session.execute(select(FAQRule).where(FAQRule.keyword == kw))
                f = res_f.scalars().first()
                if not f:
                    session.add(FAQRule(keyword=kw, response=resp, is_active=active, is_draft=draft, created_by_id=admin.id))
                else:
                    f.is_active = active
                    f.is_draft = draft
            await session.commit()
            print("Step 5 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 5 FAILED:", e)
            traceback.print_exc()

        # Step 6: Assistant Sessions
        try:
            print("Running Step 6: Assistant Sessions...")
            res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
            admin = res.scalars().first()
            res_sess = await session.execute(select(ChatSession).where(ChatSession.user_id == admin.id))
            if not res_sess.scalars().all():
                s1 = ChatSession(
                    user_id=admin.id,
                    title="Banking API Privilege Escalation Forensic Audit",
                    context_summary="Comprehensive analysis of POST /admin/transactions and RequireRole('admin') authorization boundary.",
                    active_entities={"asset": "POST /admin/transactions", "cwe": "CWE-285", "property": "AUTHORIZATION"}
                )
                session.add(s1)
                await session.flush()

                m1 = ChatMessage(
                    session_id=s1.id, role="user",
                    content="Is the POST /admin/transactions endpoint safe and protected against unauthorized access according to our security architecture?",
                    citations=[], confidence_vector={}, reasoning_trace={}, consensus_matrix={}
                )
                m2 = ChatMessage(
                    session_id=s1.id, role="assistant",
                    content="AST analysis verified RequireRole('admin') is active on POST /admin/transactions with 95.2% confidence.",
                    citations=[{"source_id": "sec-intel-001", "title": "Verified Risk Assessment", "file_path": "data/demo_repo/admin_transactions.py:42"}],
                    confidence_vector={"retrieval_confidence": 0.94},
                    calibrated_trust_score=0.952,
                    reasoning_trace={"policy_gate": "GENERATE"},
                    consensus_matrix={"supports_count": 1, "c_agreement": 0.96}
                )
                session.add_all([m1, m2])
            await session.commit()
            print("Step 6 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 6 FAILED:", e)
            traceback.print_exc()

        # Step 7: Audit Logs, Telemetry & Feedback
        try:
            print("Running Step 7: Telemetry & Feedback...")
            res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
            admin = res.scalars().first()
            now = datetime.datetime.now(datetime.timezone.utc)
            audits = [
                ("auth.login", "user", str(admin.id), "success", {"auth_method": "password"}),
                ("knowledge.document.upload", "knowledge_document", "PCI_DSS_v4.0_Banking_Security_Standard.pdf", "success", {"chunks_extracted": 3}),
                ("security.analysis.run", "security_pipeline", "data/demo_repo", "success", {"posture_score": 95.0, "rating": "STRONG"}),
                ("faq.rule.promote", "faq_rule", "what is aekof", "success", {"promoted_to": "active_stage_0"}),
                ("benchmark.probe.executed", "rag_benchmark", "probe_run_01", "success", {"latency_ms": 780, "precision": 0.886}),
                ("remediation.patch.verify", "security_assessment", "sec-intel-001", "success", {"status_after": "VERIFIED_FIXED"}),
            ]
            for act, rtype, rid, stat, det in audits:
                session.add(AuditLog(user_id=admin.id, user_email=admin.email, action=act, resource_type=rtype, resource_id=rid, status=stat, ip_address="127.0.0.1", user_agent="Mozilla/5.0", details=det, created_at=now - datetime.timedelta(minutes=30)))

            s_logs = [
                ("assistant", "Is POST /admin/transactions protected by role checks?", 4, 0.952, False, 32.4),
                ("knowledge_base", "PCI-DSS Requirement 3.4 encryption standards for cardholder PAN", 3, 0.981, False, 18.6),
                ("security_intelligence", "AST observations for authentication boundary crossing", 5, 0.940, False, 24.1),
                ("executive_intelligence", "Overall enterprise security posture trajectory deltas", 3, 0.995, False, 12.8),
                ("knowledge_gap", "How to configure zero trust mutual TLS authentication", 0, 0.0, True, 45.2),
            ]
            for feat, q, rc, ts, fb, lat in s_logs:
                session.add(SearchAnalyticsLog(feature=feat, query=q, result_count=rc, top_score=ts, fallback_triggered=fb, latency_ms=lat, user_id=admin.id))

            fbs = [
                ("assistant", "ref-chat-msg-01", 5, "Accurately pinpointed the missing RequireRole decorator in code.", admin.id),
                ("assistant", "ref-chat-msg-02", 5, "Clear explanation of PCI-DSS encryption requirements.", admin.id),
            ]
            for feat, ref, rat, comm, uid in fbs:
                session.add(Feedback(feature=feat, reference_id=ref, rating=rat, comment=comm, user_id=uid))
            await session.commit()
            print("Step 7 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 7 FAILED:", e)
            traceback.print_exc()

        # Step 8: Security Intelligence
        try:
            print("Running Step 8: Security Intelligence...")
            res_a = await session.execute(select(SecurityIntelAsset))
            if len(res_a.scalars().all()) < 5:
                a1 = SecurityIntelAsset(asset_name="POST /admin/transactions", asset_type="ENDPOINT", criticality="HIGH", owner="Payments Engineering Team", location="data/demo_repo/admin_transactions.py:42", attributes={"protocol": "HTTPS", "framework": "FastAPI", "category": "FINANCIAL_API"})
                a2 = SecurityIntelAsset(asset_name="TransactionController", asset_type="SERVICE", criticality="CRITICAL", owner="Core Banking Architecture", location="data/demo_repo/transaction_controller.py:12", attributes={"language": "Python 3.10", "type": "Microservice"})
                a3 = SecurityIntelAsset(asset_name="AuthService", asset_type="APPLICATION", criticality="CRITICAL", owner="IAM Security Team", location="data/demo_repo/auth_service.py:1", attributes={"auth_standard": "OAuth2 / JWT", "mfa": True})
                a4 = SecurityIntelAsset(asset_name="DATABASE: banking_core_db", asset_type="DATABASE", criticality="CRITICAL", owner="DBA Infrastructure Team", location="postgresql://core_db:5432/banking", attributes={"engine": "PostgreSQL 15", "encryption_at_rest": "AES-256"})
                a5 = SecurityIntelAsset(asset_name="POST /transfers/wire", asset_type="ENDPOINT", criticality="CRITICAL", owner="Wire Operations", location="data/demo_repo/wire_transfer.py:88", attributes={"limit_check": True, "dual_control": True})
                session.add_all([a1, a2, a3, a4, a5])
                await session.flush()

                obs1 = SecurityIntelObservation(asset_id=a1.id, observation_type="PUBLIC_ENDPOINT", location="data/demo_repo/admin_transactions.py:42", evidence_span="@router.post('/admin/transactions')", confidence=0.98, provenance="ast_decorator_visitor", attributes={"route": "/admin/transactions", "method": "POST"})
                obs2 = SecurityIntelObservation(asset_id=a1.id, observation_type="AUTHORIZATION_BOUNDARY", location="data/demo_repo/admin_transactions.py:44", evidence_span="def process_admin_transaction(tx_payload: TransactionSchema):", confidence=0.95, provenance="ast_arg_visitor", attributes={"missing_role_decorator": True})
                obs3 = SecurityIntelObservation(asset_id=a1.id, observation_type="DATABASE_ACCESS", location="data/demo_repo/admin_transactions.py:65", evidence_span="await db.execute(insert(TransactionModel)...)", confidence=0.92, provenance="ast_call_visitor", attributes={"target_table": "transactions"})

                c1 = SecurityIntelControl(asset_id=a1.id, control_type="AUTHORIZATION", scope="POST /admin/transactions", state="PRESENT", evidence="dependencies=[Depends(RequireRole('admin'))]", confidence=0.96)
                c2 = SecurityIntelControl(asset_id=a1.id, control_type="AUTHENTICATION", scope="POST /admin/transactions", state="PRESENT", evidence="Depends(get_current_active_user)", confidence=0.98)
                c3 = SecurityIntelControl(asset_id=a1.id, control_type="INPUT_VALIDATION", scope="POST /admin/transactions", state="PRESENT", evidence="tx_payload: TransactionSchema", confidence=0.95)

                sc1 = SecurityIntelRiskScenario(asset_id=a1.id, scenario_type="PRIVILEGE_ESCALATION_RISK", trust_boundary_crossed="INTERNET -> APPLICATION_CORE", attack_path={"steps": ["1. User authenticates", "2. Dispatches POST /admin/transactions", "3. Transaction processed without admin role check"]}, exposure_signal="PUBLIC_ENDPOINT_WITH_ELEVATED_PRIVILEGE", control_status="AUTHORIZATION_PRESENT_VERIFIED", potential_impact="Unauthorized balance adjustment or privilege escalation across banking accounts.", verification_state="VERIFIED")

                ass1 = SecurityIntelAssessment(asset_id=a1.id, risk_type="PRIVILEGE_ESCALATION_RISK", severity="HIGH", confidence=0.95, affected_scope="data/demo_repo/admin_transactions.py:42-70", evidence_chain=[{"fact": "POST endpoint discovered in AST", "line": 42}, {"fact": "RequireRole('admin') attached and verified", "line": 44}], attack_path=["Client sends unprivileged HTTP request", "Gateway evaluates role dependency", "Access granted to verified admin"], controls_evaluated=[{"type": "AUTHORIZATION", "state": "PRESENT", "confidence": 0.96}], reasoning="The administrative endpoint POST /admin/transactions was verified fixed with RequireRole('admin').", remediation="Apply @router.post('/admin/transactions', dependencies=[Depends(RequireRole('admin'))])", status="VERIFIED_FIXED", commit_hash="f68521e")

                session.add_all([obs1, obs2, obs3, c1, c2, c3, sc1, ass1])
            await session.commit()
            print("Step 8 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 8 FAILED:", e)
            traceback.print_exc()

        # Step 9: Posture Snapshots
        try:
            print("Running Step 9: Posture Snapshots...")
            res_p = await session.execute(select(SecurityIntelPostureSnapshot))
            if not res_p.scalars().all():
                now = datetime.datetime.now(datetime.timezone.utc)
                posture_records = [
                    (now - datetime.timedelta(days=14), "a1b2c3d", 62.5, "NEEDS_ATTENTION", 50.0, 5, 3, 1, 2, 0, None, "FIRST_RUN", {"new_risks_count": 3, "resolved_risks_count": 0, "persistent_risks_count": 0}),
                    (now - datetime.timedelta(days=7), "b2c3d4e", 75.0, "MODERATE", 75.0, 5, 2, 0, 2, 1, 12.5, "IMPROVED", {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 2}),
                    (now - datetime.timedelta(days=2), "c3d4e5f", 85.0, "STRONG", 85.0, 5, 1, 0, 1, 2, 10.0, "IMPROVED", {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 1}),
                    (now, "f68521e", 95.0, "STRONG", 100.0, 5, 0, 0, 0, 3, 10.0, "IMPROVED", {"new_risks_count": 0, "resolved_risks_count": 1, "persistent_risks_count": 0}),
                ]
                for c_at, comm, score, rating, cov, t_assets, unres, crit, high, fixed, delta, trend, r_evo in posture_records:
                    session.add(SecurityIntelPostureSnapshot(
                        created_at=c_at, analysis_run_id=str(uuid.uuid4()), target_scope="data/demo_repo",
                        commit_hash=comm, posture_score=score, posture_rating=rating,
                        control_coverage_pct=cov, total_assets_count=t_assets,
                        unresolved_risks_count=unres, critical_risks_count=crit,
                        high_risks_count=high, medium_risks_count=0, low_risks_count=0,
                        verified_fixed_count=fixed, delta_score=delta, trend_direction=trend,
                        risk_evolution_summary=r_evo
                    ))
            await session.commit()
            print("Step 9 PASSED")
        except Exception as e:
            await session.rollback()
            print("Step 9 FAILED:", e)
            traceback.print_exc()

    await engine.dispose()
    print("FINISHED ALL STEPS")

if __name__ == "__main__":
    asyncio.run(main())
