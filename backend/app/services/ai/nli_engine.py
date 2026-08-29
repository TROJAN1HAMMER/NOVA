"""
NOVA — NLI-Based Pairwise Evidence Relationship Engine
Evaluates structural inference (SUPPORTS, CONTRADICTS, RELATED, UNRELATED)
between heterogeneous evidence items (Knowledge Chunks, Security Findings, FAQ Axioms).
Combines cross-encoder neural inference with metadata validation, version extraction,
CVE/CWE scope matching, and structured security property conflict analysis.
"""

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog

from app.services.ai import cache as response_cache
from app.services.assistant import rerank_manager

logger = structlog.get_logger(__name__)

_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

CVE_REGEX = re.compile(r'CVE-\d{4}-\d{4,7}', re.IGNORECASE)
CWE_REGEX = re.compile(r'CWE-\d{1,4}', re.IGNORECASE)
VERSION_REGEX = re.compile(r'\bv?(\d+\.\d+(?:\.\d+)?)\b', re.IGNORECASE)


@dataclass
class SecurityProperty:
    property_type: str  # "AUTHENTICATION" | "AUTHORIZATION" | "ENCRYPTION" | "INPUT_VALIDATION" | "ACCESS_CONTROL" | "SECRET_MANAGEMENT" | "CSRF_SESSION" | "MEMORY_COMMAND"
    state: str          # "VULNERABLE" | "SAFE"
    scope: str          # file path, component, or endpoint string
    confidence: float
    evidence_span: str


@dataclass
class EvidenceRelationship:
    source_evidence_id: str
    target_evidence_id: str
    relationship: str  # "SUPPORTS" | "CONTRADICTS" | "RELATED" | "UNRELATED"
    confidence: float
    nli_label: str  # "ENTAILMENT" | "CONTRADICTION" | "NEUTRAL"
    nli_score: float
    scope_match: bool
    property_match: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NLIEngine:
    """NLI Relationship Classifier combining neural cross-encoder scores with metadata & security property rules."""

    _STATUS_KEYWORDS_VULN = {
        "vulnerable", "vulnerability", "vulnerabilities", "affected", "unpatched",
        "exploitable", "flaw", "flaws", "exposure", "exposed", "critical flaw",
        "zero-day", "leak", "leaks", "injection", "xss", "csrf", "idor", "ssrf",
        "overflow", "bypass", "bypassed", "insecure", "unquoted", "missing", "hardcoded",
        "open redirect", "unencrypted", "plaintext", "broken access control", "race condition",
        "bug", "present", "allows", "unsanitized", "arbitrary file access", "does not verify"
    }

    _STATUS_KEYWORDS_SAFE_ASSERT = {
        "not vulnerable", "secure", "unaffected", "safe", "non-vulnerable",
        "clean", "immune", "is safe", "is patched", "has zero vulnerabilities",
        "restricts redirect", "enclosed in double quotes", "is secure",
        "restricts all routes", "no memory leaks", "strictly from environment",
        "requires admin", "safe from command injection", "validates csrf",
        "mitigated via", "fixed flaw", "row locking", "restricts traffic",
        "sanitizes", "validates", "encrypts", "hashes", "vault", "restricts", "enforced", "remediated"
    }

    _DOMAIN_KEYWORDS = {
        "sql", "xss", "cwe", "cve", "auth", "jwt", "database", "postgres", "redis",
        "docker", "fastapi", "python", "security", "config", "http", "https", "token",
        "user", "admin", "password", "crypto", "hash", "session", "policy", "leave",
        "report", "scan", "finding", "vulnerability", "patch", "remediation", "alembic",
        "sqlalchemy", "pytest", "eslint", "prettier", "typescript", "react", "gunicorn", "uvicorn",
        "tailwindcss", "lucide", "git", "commit", "pull request", "tanstack", "queryclient",
        "pgvector", "hnsw", "structlog", "cors", "pytest-cov", "tsconfig"
    }

    # Semantic Property Extraction Patterns
    _PROPERTY_PATTERNS = [
        ("AUTHENTICATION", "VULNERABLE", re.compile(r'(?:without|missing|no|lacks?|does\s+not)\s+(?:verify\s+)?(?:authentication|certificates)|unauthenticated|anonymous\s+access', re.I)),
        ("AUTHENTICATION", "SAFE", re.compile(r'requires?\s+(?:admin\s+)?(?:http\s+basic\s+)?auth|authenticated\s+access|authenticates?|validates?\s+(?:tls\s+)?certificates', re.I)),

        ("AUTHORIZATION", "VULNERABLE", re.compile(r'database\s+bypass|allows?\s+(?:full\s+database\s+)?bypass|authorization\s+(?:can\s+be\s+)?bypassed|broken\s+access\s+control|unrestricted\s+access|arbitrary\s+file\s+access', re.I)),
        ("AUTHORIZATION", "SAFE", re.compile(r'validates?\s+(?:user\s+)?authorization|enforces?\s+(?:explicit\s+)?ownership|restricts?\s+(?:all\s+)?routes|authorization\s+is\s+enforced|restricts?\s+file\s+access', re.I)),

        ("ENCRYPTION", "VULNERABLE", re.compile(r'unencrypted|in\s+plaintext|plaintext\s+credentials|http\s+traffic\s+allowed|weak\s+tls', re.I)),
        ("ENCRYPTION", "SAFE", re.compile(r'forces?\s+https|encrypts?\s+credentials|ssl\s+configuration|disables?\s+http|tls\s+1\.3|salted\s+password\s+hashes', re.I)),

        ("INPUT_VALIDATION", "VULNERABLE", re.compile(r'unsanitized\s+input|accepts?\s+unsanitized|raw\s+query|autoescaping\s+disabled', re.I)),
        ("INPUT_VALIDATION", "SAFE", re.compile(r'sanitizes?\s+(?:all\s+)?(?:user\s+)?input|parameterized\s+queries|html\s+escap(?:ing|ed)|autoescape\s+enabled', re.I)),

        ("SECRET_MANAGEMENT", "VULNERABLE", re.compile(r'hardcoded|embedded\s+in\s+source|exposed\s+(?:aws\s+)?secret|secret\s+key\s+exposed', re.I)),
        ("SECRET_MANAGEMENT", "SAFE", re.compile(r'environment\s+variables|secrets?\s+manager|secure\s+vault|loaded\s+from\s+(?:secure\s+)?vault', re.I)),

        ("CSRF_SESSION", "VULNERABLE", re.compile(r'missing\s+(?:anti-)?csrf|fails?\s+csrf|session\s+fixation|missing\s+rate\s+limiting', re.I)),
        ("CSRF_SESSION", "SAFE", re.compile(r'validates?\s+csrf|samesite=strict|httponly|rate\s+limiter\s+decorator', re.I)),

        ("MEMORY_COMMAND", "VULNERABLE", re.compile(r'memory\s+leak|command\s+injection|buffer\040overflow|unquoted\s+windows\s+search\s+path', re.I)),
        ("MEMORY_COMMAND", "SAFE", re.compile(r'no\s+memory\s+leaks|shell=false|enclosed\042?\s+in\s+double\s+quotes|frees?\s+all\s+buffers', re.I)),
    ]

    def _extract_cves(self, text: str) -> Set[str]:
        return {cve.upper() for cve in CVE_REGEX.findall(text)}

    def _extract_cwes(self, text: str) -> Set[str]:
        return {cwe.upper() for cwe in CWE_REGEX.findall(text)}

    def _extract_versions(self, text: str) -> List[str]:
        return VERSION_REGEX.findall(text)

    def _extract_security_properties(self, text: str) -> List[SecurityProperty]:
        properties = []
        for prop_type, state, pattern in self._PROPERTY_PATTERNS:
            match = pattern.search(text)
            if match:
                properties.append(SecurityProperty(
                    property_type=prop_type,
                    state=state,
                    scope="",
                    confidence=0.90,
                    evidence_span=match.group(0),
                ))
        return properties

    def _cache_payload(self, text_a: str, text_b: str) -> dict:
        return {
            "model": "nli_cross_encoder_v11",
            "hash_a": hashlib.sha256(text_a.encode()).hexdigest()[:16],
            "hash_b": hashlib.sha256(text_b.encode()).hexdigest()[:16],
        }

    def analyze_pair(self, item_a: Dict[str, Any], item_b: Dict[str, Any]) -> EvidenceRelationship:
        """Evaluates pairwise NLI relationship with version, scope, and security property reasoning."""
        id_a = str(item_a.get("source_id") or item_a.get("document_id") or "item_a")
        id_b = str(item_b.get("source_id") or item_b.get("document_id") or "item_b")

        excerpt_a = str(item_a.get("excerpt") or item_a.get("content") or item_a.get("title") or "")
        excerpt_b = str(item_b.get("excerpt") or item_b.get("content") or item_b.get("title") or "")

        if not excerpt_a or not excerpt_b or id_a == id_b:
            return EvidenceRelationship(
                source_evidence_id=id_a,
                target_evidence_id=id_b,
                relationship="UNRELATED",
                confidence=1.0 if id_a == id_b else 0.0,
                nli_label="NEUTRAL",
                nli_score=0.0,
                scope_match=False,
                property_match=False,
                reason="Identical evidence item or missing text excerpt.",
            )

        # 1. Check Cache
        cache_key = self._cache_payload(excerpt_a, excerpt_b)
        cached = response_cache.get_cached("nli_pair", cache_key)
        if cached:
            return EvidenceRelationship(
                source_evidence_id=id_a,
                target_evidence_id=id_b,
                relationship=cached["relationship"],
                confidence=cached["confidence"],
                nli_label=cached["nli_label"],
                nli_score=cached["nli_score"],
                scope_match=cached.get("scope_match", False),
                property_match=cached.get("property_match", False),
                reason=cached["reason"],
            )

        # 2. Scope & Metadata Extraction
        type_a = item_a.get("source_type", "knowledge_doc")
        type_b = item_b.get("source_type", "knowledge_doc")

        cwe_a = (str(item_a.get("cwe_id") or "").upper() or str(self._extract_cwes(excerpt_a)))
        cwe_b = (str(item_b.get("cwe_id") or "").upper() or str(self._extract_cwes(excerpt_b)))

        cve_set_a = self._extract_cves(excerpt_a)
        cve_set_b = self._extract_cves(excerpt_b)
        cve_a = str(item_a.get("cve") or "").upper()
        cve_b = str(item_b.get("cve") or "").upper()
        if cve_a:
            cve_set_a.add(cve_a)
        if cve_b:
            cve_set_b.add(cve_b)

        file_a = str(item_a.get("file_path") or "").lower()
        file_b = str(item_b.get("file_path") or "").lower()

        # Extract file paths from text
        extracted_files_a = set(re.findall(r'\b[a-zA-Z0-9_\-/]+\.(?:py|js|ts|cpp|cs|xml|yml|yaml|pdf|dockerfile)\b', excerpt_a.lower()))
        extracted_files_b = set(re.findall(r'\b[a-zA-Z0-9_\-/]+\.(?:py|js|ts|cpp|cs|xml|yml|yaml|pdf|dockerfile)\b', excerpt_b.lower()))

        same_cve = bool(cve_set_a and cve_set_b and (cve_set_a & cve_set_b))
        distinct_cve = bool(cve_set_a and cve_set_b and not (cve_set_a & cve_set_b))
        same_cwe = bool(cwe_a and cwe_b and ("CWE" in cwe_a) and ("CWE" in cwe_b) and (cwe_a == cwe_b))
        same_file = bool((file_a and file_b and file_a == file_b) or (extracted_files_a and extracted_files_b and (extracted_files_a & extracted_files_b)))

        # Lexical & Neural Cross-Encoder
        words_a = set(excerpt_a.lower().split())
        words_b = set(excerpt_b.lower().split())
        lex_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)

        try:
            scores = rerank_manager.rerank(excerpt_a, [excerpt_b])
            raw_score = scores[0] if scores else 0.0
            nli_score = rerank_manager.normalize_confidence(raw_score)
        except Exception as exc:
            logger.warning("nli_engine.cross_encoder_failed", error=str(exc))
            nli_score = lex_overlap

        # 3. Security Property Extraction
        props_a = self._extract_security_properties(excerpt_a)
        props_b = self._extract_security_properties(excerpt_b)

        property_types_a = {p.property_type: p.state for p in props_a}
        property_types_b = {p.property_type: p.state for p in props_b}

        common_props = set(property_types_a.keys()) & set(property_types_b.keys())
        has_property_conflict = any(property_types_a[pt] != property_types_b[pt] for pt in common_props)
        property_match = len(common_props) > 0

        # Scope Match Flag
        scope_match = same_cve or same_file or same_cwe

        # 4. Remediation Guidance vs Assertion Check
        lower_b = excerpt_b.lower()
        is_remediation_b = (
            "to fix" in lower_b or "use parameterized" in lower_b or
            "to resolve" in lower_b or "how to fix" in lower_b or "how to remediate" in lower_b or
            "upgrade to" in lower_b or "remediation guide" in lower_b or "remediation path" in lower_b or
            "to remediate" in lower_b or "apply " in lower_b or "add " in lower_b or
            "load secret" in lower_b or "validate file path" in lower_b or "escaping" in lower_b
        )

        lower_a = excerpt_a.lower()
        versions_a = self._extract_versions(excerpt_a)
        versions_b = self._extract_versions(excerpt_b)

        has_vuln_a = any(k in lower_a for k in self._STATUS_KEYWORDS_VULN)
        has_safe_assert_a = any(k in lower_a for k in self._STATUS_KEYWORDS_SAFE_ASSERT)
        has_vuln_b = any(k in lower_b for k in self._STATUS_KEYWORDS_VULN)
        has_safe_assert_b = any(k in lower_b for k in self._STATUS_KEYWORDS_SAFE_ASSERT)

        is_opposite_status = (
            ((has_vuln_a and has_safe_assert_b) or (has_safe_assert_a and has_vuln_b) or has_property_conflict)
            and not is_remediation_b
        )

        different_versions = False
        same_version = False
        if versions_a and versions_b:
            if set(versions_a) == set(versions_b):
                same_version = True
            else:
                different_versions = True

        shared_domain_words = (words_a & words_b) & self._DOMAIN_KEYWORDS
        has_domain_overlap = len(shared_domain_words) > 0

        # =====================================================================
        # 5. DECISION HIERARCHY
        # =====================================================================

        # RULE 1: Distinct CVEs -> Not contradictory
        if distinct_cve:
            if has_domain_overlap or lex_overlap > 0.04:
                nli_label = "NEUTRAL"
                relationship = "RELATED"
                confidence = 0.85
                reason = f"Evidence items refer to distinct CVE identifiers ({list(cve_set_a)} vs {list(cve_set_b)})."
            else:
                nli_label = "NEUTRAL"
                relationship = "UNRELATED"
                confidence = 0.90
                reason = "Evidence items cover distinct security vulnerabilities."

        # RULE 2: Version Upgrade Path -> RELATED or SUPPORTS
        elif different_versions and (has_vuln_a or has_vuln_b):
            nli_label = "NEUTRAL"
            relationship = "RELATED"
            confidence = 0.88
            reason = f"Evidence describes version upgrade or remediation path between versions ({versions_a} vs {versions_b})."

        # RULE 3: Same Scope / Property Conflict + Opposing Status -> CONTRADICTS
        elif is_opposite_status and (scope_match or property_match or same_version or lex_overlap > 0.04):
            nli_label = "CONTRADICTION"
            relationship = "CONTRADICTS"
            confidence = round(max(nli_score, 0.91), 4)
            if property_match and has_property_conflict:
                reason = f"Same security property ({list(common_props)[0]}) exhibits opposing state assertions ({property_types_a[list(common_props)[0]]} vs {property_types_b[list(common_props)[0]]})."
            elif same_version:
                reason = f"Same component/file version ({versions_a}) exhibits opposite vulnerability status assertions."
            elif same_cve:
                reason = f"Same CVE identifier ({list(cve_set_a)}) exhibits opposite status assertions."
            elif same_file:
                reason = f"Same source file ({file_a or list(extracted_files_a)}) exhibits conflicting security assertions."
            else:
                reason = "Opposite vulnerability status assertions detected in shared scope."

        # RULE 4: Remediation Guidance or Shared CWE/File -> SUPPORTS
        elif is_remediation_b or same_cwe or same_file or same_cve or (type_a != type_b and lex_overlap > 0.04):
            nli_label = "ENTAILMENT"
            relationship = "SUPPORTS"
            confidence = round(max(nli_score, 0.85), 4)
            reason = "Evidence items reinforce remediation guidance or document context."

        # RULE 5: Domain Overlap -> RELATED
        elif has_domain_overlap or lex_overlap > 0.03:
            nli_label = "NEUTRAL"
            relationship = "RELATED"
            confidence = round(nli_score, 4)
            reason = "Evidence items share domain context but do not explicitly entail or contradict."

        # RULE 6: Default UNRELATED
        else:
            nli_label = "NEUTRAL"
            relationship = "UNRELATED"
            confidence = round(1.0 - nli_score, 4)
            reason = "Evidence items cover distinct topics without semantic alignment."

        rel_obj = EvidenceRelationship(
            source_evidence_id=id_a,
            target_evidence_id=id_b,
            relationship=relationship,
            confidence=confidence,
            nli_label=nli_label,
            nli_score=round(nli_score, 4),
            scope_match=scope_match,
            property_match=property_match,
            reason=reason,
        )

        response_cache.set_cached("nli_pair", cache_key, rel_obj.to_dict(), ttl_seconds=_CACHE_TTL_SECONDS)
        return rel_obj

    def analyze_evidence_set(
        self, items: List[Dict[str, Any]], max_pairs: int = 10
    ) -> List[EvidenceRelationship]:
        """Runs bounded pairwise analysis across top evidence items."""
        if not items or len(items) < 2:
            return []

        top_candidates = items[:5]
        pairs = []

        for i in range(len(top_candidates)):
            for j in range(i + 1, len(top_candidates)):
                item_i = top_candidates[i]
                item_j = top_candidates[j]
                is_cross = item_i.get("source_type") != item_j.get("source_type")
                pairs.append((item_i, item_j, is_cross))

        pairs.sort(key=lambda x: 0 if x[2] else 1)

        relationships = []
        for item_a, item_b, _ in pairs[:max_pairs]:
            rel = self.analyze_pair(item_a, item_b)
            relationships.append(rel)

        return relationships


nli_engine = NLIEngine()
