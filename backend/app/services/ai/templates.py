"""
NOVA — Deterministic AI Fallback / Generic-Context Templates

Two independent consumers rely on this same per-category content:
  - `ai_engine.py` uses it as the deterministic fallback insight when no
    provider is configured or every provider call fails.
  - `sanitizer.py` uses the (already generic, non-raw) `explanation` text
    as the "generic_description" sent to providers *instead of* a
    finding's raw scanner-produced title/description — see sanitizer.py's
    module docstring for why raw scan text is never forwarded.

Living in its own module (rather than inside ai_engine.py) avoids a
circular import between those two.
"""

TEMPLATE_INSIGHTS: dict[str, dict] = {
    "hardcoded_secret": {
        "explanation": (
            "Hardcoded secrets embed sensitive credentials (API keys, passwords, tokens) "
            "directly in source code. When code is shared via version control or decompiled, "
            "attackers gain immediate access to these credentials."
        ),
        "business_impact": (
            "Exposed credentials in banking systems can lead to unauthorized account access, "
            "fraudulent transactions, and complete system compromise. "
            "RBI guidelines mandate immediate incident reporting and can result in operational restrictions."
        ),
        "remediation": (
            "1. Remove the hardcoded secret from source code immediately. "
            "2. Rotate/revoke the exposed credential. "
            "3. Store secrets in environment variables or a secrets manager (HashiCorp Vault, AWS Secrets Manager). "
            "4. Implement pre-commit hooks to scan for secrets before code is committed. "
            "5. Audit git history for any previously committed secrets."
        ),
    },
    "sql_injection": {
        "explanation": (
            "SQL Injection occurs when user-controlled input is inserted directly into database queries. "
            "Attackers can manipulate the query to read, modify, or delete data, "
            "and in some cases execute commands on the database server."
        ),
        "business_impact": (
            "In banking systems, SQL injection can expose complete customer account databases, "
            "enable fraudulent fund transfers, and compromise transaction records. "
            "This constitutes a reportable data breach under RBI and DPDP Act, "
            "with potential fines and license implications."
        ),
        "remediation": (
            "1. Replace string concatenation with parameterized queries or prepared statements. "
            "2. Use ORM frameworks (SQLAlchemy, Hibernate) which provide automatic parameterization. "
            "3. Implement input validation and allowlisting. "
            "4. Apply principle of least privilege for database accounts. "
            "5. Deploy a Web Application Firewall (WAF) as an additional layer."
        ),
    },
    "weak_cryptography": {
        "explanation": (
            "Weak cryptographic algorithms (MD5, SHA-1, DES, RC4) have known mathematical weaknesses "
            "that allow attackers to break the encryption, forge signatures, or reverse hashes "
            "using modern computing resources."
        ),
        "business_impact": (
            "Banking data protected with weak cryptography can be decrypted by sophisticated adversaries. "
            "Customer PINs, card data, and transaction records could be exposed. "
            "PCI-DSS 4.0 explicitly prohibits weak ciphers for cardholder data protection."
        ),
        "remediation": (
            "1. Replace MD5/SHA-1 with SHA-256 or SHA-3 for hashing. "
            "2. Replace DES/3DES with AES-256-GCM. "
            "3. Replace RC4 with ChaCha20-Poly1305 for stream encryption. "
            "4. Enforce TLS 1.2+ for all communications (disable TLS 1.0/1.1). "
            "5. Implement a cryptographic algorithm policy and review cycle."
        ),
    },
    "unsafe_deserialization": {
        "explanation": (
            "Unsafe deserialization allows attackers to craft malicious serialized objects "
            "that, when deserialized by the application, execute arbitrary code on the server. "
            "Python's pickle and PHP's unserialize are common attack vectors."
        ),
        "business_impact": (
            "Remote Code Execution (RCE) in banking servers can lead to complete system takeover, "
            "data theft, ransomware deployment, and unauthorized fund transfers. "
            "This is classified as a critical breach requiring immediate RBI notification."
        ),
        "remediation": (
            "1. Never deserialize data from untrusted sources with pickle or similar tools. "
            "2. Use safe alternatives: JSON for data exchange, yaml.safe_load() for YAML. "
            "3. Implement integrity checks (HMAC signatures) before deserializing any data. "
            "4. Apply sandboxing and process isolation for deserialization operations. "
            "5. Monitor for unusual process spawning that may indicate exploitation."
        ),
    },
    "security_misconfiguration": {
        "explanation": (
            "Security misconfigurations occur when systems are deployed with insecure default settings, "
            "unnecessary features enabled, or sensitive information exposed through configuration files. "
            "These are often the easiest vulnerabilities for attackers to exploit."
        ),
        "business_impact": (
            "Misconfigurations in banking systems can expose debug endpoints, admin interfaces, "
            "or raw database connections to the internet. "
            "This can violate RBI IS Audit requirements and PCI-DSS Requirement 2."
        ),
        "remediation": (
            "1. Apply CIS Benchmark hardening guides for all system components. "
            "2. Disable DEBUG mode in all production environments. "
            "3. Remove default credentials and enforce strong password policies. "
            "4. Restrict exposed ports to only those required for operation. "
            "5. Implement regular configuration drift detection."
        ),
    },
    "vulnerable_dependency": {
        "explanation": (
            "Vulnerable dependencies are third-party libraries included in the application "
            "that contain known security flaws. "
            "Attackers actively scan for applications using vulnerable library versions."
        ),
        "business_impact": (
            "Known CVEs in banking application dependencies are exploited in automated attacks. "
            "Financial malware specifically targets unpatched library vulnerabilities. "
            "RBI requires vulnerability remediation within defined SLA windows."
        ),
        "remediation": (
            "1. Update the affected package to the patched version immediately. "
            "2. Subscribe to vulnerability advisories (NVD, GitHub Security Advisories). "
            "3. Implement automated dependency scanning in the CI/CD pipeline. "
            "4. Maintain a Software Bill of Materials (SBOM) for all components. "
            "5. Define and enforce patch SLA policies aligned with CVSS severity."
        ),
    },
    "command_injection": {
        "explanation": (
            "Command injection occurs when user input is passed to system shell commands without validation. "
            "Attackers can inject additional commands separated by metacharacters (;, |, &&) "
            "to execute arbitrary operating system commands."
        ),
        "business_impact": (
            "OS command execution in banking servers can enable data exfiltration, "
            "lateral movement across the network, and complete server compromise. "
            "This is a severe breach scenario requiring immediate regulatory notification."
        ),
        "remediation": (
            "1. Avoid using os.system() or shell=True wherever possible. "
            "2. Use subprocess with a list of arguments (no shell interpretation). "
            "3. Validate and sanitize all user inputs against strict allowlists. "
            "4. Run application processes with minimal OS privileges. "
            "5. Implement process monitoring and anomaly detection for unexpected child processes."
        ),
    },
}

DEFAULT_TEMPLATE = {
    "explanation": (
        "A security vulnerability has been detected that could pose a risk to the application. "
        "Review the finding details and consult security documentation for more context."
    ),
    "business_impact": (
        "This vulnerability could expose banking customer data, enable unauthorized access, "
        "or create compliance violations with RBI, PCI-DSS, or SWIFT regulations."
    ),
    "remediation": (
        "1. Review the code at the identified file and line number. "
        "2. Apply secure coding best practices relevant to this vulnerability category. "
        "3. Test the fix in a non-production environment. "
        "4. Document the remediation for audit purposes."
    ),
}


def get_template(category: str) -> dict:
    normalized = (category or "unknown").lower().replace("-", "_")
    return TEMPLATE_INSIGHTS.get(normalized, DEFAULT_TEMPLATE)
