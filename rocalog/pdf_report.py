from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generate_report_pdf(
    output_path: Path,
    engagement: dict,
    controls: Iterable[dict],
    score_summary: dict,
    signatures: list[dict],
) -> tuple[str, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    y = 28 * cm

    def write(line: str, step: float = 0.7):
        nonlocal y
        c.drawString(2 * cm, y, line)
        y -= step * cm

    write("INFORME DE AUDITORÍA", 1.0)
    write(f"Empresa: {engagement['company_name']}")
    write(f"CIF/NIF: {engagement['tax_identifier']}")
    write(f"Dirección: {engagement['full_address']}")
    write(f"Persona de contacto: {engagement['contact_person']}")
    write(f"Auditor: {engagement['auditor_name']} ({engagement['auditor_document_id']})")
    write(f"Fecha de auditoría: {engagement['audit_date']}")
    write(f"Puntuación global: {score_summary['score_global']}%")
    write(f"Riesgo global: {score_summary['risk_global']}%")
    write(f"Semáforo: {score_summary['semaphore']}")
    write(" ")
    write("ALCANCE")
    write(engagement["scope_text"])
    write("LIMITACIÓN DE RESPONSABILIDAD")
    write(engagement["liability_clause_text"])
    write("CONSENTIMIENTO ACCESO REMOTO")
    write(engagement["remote_access_consent_text"])

    y -= 0.4 * cm
    write("RESULTADOS DE CONTROLES", 0.9)
    for ctrl in controls:
        write(f"- [{ctrl['category']}] {ctrl['code']} {ctrl['title']} | cumplimiento={ctrl['compliance_value']}")
        if y < 3 * cm:
            c.showPage()
            y = 28 * cm

    write("FIRMAS", 0.9)
    for sig in signatures:
        write(
            f"{sig['signer_type']}: {sig['signer_name']} ({sig['signer_document_id']}) - {sig['signed_at']} - firma: {sig['signature_text']}"
        )

    c.save()
    payload = output_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    return str(output_path), digest
