"""
NOVA — Benchmark Suite Payload Generator
Generates five ZIP payloads — very_low_risk, low_risk, medium_risk, high_risk,
critical_risk — the canonical regression suite specified in
docs/benchmark_suite_spec.md. Every vulnerability below was placed against a
specific, verified scanner rule (static_scanner.py's fallback PATTERN_RULES,
config_scanner.py, docker_scanner.py, yaml_scanner.py, secrets_scanner.py, or
a real OSV/pip-audit-tracked CVE) — not an assumption of what "should" be
detected. Rule severities are fixed per-rule in this codebase, not tunable
per-finding, so each repo's target risk band is achieved by choosing *which*
rules fire, not by hand-picking a CVSS number.
"""

import os
import zipfile
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


# ── Repo 1: NOVA-demo-very-low-risk ─────────────────────────────────────────
# Secure authentication & session microservice. Zero intended findings —
# this is NOVA's false-positive regression check as much as anything else.

VERY_LOW_RISK_FILES = {
    "requirements.txt": (
        "fastapi==0.115.0\n"
        "pydantic==2.9.0\n"
        "uvicorn==0.30.6\n"
        "passlib[bcrypt]==1.7.4\n"
    ),
    "app/__init__.py": "",
    "app/store.py": (
        "import secrets\n\n\n"
        "class InMemoryUserStore:\n"
        '    """A single-process user + session store. A real deployment would\n'
        "    swap this for a real database -- kept in-memory here purely to\n"
        "    keep this reference repository's dependency footprint minimal.\n"
        '    """\n\n'
        "    def __init__(self):\n"
        "        self._users: dict[str, str] = {}  # email -> hashed_password\n"
        "        self._sessions: dict[str, str] = {}  # opaque token -> email\n\n"
        "    def create_user(self, email: str, hashed_password: str) -> None:\n"
        "        if email in self._users:\n"
        '            raise ValueError("Email already registered")\n'
        "        self._users[email] = hashed_password\n\n"
        "    def get_hashed_password(self, email: str) -> str | None:\n"
        "        return self._users.get(email)\n\n"
        "    def create_session(self, email: str) -> str:\n"
        "        token = secrets.token_urlsafe(32)\n"
        "        self._sessions[token] = email\n"
        "        return token\n\n"
        "    def resolve_session(self, token: str) -> str | None:\n"
        "        return self._sessions.get(token)\n\n\n"
        "store = InMemoryUserStore()\n"
    ),
    "app/schemas.py": (
        "from pydantic import BaseModel, EmailStr, Field\n\n\n"
        "class UserCreate(BaseModel):\n"
        "    email: EmailStr\n"
        "    password: str = Field(min_length=12, max_length=128)\n\n\n"
        "class UserLogin(BaseModel):\n"
        "    email: EmailStr\n"
        "    password: str = Field(min_length=1, max_length=128)\n\n\n"
        "class UserOut(BaseModel):\n"
        "    email: EmailStr\n\n\n"
        "class TokenOut(BaseModel):\n"
        "    access_token: str\n"
        '    token_type: str = "bearer"\n'
    ),
    "app/security.py": (
        "from passlib.context import CryptContext\n\n"
        'pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")\n\n\n'
        "def hash_password(plain_password: str) -> str:\n"
        "    return pwd_context.hash(plain_password)\n\n\n"
        "def verify_password(plain_password: str, hashed_password: str) -> bool:\n"
        "    return pwd_context.verify(plain_password, hashed_password)\n"
    ),
    "app/main.py": (
        "from fastapi import FastAPI, Depends, HTTPException, status\n"
        "from fastapi.security import OAuth2PasswordBearer\n\n"
        "from app.store import store\n"
        "from app.schemas import UserCreate, UserLogin, UserOut, TokenOut\n"
        "from app.security import hash_password, verify_password\n\n"
        'app = FastAPI(title="NOVA Demo -- Secure Authentication Service")\n'
        'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")\n\n\n'
        '@app.get("/health")\n'
        "def health():\n"
        '    return {"status": "healthy"}\n\n\n'
        '@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)\n'
        "def register(payload: UserCreate):\n"
        "    try:\n"
        "        store.create_user(payload.email, hash_password(payload.password))\n"
        "    except ValueError:\n"
        '        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")\n'
        "    return UserOut(email=payload.email)\n\n\n"
        '@app.post("/login", response_model=TokenOut)\n'
        "def login(payload: UserLogin):\n"
        "    hashed = store.get_hashed_password(payload.email)\n"
        "    if hashed is None or not verify_password(payload.password, hashed):\n"
        '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")\n'
        "    return TokenOut(access_token=store.create_session(payload.email))\n\n\n"
        "def get_current_user(token: str = Depends(oauth2_scheme)) -> str:\n"
        "    email = store.resolve_session(token)\n"
        "    if email is None:\n"
        '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")\n'
        "    return email\n\n\n"
        '@app.get("/me", response_model=UserOut)\n'
        "def read_current_user(current_email: str = Depends(get_current_user)):\n"
        "    return UserOut(email=current_email)\n"
    ),
    "tests/test_auth.py": (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n\n"
        "client = TestClient(app)\n\n\n"
        "def test_health():\n"
        '    assert client.get("/health").status_code == 200\n\n\n'
        "def test_register_and_login():\n"
        '    client.post("/register", json={"email": "demo@example.com", "password": "correct-horse-battery"})\n'
        '    response = client.post("/login", json={"email": "demo@example.com", "password": "correct-horse-battery"})\n'
        "    assert response.status_code == 200\n"
        '    assert "access_token" in response.json()\n\n\n'
        "def test_login_rejects_wrong_password():\n"
        '    response = client.post("/login", json={"email": "demo@example.com", "password": "wrong-password"})\n'
        "    assert response.status_code == 401\n"
    ),
    "Dockerfile": (
        "FROM python:3.12.4-slim AS builder\n"
        "WORKDIR /build\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir --prefix=/install -r requirements.txt\n\n"
        "FROM python:3.12.4-slim\n"
        "RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid appuser --no-create-home appuser\n"
        "WORKDIR /app\n"
        "COPY --from=builder /install /usr/local\n"
        "COPY app/ ./app/\n"
        "USER appuser\n"
        "EXPOSE 8000\n"
        "HEALTHCHECK --interval=30s --timeout=3s CMD python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')\" || exit 1\n"
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    ),
    "docker-compose.yml": (
        "services:\n"
        "  auth-service:\n"
        "    build: .\n"
        "    ports:\n"
        '      - "8000:8000"\n'
        "    read_only: true\n"
        "    mem_limit: 256m\n"
    ),
    ".github/workflows/ci.yml": (
        "name: CI\n\n"
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  pull_request:\n"
        "    branches: [main]\n\n"
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-24.04\n"
        "    steps:\n"
        "      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n"
        "      - uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b\n"
        "        with:\n"
        '          python-version: "3.12"\n'
        "      - run: pip install -r requirements.txt pytest\n"
        "      - run: pytest tests/\n"
    ),
}


# ── Repo 2: NOVA-demo-low-risk ──────────────────────────────────────────────
# Employee portal. Same secure foundation as repo 1, plus a handful of small,
# realistic mistakes in config/dependencies/Docker hygiene.

LOW_RISK_FILES = {
    "requirements.txt": (
        "fastapi==0.115.0\n"
        "pydantic==2.9.0\n"
        "uvicorn==0.30.6\n"
        "passlib[bcrypt]==1.7.4\n"
        "requests==2.31.0\n"
    ),
    "app/__init__.py": "",
    "app/store.py": VERY_LOW_RISK_FILES["app/store.py"],
    "app/schemas.py": VERY_LOW_RISK_FILES["app/schemas.py"],
    "app/security.py": VERY_LOW_RISK_FILES["app/security.py"],
    "app/directory.py": (
        "import requests\n\n\n"
        "def lookup_employee(employee_id: str) -> dict:\n"
        '    """Look up an employee in the corporate directory service."""\n'
        "    response = requests.get(\n"
        f'        f"https://directory.internal.example.com/api/employees/{{employee_id}}", timeout=5\n'
        "    )\n"
        "    response.raise_for_status()\n"
        "    return response.json()\n"
    ),
    "app/main.py": (
        "from fastapi import FastAPI, Depends, HTTPException, status\n"
        "from fastapi.security import OAuth2PasswordBearer\n\n"
        "from app.store import store\n"
        "from app.schemas import UserCreate, UserLogin, UserOut, TokenOut\n"
        "from app.security import hash_password, verify_password\n"
        "from app.directory import lookup_employee\n\n"
        'app = FastAPI(title="NOVA Demo -- Employee Portal")\n'
        'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")\n\n\n'
        '@app.get("/health")\n'
        "def health():\n"
        '    return {"status": "healthy"}\n\n\n'
        '@app.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)\n'
        "def register(payload: UserCreate):\n"
        "    try:\n"
        "        store.create_user(payload.email, hash_password(payload.password))\n"
        "    except ValueError:\n"
        '        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")\n'
        "    return UserOut(email=payload.email)\n\n\n"
        '@app.post("/login", response_model=TokenOut)\n'
        "def login(payload: UserLogin):\n"
        "    hashed = store.get_hashed_password(payload.email)\n"
        "    if hashed is None or not verify_password(payload.password, hashed):\n"
        '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")\n'
        "    return TokenOut(access_token=store.create_session(payload.email))\n\n\n"
        "def get_current_user(token: str = Depends(oauth2_scheme)) -> str:\n"
        "    email = store.resolve_session(token)\n"
        "    if email is None:\n"
        '        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")\n'
        "    return email\n\n\n"
        '@app.get("/me", response_model=UserOut)\n'
        "def read_current_user(current_email: str = Depends(get_current_user)):\n"
        "    return UserOut(email=current_email)\n\n\n"
        '@app.get("/directory/{employee_id}")\n'
        "def get_employee(employee_id: str, current_email: str = Depends(get_current_user)):\n"
        "    return lookup_employee(employee_id)\n"
    ),
    "config/settings.yaml": (
        "app_name: employee-portal\n"
        "environment: production\n"
        "cors:\n"
        "  allow_origins: \"*\"\n"
        "notifications:\n"
        "  partner_webhook_url: http://partner-notify.example.com/hook\n"
    ),
    ".env": (
        "# Accidentally committed alongside .env.example -- contains only a\n"
        "# low-sensitivity internal notification webhook, nothing else.\n"
        "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/TEXAMPLE00/BEXAMPLE00/EXAMPLEPLACEHOLDERNOTREAL\n"
    ),
    ".env.example": (
        "SLACK_WEBHOOK_URL=\n"
    ),
    "Dockerfile": (
        "FROM python:3.12.4-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY app/ ./app/\n"
        "RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid appuser --no-create-home appuser\n"
        "USER appuser\n"
        "EXPOSE 8000\n"
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    ),
    "docker-compose.yml": (
        "services:\n"
        "  employee-portal:\n"
        "    build: .\n"
        "    ports:\n"
        '      - "8000:8000"\n'
        "    env_file: .env\n"
    ),
    ".github/workflows/ci.yml": VERY_LOW_RISK_FILES[".github/workflows/ci.yml"],
}


# ── Repo 3: NOVA-demo-medium-risk ───────────────────────────────────────────
# Inventory management system (Flask) + a small Node reporting component.
# Deliberately avoids auth/payment/customer-data module keywords (see
# docs/benchmark_suite_spec.md sec 0) -- these are general developer mistakes,
# not business-critical-path ones.

MEDIUM_RISK_FILES = {
    "requirements.txt": (
        "flask==2.2.3\n"
    ),
    "app/__init__.py": "",
    "app/main.py": (
        "from flask import Flask, jsonify\n"
        "from app.inventory.orders import orders_bp\n"
        "from app.inventory.stock import stock_bp\n\n"
        "app = Flask(__name__)\n"
        "app.register_blueprint(orders_bp)\n"
        "app.register_blueprint(stock_bp)\n\n\n"
        '@app.get("/health")\n'
        "def health():\n"
        '    return jsonify({"status": "healthy"})\n'
    ),
    "app/inventory/__init__.py": "",
    "app/inventory/orders.py": (
        "from flask import Blueprint, jsonify, request\n\n"
        'orders_bp = Blueprint("orders", __name__, url_prefix="/orders")\n\n'
        "_ORDERS = {}\n"
        "_next_id = 1\n\n\n"
        '@orders_bp.post("/")\n'
        "def create_order():\n"
        "    global _next_id\n"
        "    payload = request.get_json(force=True)\n"
        "    order_id = _next_id\n"
        "    _next_id += 1\n"
        '    _ORDERS[order_id] = {"sku": payload.get("sku"), "quantity": payload.get("quantity")}\n'
        '    return jsonify({"order_id": order_id}), 201\n\n\n'
        '@orders_bp.get("/<int:order_id>")\n'
        "def get_order(order_id: int):\n"
        "    order = _ORDERS.get(order_id)\n"
        "    if order is None:\n"
        '        return jsonify({"error": "not found"}), 404\n'
        "    return jsonify(order)\n"
    ),
    "app/inventory/stock.py": (
        "from flask import Blueprint, jsonify\n\n"
        'stock_bp = Blueprint("stock", __name__, url_prefix="/stock")\n\n'
        "_STOCK = {\"widget-a\": 120, \"widget-b\": 45}\n\n\n"
        '@stock_bp.get("/<sku>")\n'
        "def get_stock(sku: str):\n"
        '    return jsonify({"sku": sku, "quantity": _STOCK.get(sku, 0)})\n'
    ),
    "app/utils/__init__.py": "",
    "app/utils/checksums.py": (
        "import hashlib\n\n\n"
        "def file_checksum(data: bytes) -> str:\n"
        '    """Non-cryptographic integrity check for cached report exports."""\n'
        "    return hashlib.sha1(data).hexdigest()\n"
    ),
    "config/settings.yaml": (
        "app_name: inventory-system\n"
        "environment: production\n"
        "cors:\n"
        "  allow_origins: \"*\"\n"
        "integrations:\n"
        "  legacy_erp_url: http://erp.internal.example.com/sync\n"
    ),
    "reporting-service/package.json": (
        "{\n"
        '  "name": "inventory-reporting-service",\n'
        '  "version": "1.0.0",\n'
        '  "private": true,\n'
        '  "main": "report.js",\n'
        '  "dependencies": {\n'
        '    "lodash": "4.17.15",\n'
        '    "express": "4.19.2"\n'
        "  }\n"
        "}\n"
    ),
    "reporting-service/report.js": (
        "const express = require('express');\n"
        "const _ = require('lodash');\n\n"
        "const app = express();\n\n"
        "app.get('/nightly-report', (req, res) => {\n"
        "  const summary = _.merge({}, { generated: new Date().toISOString() });\n"
        "  res.json(summary);\n"
        "});\n\n"
        "app.listen(4000, () => console.log('reporting service listening on 4000'));\n"
    ),
    "Dockerfile": (
        "FROM python:3.9\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY app/ ./app/\n"
        "ADD legacy-migration-scripts.tar.gz /app/migrations/\n"
        "EXPOSE 3306\n"
        'CMD ["python", "-m", "flask", "--app", "app.main", "run", "--host=0.0.0.0"]\n'
    ),
    "docker-compose.yml": (
        "services:\n"
        "  inventory-api:\n"
        "    build: .\n"
        "    ports:\n"
        '      - "5000:5000"\n'
        "  reporting-service:\n"
        "    build: ./reporting-service\n"
        "    ports:\n"
        '      - "4000:4000"\n'
    ),
    ".github/workflows/ci.yml": VERY_LOW_RISK_FILES[".github/workflows/ci.yml"],
}


# ── Repo 4: NOVA-demo-high-risk ─────────────────────────────────────────────
# Payment microservice. Deliberately uses app/payments/... paths -- the
# Payments business module (highest criticality/asset weight) is meant to
# apply here, reflecting that a real payment system's mistakes carry more
# business risk than the same mistake in an internal tool.

HIGH_RISK_FILES = {
    "requirements.txt": (
        "fastapi==0.115.0\n"
        "uvicorn==0.30.6\n"
        "pyyaml==5.3.1\n"
    ),
    "app/__init__.py": "",
    "app/payments/__init__.py": "",
    "app/payments/api/__init__.py": "",
    "app/payments/api/routes/__init__.py": "",
    "app/payments/config/__init__.py": "",
    "app/payments/services/__init__.py": "",
    "app/payments/config/settings.py": (
        "import os\n\n"
        "# INSECURE: DB connection string with embedded credentials, committed to\n"
        "# source control instead of loaded from a secrets manager.\n"
        'PAYMENT_DB_URL = "postgresql://payments_svc:Tr8nsact!on2024@db-payments.internal:5432/payments"\n\n'
        'MERCHANT_API_BASE = os.environ.get("MERCHANT_API_BASE", "https://api.merchant-gateway.example.com")\n'
    ),
    "app/payments/config/merchant_config.py": (
        "import yaml\n\n\n"
        "def load_merchant_config(raw_yaml: str) -> dict:\n"
        '    """Parse a merchant-uploaded YAML configuration bundle.\n\n'
        "    INSECURE: an unsafe loader can execute arbitrary Python objects\n"
        "    if the upload contains a crafted object tag -- a safe loader\n"
        "    should be used instead (see PyYAML's documented safe-loading API).\n"
        '    """\n'
        "    return yaml.load(raw_yaml)\n"
    ),
    "app/payments/services/token_vault.py": (
        "import hashlib\n\n\n"
        "def store_card_reference(card_token: str) -> str:\n"
        '    """Derive a lookup key for a tokenized card reference.\n\n'
        "    INSECURE: MD5 is not suitable for protecting sensitive reference\n"
        "    tokens -- it is fast to brute-force and offers no keyed security.\n"
        '    """\n'
        "    return hashlib.md5(card_token.encode()).hexdigest()\n"
    ),
    "app/payments/api/routes/transactions.py": (
        "import sqlite3\n"
        "from fastapi import APIRouter\n\n"
        'router = APIRouter(prefix="/payments/transactions")\n\n\n'
        '@router.get("/search")\n'
        "def search_transactions(merchant_id: str):\n"
        '    """Search transactions by merchant ID (parameterized -- safe)."""\n'
        '    conn = sqlite3.connect("payments.db")\n'
        "    cursor = conn.cursor()\n"
        '    cursor.execute("SELECT * FROM transactions WHERE merchant_id = ?", (merchant_id,))\n'
        "    rows = cursor.fetchall()\n"
        "    conn.close()\n"
        '    return {"results": rows}\n\n\n'
        '@router.get("/export")\n'
        "def export_transactions(merchant_id: str, output_format: str):\n"
        '    """Export a merchant\'s transactions via the legacy report-converter tool.\n\n'
        "    INSECURE: output_format is attacker-controlled and passed through a\n"
        "    shell, allowing arbitrary command injection via shell metacharacters.\n"
        '    """\n'
        "    import subprocess\n"
        f'    subprocess.run(f"report-converter --merchant={{merchant_id}} --format={{output_format}}", shell=True)\n'
        '    return {"status": "export queued"}\n'
    ),
    "app/payments/api/routes/receipts.py": (
        "import os\n"
        "from fastapi import APIRouter\n\n"
        'router = APIRouter(prefix="/payments/receipts")\n\n\n'
        '@router.get("/notify-partner")\n'
        "def notify_partner(partner_host: str):\n"
        '    """Ping a partner webhook host to confirm it is reachable before\n'
        "    dispatching a receipt notification.\n\n"
        "    INSECURE: partner_host is attacker-controlled and passed straight\n"
        "    into a shell command.\n"
        '    """\n'
        f'    os.system("ping -c 1 " + partner_host)\n'
        '    return {"status": "checked"}\n'
    ),
    "app/payments/api/routes/upload.py": (
        "from pathlib import Path\n"
        "from fastapi import APIRouter, UploadFile\n\n"
        'router = APIRouter(prefix="/payments/uploads")\n'
        'UPLOAD_DIR = Path("/data/payment-attachments")\n\n\n'
        '@router.post("/receipt-attachment")\n'
        "async def upload_attachment(file: UploadFile):\n"
        '    """Accept a receipt attachment upload.\n\n'
        "    INSECURE: no extension allowlist, no size limit, and the\n"
        "    destination path is built directly from the client-supplied\n"
        "    filename with no normalization.\n"
        '    """\n'
        "    destination = UPLOAD_DIR / file.filename\n"
        "    contents = await file.read()\n"
        "    destination.write_bytes(contents)\n"
        '    return {"stored_at": str(destination)}\n'
    ),
    "webhook-notifier/package.json": (
        "{\n"
        '  "name": "payments-webhook-notifier",\n'
        '  "version": "1.0.0",\n'
        '  "private": true,\n'
        '  "main": "views.js",\n'
        '  "dependencies": {\n'
        '    "express": "4.19.2"\n'
        "  }\n"
        "}\n"
    ),
    "webhook-notifier/views.js": (
        "const express = require('express');\n"
        "const app = express();\n\n"
        "// INSECURE: the transaction note is interpolated directly into the\n"
        "// HTML response with no escaping, allowing a stored XSS payload\n"
        "// submitted as a transaction note to execute in an admin's browser.\n"
        "app.get('/admin/transaction-note', (req, res) => {\n"
        "  const note = req.query.note || '';\n"
        "  res.send('<html><body><div class=\"note\">' + note + '</div></body></html>');\n"
        "});\n\n"
        "app.listen(4100, () => console.log('webhook-notifier listening on 4100'));\n"
    ),
    "Dockerfile": (
        "FROM python:3.11-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY app/ ./app/\n"
        "ENV PAYMENT_GATEWAY_TOKEN=sk_test_EXAMPLENOTREALPLACEHOLDER\n"
        "EXPOSE 8000\n"
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    ),
    "docker-compose.yml": (
        "services:\n"
        "  payments-api:\n"
        "    build: .\n"
        "    ports:\n"
        '      - "8000:8000"\n'
        "  webhook-notifier:\n"
        "    build: ./webhook-notifier\n"
        "    ports:\n"
        '      - "4100:4100"\n'
    ),
    ".github/workflows/ci.yml": VERY_LOW_RISK_FILES[".github/workflows/ci.yml"],
}


# ── Repo 5: NOVA-demo-critical-risk ─────────────────────────────────────────
# Legacy core banking backend -- the "everything wrong at once" reference.

CRITICAL_RISK_FILES = {
    "requirements.txt": (
        "flask==2.2.3\n"
        "pyyaml==5.3.1\n"
    ),
    "package.json": (
        "{\n"
        '  "name": "core-banking-legacy",\n'
        '  "version": "0.1.0",\n'
        '  "private": true,\n'
        '  "dependencies": {\n'
        '    "lodash": "4.17.11"\n'
        "  }\n"
        "}\n"
    ),
    "app/__init__.py": "",
    "app/core/__init__.py": "",
    "app/auth/__init__.py": "",
    "app/api/__init__.py": "",
    "app/api/routes/__init__.py": "",
    "app/core/config.py": (
        "# INSECURE: production credentials hardcoded directly in source.\n"
        'DB_PASSWORD = "CoreBank_Prod_2019!"\n'
        'AWS_ACCESS_KEY_ID = "AKIA27EXAMPLEKEYID11"\n'
        "DEBUG = True\n"
    ),
    "app/auth/password.py": (
        "import hashlib\n\n\n"
        "def hash_password(plain_password: str) -> str:\n"
        '    """INSECURE: MD5 has no place hashing account passwords -- it is\n'
        "    unsalted here and trivially reversible via rainbow tables.\n"
        '    """\n'
        "    return hashlib.md5(plain_password.encode()).hexdigest()\n"
    ),
    "app/api/routes/transfer.py": (
        "import sqlite3\n"
        "from flask import Blueprint, request, jsonify\n\n"
        'transfer_bp = Blueprint("transfer", __name__)\n\n\n'
        '@transfer_bp.post("/transfer")\n'
        "def transfer_funds():\n"
        '    """INSECURE: the account number is concatenated directly into the\n'
        "    SQL update statement instead of using a bound parameter.\n"
        '    """\n'
        "    account_number = request.json.get(\"account_number\")\n"
        "    amount = request.json.get(\"amount\")\n"
        '    conn = sqlite3.connect("core_banking.db")\n'
        "    cursor = conn.cursor()\n"
        '    cursor.execute("UPDATE accounts SET balance = balance - " + str(amount) +\n'
        '                   " WHERE account_number = \'" + account_number + "\'")\n'
        "    conn.commit()\n"
        "    conn.close()\n"
        '    return jsonify({"status": "transferred"})\n'
    ),
    "app/api/routes/accounts.py": (
        "import sqlite3\n"
        "from flask import Blueprint, request, jsonify\n\n"
        'accounts_bp = Blueprint("accounts", __name__)\n\n\n'
        '@accounts_bp.get("/accounts/search")\n'
        "def search_accounts():\n"
        '    """INSECURE: the search term is concatenated directly into the SQL\n'
        "    query instead of using a bound parameter.\n"
        '    """\n'
        '    name = request.args.get("name", "")\n'
        '    conn = sqlite3.connect("core_banking.db")\n'
        "    cursor = conn.cursor()\n"
        '    cursor.execute("SELECT * FROM accounts WHERE holder_name LIKE \'%" + name + "%\'")\n'
        "    rows = cursor.fetchall()\n"
        "    conn.close()\n"
        '    return jsonify({"results": rows})\n\n\n'
        '@accounts_bp.get("/accounts/<account_id>")\n'
        "def get_account(account_id):\n"
        '    """INSECURE (structural, not pattern-detectable today): returns any\n'
        "    account's data with no check that the caller owns it -- a real IDOR.\n"
        '    Requires ast-grep/Joern cross-file authorization analysis.\n'
        '    """\n'
        '    conn = sqlite3.connect("core_banking.db")\n'
        "    cursor = conn.cursor()\n"
        '    cursor.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,))\n'
        "    row = cursor.fetchone()\n"
        "    conn.close()\n"
        '    return jsonify({"account": row})\n'
    ),
    "app/api/routes/admin_diagnostics.py": (
        "import os\n"
        "from flask import Blueprint, request, jsonify\n\n"
        'admin_diagnostics_bp = Blueprint("admin_diagnostics", __name__)\n\n\n'
        '@admin_diagnostics_bp.get("/admin/diagnostics/ping")\n'
        "def ping_host():\n"
        '    """INSECURE: the host parameter is attacker-controlled and passed\n'
        "    straight into a shell command.\n"
        '    """\n'
        '    host = request.args.get("host", "")\n'
        '    os.system("ping -c 1 " + host)\n'
        '    return jsonify({"status": "executed"})\n'
    ),
    "app/api/routes/session.py": (
        "import pickle\n"
        "from flask import Blueprint, request, jsonify\n\n"
        'session_bp = Blueprint("session", __name__)\n\n\n'
        '@session_bp.get("/session/restore")\n'
        "def restore_session():\n"
        '    """INSECURE: deserializes a client-supplied cookie with pickle,\n'
        "    which can execute arbitrary code for a crafted payload.\n"
        '    """\n'
        '    raw_cookie = request.cookies.get("session_data", "")\n'
        "    session_obj = pickle.loads(bytes.fromhex(raw_cookie)) if raw_cookie else {}\n"
        '    return jsonify({"restored": bool(session_obj)})\n'
    ),
    "app/api/routes/documents.py": (
        "from flask import Blueprint, send_from_directory\n\n"
        'documents_bp = Blueprint("documents", __name__)\n\n\n'
        '@documents_bp.get("/documents/<path:filename>")\n'
        "def get_document(filename):\n"
        '    return send_from_directory("/data/statements", filename)\n'
    ),
    "certs/service.pem": (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEAwJ5rTm0V4z3s6qkS0N1YkqjZ0e6d9fGZ1B3n7t8rXqQ2v1p9\n"
        "PLACEHOLDERKEYMATERIALFORBENCHMARKPURPOSESONLYNOTAREALPRIVATEKEY\n"
        "YnE3v8sQ2rXqP1t7n3B0e6dZjq0N0Sk6q3s4z0V0mTr5J1w9PLACEHOLDERDATA0=\n"
        "-----END RSA PRIVATE KEY-----\n"
    ),
    ".env": (
        "# INSECURE: production-shaped secrets committed to source control.\n"
        "DEBUG=true\n"
        "SECRET_KEY=django-insecure-development-placeholder-key\n"
        "DB_PASSWORD=CoreBank_Prod_2019!\n"
        "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
    ),
    "k8s/deployment.yaml": (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: core-banking-legacy\n"
        "spec:\n"
        "  replicas: 2\n"
        "  selector:\n"
        "    matchLabels:\n"
        "      app: core-banking-legacy\n"
        "  template:\n"
        "    metadata:\n"
        "      labels:\n"
        "        app: core-banking-legacy\n"
        "    spec:\n"
        "      hostNetwork: true\n"
        "      containers:\n"
        "        - name: core-banking-legacy\n"
        "          image: core-banking-legacy:2019-01-snapshot\n"
        "          securityContext:\n"
        "            privileged: true\n"
        "          env:\n"
        "            - name: DB_PASSWORD\n"
        "              value: CoreBank_Prod_2019!\n"
    ),
    "docker-compose.yml": (
        "services:\n"
        "  core-banking-legacy:\n"
        "    build: .\n"
        "    privileged: true\n"
        "    environment:\n"
        "      DB_PASSWORD: CoreBank_Prod_2019!\n"
        "    ports:\n"
        '      - "5000:5000"\n'
    ),
    "Dockerfile": (
        "FROM python:3.9\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY app/ ./app/\n"
        'CMD ["python", "-m", "flask", "--app", "app.main", "run", "--host=0.0.0.0"]\n'
    ),
    ".github/workflows/ci.yml": (
        "name: CI\n\n"
        "on:\n"
        "  pull_request_target:\n"
        "    branches: [main]\n\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-24.04\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          ref: ${{ github.event.pull_request.head.sha }}\n"
        "      - name: Build\n"
        "        run: |\n"
        "          echo \"Building PR: ${{ github.event.pull_request.title }}\"\n"
        "          npm install\n"
        "          npm run build\n"
    ),
}


# ── Zip generation ─────────────────────────────────────────────────────────────

def _create_zip_file(files: dict[str, str], output_path: Path):
    """Write the dictionary of filenames and contents into a ZIP file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in files.items():
            zip_file.writestr(filename, content)


def generate_premade_payloads(data_dir: Path):
    """Generate the pre-made ZIP payloads if they do not exist."""
    payloads_dir = data_dir / "payloads"
    payloads_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("very_low_risk.zip", VERY_LOW_RISK_FILES),
        ("low_risk.zip", LOW_RISK_FILES),
        ("medium_risk.zip", MEDIUM_RISK_FILES),
        ("high_risk.zip", HIGH_RISK_FILES),
        ("critical_risk.zip", CRITICAL_RISK_FILES),
    ]

    for filename, files_dict in configs:
        zip_path = payloads_dir / filename
        if not zip_path.exists():
            logger.info("payload_generator.creating", file=filename)
            try:
                _create_zip_file(files_dict, zip_path)
                logger.info("payload_generator.created_successfully", file=filename)
            except Exception as exc:
                logger.exception("payload_generator.failed_to_create", file=filename, error=str(exc))
        else:
            logger.debug("payload_generator.exists", file=filename)
