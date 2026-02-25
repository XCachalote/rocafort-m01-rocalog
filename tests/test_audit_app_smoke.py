import importlib.util
import tempfile
import unittest
from pathlib import Path

FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None
PYOTP_AVAILABLE = importlib.util.find_spec("pyotp") is not None

if FASTAPI_AVAILABLE and PYOTP_AVAILABLE:
    import pyotp
    from fastapi.testclient import TestClient

    from rocalog import audit_storage
    from rocalog.audit_app import app


@unittest.skipUnless(FASTAPI_AVAILABLE and PYOTP_AVAILABLE, "fastapi/pyotp not installed in environment")
class TestAuditAppSmoke(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        audit_storage.DB_PATH = Path(self.tmpdir.name) / "audit.db"
        audit_storage.init_db()
        self.client = TestClient(app)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_login_dashboard_flow(self):
        with audit_storage.get_conn() as conn:
            admin = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
            secret = admin["totp_secret"]

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "admin1234",
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]

        engagement = self.client.post(
            "/api/engagements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "company_name": "ACME SA",
                "tax_identifier": "A00000000",
                "full_address": "Calle Falsa 123",
                "contact_person": "Ana",
                "auditor_name": "Luis",
                "auditor_document_id": "X123",
                "audit_date": "2026-02-25",
                "scope_text": "Alcance técnico",
                "liability_clause_text": "Limitación estándar",
                "remote_access_consent_text": "Consentimiento explícito",
            },
        )
        self.assertEqual(engagement.status_code, 200)
        eid = engagement.json()["engagement_id"]

        control = self.client.post(
            f"/api/engagements/{eid}/controls",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "category": "network",
                "code": "NET-001",
                "title": "Firewall",
                "criticality_weight": 1.5,
                "max_score": 100,
                "compliance_value": 0.9,
                "evidence_text": "Reglas revisadas",
                "risk_observation": "Bajo",
            },
        )
        self.assertEqual(control.status_code, 200)

        dashboard = self.client.get(
            f"/api/engagements/{eid}/dashboard",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("score", dashboard.json())


if __name__ == "__main__":
    unittest.main()
