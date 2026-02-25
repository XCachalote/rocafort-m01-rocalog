# Diseño técnico: aplicación de auditorías empresariales

## 0) Datos faltantes que impactan implementación
No se detectan bloqueos críticos para un diseño técnico base. Los siguientes puntos quedan parametrizados porque no fueron especificados:
- Umbrales numéricos exactos de aceptación por control (se configuran por plantilla de auditoría).
- Catálogo de controles por sector (se define por plantillas versionadas).
- Jurisdicción legal aplicable (el sistema permite textos legales configurables por país/cliente).

## 1) Arquitectura técnica detallada

### 1.1 Stack propuesto (concreto)
- Frontend web: React 18 + TypeScript + Vite.
- UI y gráficos: MUI 5 + ECharts.
- Gestión de estado cliente: Redux Toolkit.
- Backend API: Python 3.11 + FastAPI.
- Validación de datos: Pydantic v2.
- Base de datos transaccional: PostgreSQL 15.
- Cache y cola corta: Redis 7.
- Tareas asíncronas (PDF, firmas, notificaciones): Celery + Redis broker.
- Almacenamiento de documentos (PDF, evidencias, firmas): S3 compatible (MinIO on-prem o AWS S3).
- Identidad y autenticación fuerte: Keycloak (OIDC/OAuth2.1) con MFA TOTP/WebAuthn.
- Auditoría inmutable de eventos: tabla append-only en PostgreSQL + hash encadenado por evento.
- Observabilidad: OpenTelemetry + Prometheus + Grafana + Loki.
- Despliegue: contenedores Docker, orquestación Kubernetes.

Justificación breve:
- FastAPI + Pydantic reduce ambigüedad de contratos y permite validación fuerte.
- PostgreSQL ofrece ACID y versionado confiable para trazabilidad.
- Keycloak soporta MFA y RBAC empresarial sin desarrollo ad-hoc.
- Kubernetes permite escalado horizontal para auditorías simultáneas.

### 1.2 Componentes lógicos
1. **Módulo de autenticación y autorización**
   - Login OIDC.
   - MFA obligatorio por política.
   - RBAC por roles (Auditor, Revisor, Admin, Cliente-lectura).
2. **Módulo de gestión de auditorías**
   - Alta de empresa, alcance, equipo auditor, fechas.
   - Plantillas de controles por categoría (red/software/hardware).
3. **Módulo de captura de evidencias y respuestas**
   - Respuesta por control: cumplimiento, severidad, observación, evidencia.
   - Guardado incremental con sello temporal.
4. **Motor de scoring y riesgo**
   - Cálculo en tiempo real por categoría y global.
   - Semáforo objetivo por umbrales definidos.
5. **Dashboard en tiempo real**
   - KPIs, evolución de score, distribución de riesgo.
6. **Generador de informe PDF**
   - Render server-side con plantilla HTML/CSS + motor WeasyPrint.
   - Firma electrónica manuscrita (captura) y sello hash del documento.
7. **Trazabilidad y versionado**
   - Historial por cambio de campo.
   - Versionado de informe (v1, v2, ...).
   - Registro de accesos y acciones.

### 1.3 Arquitectura de ejecución
- Cliente React consume API REST en FastAPI.
- FastAPI escribe en PostgreSQL y publica tareas de PDF en Celery.
- Documentos y evidencias se guardan en S3 con metadatos en PostgreSQL.
- WebSocket (FastAPI) para actualizar score en dashboard en tiempo real.
- Logs y métricas centralizados para auditoría operativa.

## 2) Modelo de base de datos

### 2.1 Entidades principales
1. `users`
   - `id` (UUID, PK)
   - `full_name`
   - `email` (unique)
   - `document_id`
   - `role_id` (FK)
   - `is_active`
   - `created_at`, `updated_at`
2. `roles`
   - `id` (PK)
   - `name` (`admin`, `auditor`, `reviewer`, `client_readonly`)
3. `companies`
   - `id` (UUID, PK)
   - `legal_name`
   - `tax_identifier` (CIF/NIF u otro)
   - `full_address`
   - `contact_name`
   - `contact_email`
   - `contact_phone`
4. `audit_engagements`
   - `id` (UUID, PK)
   - `company_id` (FK)
   - `lead_auditor_id` (FK -> users)
   - `audit_date`
   - `scope_text`
   - `liability_clause_text`
   - `remote_access_consent_text`
   - `status` (`draft`, `in_progress`, `closed`)
   - `created_at`, `updated_at`
5. `control_templates`
   - `id` (UUID, PK)
   - `name`
   - `category` (`network`, `software`, `hardware`)
   - `version`
   - `is_active`
6. `controls`
   - `id` (UUID, PK)
   - `template_id` (FK)
   - `code` (ej. `NET-001`)
   - `title`
   - `description`
   - `criticality_weight` (decimal, > 0)
   - `max_score` (decimal, default 100)
7. `audit_control_results`
   - `id` (UUID, PK)
   - `engagement_id` (FK)
   - `control_id` (FK)
   - `compliance_value` (decimal 0..1)
   - `evidence_text`
   - `risk_observation`
   - `entered_by_user_id` (FK)
   - `entered_at`
   - `updated_at`
8. `audit_versions`
   - `id` (UUID, PK)
   - `engagement_id` (FK)
   - `version_number` (int)
   - `change_summary`
   - `created_by_user_id` (FK)
   - `created_at`
9. `documents`
   - `id` (UUID, PK)
   - `engagement_id` (FK)
   - `document_type` (`report_pdf`, `evidence`, `signature`)
   - `storage_uri`
   - `sha256`
   - `created_at`
10. `signatures`
   - `id` (UUID, PK)
   - `engagement_id` (FK)
   - `signer_type` (`auditor`, `legal_representative`)
   - `signer_name`
   - `signer_document_id`
   - `signature_document_id` (FK -> documents)
   - `signed_at`
11. `access_logs`
   - `id` (bigserial, PK)
   - `user_id` (FK)
   - `action` (login, read, write, export)
   - `resource_type`
   - `resource_id`
   - `ip_address`
   - `user_agent`
   - `created_at`
12. `event_audit_log` (append-only)
   - `id` (bigserial, PK)
   - `event_time`
   - `actor_user_id`
   - `entity`
   - `entity_id`
   - `operation` (insert/update/delete/export/sign)
   - `before_json`
   - `after_json`
   - `prev_event_hash`
   - `event_hash`

### 2.2 Reglas de integridad
- `criticality_weight > 0`.
- `compliance_value` restringido a `[0,1]`.
- Unicidad: (`engagement_id`, `control_id`) en `audit_control_results`.
- Unicidad: (`engagement_id`, `version_number`) en `audit_versions`.
- Bloqueo de `delete` lógico para datos de auditoría cerrada.

## 3) Flujo de funcionamiento
1. Admin crea usuarios y asigna roles.
2. Auditor crea auditoría (`audit_engagement`) con datos legales de empresa.
3. Auditor selecciona plantilla de controles por categoría.
4. Auditor registra resultados por control; cada guardado genera:
   - actualización de score en tiempo real,
   - evento en `event_audit_log`,
   - entrada de trazabilidad (`entered_by`, `entered_at`).
5. Dashboard recalcula KPIs y semáforo agregado.
6. Revisor valida y cierra auditoría.
7. Sistema genera versión de informe PDF con hash SHA-256.
8. Captura firma de auditor y representante legal.
9. Informe firmado queda versionado y descargable.
10. Cualquier modificación posterior crea nueva versión, nunca sobrescribe versión previa.

## 4) Lógica del sistema de puntuación

### 4.1 Variables definidas
Para cada control `i`:
- `c_i`: cumplimiento objetivo en rango `[0,1]`.
- `w_i`: peso por criticidad (`w_i > 0`).
- `m_i`: puntuación máxima del control (por defecto 100).

Puntuación normalizada de control:
- `s_i = c_i * m_i`

Puntuación ponderada por control:
- `p_i = s_i * w_i`

Puntuación de categoría `k` (network/software/hardware):
- `Score_k = (sum(p_i en k) / sum(m_i * w_i en k)) * 100`

Puntuación global:
- `Score_global = (sum(p_i total) / sum(m_i * w_i total)) * 100`

### 4.2 Riesgo agregado (cuantificable)
Se define índice de riesgo inverso al cumplimiento:
- `Risk_global = 100 - Score_global`

### 4.3 Semáforo (criterio objetivo)
- **Verde (Cumple)**: `Score_global >= 85`
- **Amarillo (Riesgo Medio)**: `70 <= Score_global < 85`
- **Rojo (Acción Correctiva Urgente)**: `Score_global < 70`

Regla de severidad crítica adicional (objetiva):
- Si existe al menos un control con `w_i >= 2.0` y `c_i < 0.5`, estado mínimo permitido = Rojo.

Nota:
- Los umbrales (85/70) quedan como parámetros de política en tabla de configuración y deben aprobarse por gobierno de auditoría.

## 5) Estructura del dashboard

### 5.1 Panel superior (KPIs)
- Score global (%) en tiempo real.
- Riesgo global (%).
- Semáforo actual.
- Total de controles evaluados / pendientes.

### 5.2 Sección por categorías
- Tarjeta Red: score, riesgo, controles críticos fallidos.
- Tarjeta Software: score, riesgo, controles críticos fallidos.
- Tarjeta Hardware: score, riesgo, controles críticos fallidos.

### 5.3 Visualizaciones
- Gráfico radial por categoría (`Score_k`).
- Serie temporal de evolución del `Score_global`.
- Tabla de controles con filtros (categoría, criticidad, estado).

### 5.4 Eventos y trazabilidad visible
- Timeline de cambios (usuario, fecha/hora, campo modificado).
- Última versión del informe y hash.

## 6) Estructura del PDF

### 6.1 Portada
- Nombre completo de la empresa auditada.
- CIF/NIF o identificador fiscal.
- Dirección completa.
- Persona de contacto.
- Fecha de auditoría.
- Nombre completo del auditor.
- Documento identificativo del auditor.
- ID y versión del informe.

### 6.2 Cuerpo técnico
1. Alcance de auditoría (texto cerrado de la auditoría).
2. Metodología aplicada (plantilla y versión de controles).
3. Resultados por categoría con métricas cuantificables.
4. Score global, riesgo global y semáforo.
5. Hallazgos críticos y acciones correctivas propuestas.

### 6.3 Sección legal y consentimiento
- Consentimiento explícito firmado para acceso remoto a sistemas.
- Cláusula de limitación de responsabilidad.
- Referencia de tratamiento de datos (texto configurable por jurisdicción).

### 6.4 Firmas
- Firma del auditor (nombre, documento, fecha/hora).
- Firma del representante legal (nombre, documento, fecha/hora).
- Hash SHA-256 del PDF para verificación de integridad.

## 7) Riesgos técnicos y legales identificados

### 7.1 Técnicos
- Riesgo de inconsistencia si se permite edición concurrente sin control de versión optimista.
  - Mitigación: `row_version` + rechazo de escrituras conflictivas.
- Riesgo de manipulación de evidencias si no se verifica integridad.
  - Mitigación: hash SHA-256 por archivo + almacenamiento WORM cuando aplique.
- Riesgo de pérdida de trazabilidad por borrado físico.
  - Mitigación: append-only log + retención obligatoria.

### 7.2 Seguridad
- Riesgo de acceso no autorizado a datos sensibles.
  - Mitigación: MFA, RBAC estricto, cifrado TLS 1.2+ y AES-256 en reposo.
- Riesgo por exposición de firmas/documentos.
  - Mitigación: URLs prefirmadas de corta duración y control de descarga por rol.

### 7.3 Legales (explícitos)
- Riesgo legal por acceso remoto sin consentimiento válido.
  - Control obligatorio: consentimiento explícito firmado previo al acceso.
- Riesgo legal por tratamiento de datos personales sin base documentada.
  - Control obligatorio: registro de finalidad, minimización de datos y retención definida.
- Riesgo contractual por interpretación ambigua del alcance.
  - Control obligatorio: alcance delimitado en informe y aceptación firmada.

## 8) Limitaciones del sistema
- El motor no sustituye juicio profesional del auditor; cuantifica controles definidos.
- La calidad del resultado depende de la calidad de evidencias cargadas.
- Sin catálogo sectorial validado, la cobertura de controles puede ser incompleta.
- La validez legal de firma electrónica depende del método de firma y jurisdicción configurada.
- Operación offline no incluida en esta versión base (requiere diseño de sincronización diferida).
