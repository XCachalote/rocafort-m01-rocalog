# RocaLog

RocaLog es un proyecto Python 3.11 para analizar logs tipo `auth.log` y detectar intentos de acceso SSH con `Failed password`.

## Estructura del proyecto

```text
.
├── data/
│   └── sample_auth.log
├── rocalog/
│   ├── __init__.py
│   ├── cli.py
│   └── parser.py
├── tests/
│   ├── test_cli_smoke.py
│   └── test_parser.py
├── tools/
│   └── lint.py
├── pyproject.toml
└── README.md
```

## Requisitos

- Python 3.11+
- Sin dependencias externas en runtime

## Instalación / setup (equivalente a `npm ci`)

```bash
git clone https://github.com/ivanglpx/rocafort-m01-rocalog.git
cd rocafort-m01-rocalog
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
```

## Ejecución CLI

```bash
python3 -m rocalog.cli --file data/sample_auth.log --json
```

## Tests (equivalente a `npm test`)

```bash
python3 -m unittest discover -s tests -v
```

## Lint básico

```bash
python3 tools/lint.py
```

El lint valida sintaxis Python (`py_compile`) en el paquete, tests y herramientas.
