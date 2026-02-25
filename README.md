# RocaLog

RocaLog incluye dos capacidades:

1. CLI Python 3.11 para analizar logs tipo `auth.log` y detectar intentos `Failed password`.
2. Aplicación web/API `RocaAudit` para auditorías empresariales con dashboard, scoring, trazabilidad y PDF.

## Estructura del proyecto

```text
.
├── data/
│   └── sample_auth.log
├── docs/
│   └── diseno-aplicacion-auditorias.md
├── rocalog/
│   ├── __init__.py
│   ├── audit_app.py
│   ├── audit_storage.py
│   ├── cli.py
│   ├── parser.py
│   ├── pdf_report.py
│   └── scoring.py
├── tests/
│   ├── test_audit_app_smoke.py
│   ├── test_cli_smoke.py
│   ├── test_parser.py
│   └── test_scoring.py
├── tools/
│   └── lint.py
├── pyproject.toml
└── README.md
```

## Requisitos

- Python 3.11+

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
```

## Ejecución CLI de logs

```bash
python3 -m rocalog.cli --file data/sample_auth.log --json
```

## Ejecución app de auditorías

```bash
uvicorn rocalog.audit_app:app --reload
```

- API docs: `http://127.0.0.1:8000/docs`
- Dashboard HTML: `http://127.0.0.1:8000/dashboard/{engagement_id}`

### Credenciales iniciales (entorno local)
- Usuario: `admin`
- Password: `admin1234`
- MFA TOTP: secreto generado en la tabla `users` al inicializar DB.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Lint básico

```bash
python3 tools/lint.py
```
