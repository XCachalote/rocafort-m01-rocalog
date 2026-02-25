from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from rocalog.audit_storage import (
    access_log,
    as_dict,
    create_session,
    get_conn,
    get_user_by_token,
    hash_password,
    init_db,
    log_event,
    verify_password,
    verify_totp,
)
from rocalog.pdf_report import generate_report_pdf
from rocalog.scoring import ControlScoreInput, calculate_score_summary

app = FastAPI(title="RocaAudit", version="0.1.0")


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str = Field(min_length=6, max_length=6)


class UserCreateRequest(BaseModel):
    full_name: str
    username: str
    document_id: str
    role: str
    password: str = Field(min_length=8)


class EngagementCreateRequest(BaseModel):
    company_name: str
    tax_identifier: str
    full_address: str
    contact_person: str
    auditor_name: str
    auditor_document_id: str
    audit_date: str
    scope_text: str
    liability_clause_text: str
    remote_access_consent_text: str


class ControlUpsertRequest(BaseModel):
    category: str
    code: str
    title: str
    criticality_weight: float = Field(gt=0)
    max_score: float = Field(default=100, gt=0)
    compliance_value: float = Field(ge=0, le=1)
    evidence_text: str
    risk_observation: str


class SignatureRequest(BaseModel):
    signer_type: str
    signer_name: str
    signer_document_id: str
    signature_text: str


@app.on_event("startup")
def startup() -> None:
    init_db()


def auth_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    with get_conn() as conn:
        user = get_user_by_token(conn, token)
        if not user:
            raise HTTPException(401, "Invalid or expired token")
        return as_dict(user)  # type: ignore[return-value]


def require_roles(user: dict, allowed: set[str]) -> None:
    if user["role"] not in allowed:
        raise HTTPException(403, "Forbidden")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html><body>
    <h2>RocaAudit API</h2>
    <p>Use <code>/docs</code> for interactive API and <code>/dashboard/{engagement_id}</code> for dashboard.</p>
    </body></html>
    """


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (payload.username,)).fetchone()
        if not row:
            raise HTTPException(401, "Invalid credentials")
        user = as_dict(row)
        assert user is not None
        if not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(401, "Invalid credentials")
        if not verify_totp(user["totp_secret"], payload.totp_code):
            raise HTTPException(401, "Invalid MFA code")
        token = create_session(conn, user["id"])
        access_log(conn, user["id"], "login", "user", str(user["id"]))
        return {"access_token": token, "role": user["role"]}


@app.post("/api/users")
def create_user(payload: UserCreateRequest, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin"})
    with get_conn() as conn:
        import pyotp

        totp_secret = pyotp.random_base32()
        cur = conn.execute(
            """
            INSERT INTO users(full_name, username, document_id, role, password_hash, totp_secret, created_at)
            VALUES(?,?,?,?,?,?,datetime('now'))
            """,
            (
                payload.full_name,
                payload.username,
                payload.document_id,
                payload.role,
                hash_password(payload.password),
                totp_secret,
            ),
        )
        new_id = cur.lastrowid
        log_event(conn, user["id"], "users", str(new_id), "insert", after_json=json.dumps(payload.model_dump()))
        access_log(conn, user["id"], "write", "users", str(new_id))
        return {"id": new_id, "totp_secret": totp_secret}


@app.post("/api/engagements")
def create_engagement(payload: EngagementCreateRequest, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin", "auditor"})
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO engagements(
            company_name, tax_identifier, full_address, contact_person,
            auditor_name, auditor_document_id, audit_date, scope_text,
            liability_clause_text, remote_access_consent_text,
            created_by, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
            """,
            (
                payload.company_name,
                payload.tax_identifier,
                payload.full_address,
                payload.contact_person,
                payload.auditor_name,
                payload.auditor_document_id,
                payload.audit_date,
                payload.scope_text,
                payload.liability_clause_text,
                payload.remote_access_consent_text,
                user["id"],
            ),
        )
        engagement_id = cur.lastrowid
        log_event(conn, user["id"], "engagements", str(engagement_id), "insert", after_json=json.dumps(payload.model_dump()))
        return {"engagement_id": engagement_id}


@app.post("/api/engagements/{engagement_id}/controls")
def upsert_control(engagement_id: int, payload: ControlUpsertRequest, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin", "auditor"})
    with get_conn() as conn:
        before = conn.execute(
            "SELECT * FROM controls WHERE engagement_id = ? AND code = ?",
            (engagement_id, payload.code),
        ).fetchone()
        if before:
            conn.execute(
                """
                UPDATE controls
                SET title=?, criticality_weight=?, max_score=?, compliance_value=?,
                    evidence_text=?, risk_observation=?, entered_by=?, updated_at=datetime('now')
                WHERE engagement_id=? AND code=?
                """,
                (
                    payload.title,
                    payload.criticality_weight,
                    payload.max_score,
                    payload.compliance_value,
                    payload.evidence_text,
                    payload.risk_observation,
                    user["id"],
                    engagement_id,
                    payload.code,
                ),
            )
            op = "update"
        else:
            conn.execute(
                """
                INSERT INTO controls(engagement_id, category, code, title, criticality_weight, max_score, compliance_value,
                evidence_text, risk_observation, entered_by, entered_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                """,
                (
                    engagement_id,
                    payload.category,
                    payload.code,
                    payload.title,
                    payload.criticality_weight,
                    payload.max_score,
                    payload.compliance_value,
                    payload.evidence_text,
                    payload.risk_observation,
                    user["id"],
                ),
            )
            op = "insert"
        log_event(
            conn,
            user["id"],
            "controls",
            f"{engagement_id}:{payload.code}",
            op,
            before_json=json.dumps(as_dict(before) or {}),
            after_json=json.dumps(payload.model_dump()),
        )

        score = _compute_engagement_score(conn, engagement_id)
        return score


def _compute_engagement_score(conn, engagement_id: int) -> dict:
    rows = conn.execute("SELECT * FROM controls WHERE engagement_id = ?", (engagement_id,)).fetchall()
    summary = calculate_score_summary(
        [
            ControlScoreInput(
                category=row["category"],
                compliance_value=row["compliance_value"],
                criticality_weight=row["criticality_weight"],
                max_score=row["max_score"],
            )
            for row in rows
        ]
    )
    return {
        "engagement_id": engagement_id,
        "score_global": summary.score_global,
        "risk_global": summary.risk_global,
        "semaphore": summary.semaphore,
        "per_category": summary.per_category,
        "controls_count": len(rows),
    }


@app.get("/api/engagements/{engagement_id}/dashboard")
def dashboard_data(engagement_id: int, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin", "auditor", "reviewer", "client_readonly"})
    with get_conn() as conn:
        score = _compute_engagement_score(conn, engagement_id)
        controls = [as_dict(r) for r in conn.execute("SELECT * FROM controls WHERE engagement_id = ?", (engagement_id,)).fetchall()]
        access_log(conn, user["id"], "read", "engagement", str(engagement_id))
        return {"score": score, "controls": controls}


@app.get("/dashboard/{engagement_id}", response_class=HTMLResponse)
def dashboard_page(engagement_id: int) -> str:
    return f"""
<html>
<head><title>Dashboard Auditoría {engagement_id}</title></head>
<body>
<h2>Dashboard auditoría #{engagement_id}</h2>
<div id='score'></div>
<table border='1' id='tbl'><thead><tr><th>Cat</th><th>Código</th><th>Título</th><th>Cump.</th><th>Peso</th></tr></thead><tbody></tbody></table>
<script>
const token = localStorage.getItem('token') || prompt('Bearer token');
if(token) localStorage.setItem('token', token);
async function refresh() {{
 const r = await fetch('/api/engagements/{engagement_id}/dashboard', {{headers: {{Authorization: 'Bearer '+token}}}});
 if(!r.ok) {{ document.getElementById('score').innerText='Sin acceso'; return; }}
 const data = await r.json();
 document.getElementById('score').innerText = `Score=${{data.score.score_global}} | Riesgo=${{data.score.risk_global}} | Semáforo=${{data.score.semaphore}}`;
 const tbody = document.querySelector('#tbl tbody');
 tbody.innerHTML = '';
 for(const c of data.controls) {{
   const tr = document.createElement('tr');
   tr.innerHTML = `<td>${{c.category}}</td><td>${{c.code}}</td><td>${{c.title}}</td><td>${{c.compliance_value}}</td><td>${{c.criticality_weight}}</td>`;
   tbody.appendChild(tr);
 }}
}}
setInterval(refresh, 3000); refresh();
</script>
</body>
</html>
"""


@app.post("/api/engagements/{engagement_id}/signatures")
def add_signature(engagement_id: int, payload: SignatureRequest, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin", "auditor", "reviewer"})
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO signatures(engagement_id, signer_type, signer_name, signer_document_id, signature_text, signed_at)
            VALUES(?,?,?,?,?,datetime('now'))
            """,
            (
                engagement_id,
                payload.signer_type,
                payload.signer_name,
                payload.signer_document_id,
                payload.signature_text,
            ),
        )
        sig_id = cur.lastrowid
        log_event(conn, user["id"], "signatures", str(sig_id), "insert", after_json=json.dumps(payload.model_dump()))
        return {"signature_id": sig_id}


@app.post("/api/engagements/{engagement_id}/report")
def generate_report(engagement_id: int, user: dict = Depends(auth_user)) -> dict:
    require_roles(user, {"admin", "auditor", "reviewer"})
    with get_conn() as conn:
        engagement = as_dict(conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone())
        if not engagement:
            raise HTTPException(404, "Engagement not found")
        controls = [as_dict(r) for r in conn.execute("SELECT * FROM controls WHERE engagement_id = ?", (engagement_id,)).fetchall()]
        signatures = [as_dict(r) for r in conn.execute("SELECT * FROM signatures WHERE engagement_id = ?", (engagement_id,)).fetchall()]
        score = _compute_engagement_score(conn, engagement_id)
        last = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS v FROM report_versions WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        version = int(last["v"]) + 1
        out = Path(f"data/reports/engagement-{engagement_id}-v{version}.pdf")
        pdf_path, digest = generate_report_pdf(out, engagement, controls, score, signatures)
        conn.execute(
            """
            INSERT INTO report_versions(engagement_id, version_number, pdf_path, sha256, created_by, created_at)
            VALUES(?,?,?,?,?,datetime('now'))
            """,
            (engagement_id, version, pdf_path, digest, user["id"]),
        )
        log_event(conn, user["id"], "report_versions", f"{engagement_id}:{version}", "insert", after_json=json.dumps({"pdf_path": pdf_path, "sha256": digest}))
        return {"version": version, "pdf_path": pdf_path, "sha256": digest}


@app.get("/api/engagements/{engagement_id}/report/{version}")
def download_report(engagement_id: int, version: int, user: dict = Depends(auth_user)) -> FileResponse:
    require_roles(user, {"admin", "auditor", "reviewer", "client_readonly"})
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM report_versions WHERE engagement_id = ? AND version_number = ?",
            (engagement_id, version),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Report version not found")
        payload = as_dict(row)
        assert payload is not None
        access_log(conn, user["id"], "export", "report", f"{engagement_id}:{version}")
    return FileResponse(payload["pdf_path"], media_type="application/pdf", filename=f"audit-{engagement_id}-v{version}.pdf")
