# Financial SaaS Backend

Modular Monolith backend for Contractor Financial SaaS, providing single-input double-entry accounting, project financial tracking, and review queue workflows.

## Development Setup

### 1. Create and activate a virtual environment

```bash
cd backend
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (cmd):
.venv\Scripts\activate.bat

# Linux/macOS:
source .venv/bin/activate
```

### 2. Install dependencies (including development and test tools)

```bash
pip install -e ".[dev]"
```

### 3. Run tests

```bash
python -m pytest -v
```
