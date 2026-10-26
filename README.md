# FieldOps Nexus — Enterprise Asset, Maintenance & Field Service ERP
## Day-30 Checkpoint Verified Release (`HPE-PRD-2026-FOPS02`)

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](#)
[![Automated Tests](https://img.shields.io/badge/tests-713%20passed%20%7C%200%20failed-brightgreen)](#)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-5.2%20LTS-green)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-16%20relational-blue)](https://www.postgresql.org/)

---

## 1. Project Overview

**FieldOps Nexus** is a mission-critical, multi-tenant enterprise ERP platform engineered for **VPD Technologies** to manage distributed facilities, multi-tier physical equipment hierarchies, preventive maintenance recurrence, incident response, field technician dispatch, inventory parts lifecycle, customer sign-off, and compliance auditability.

### Architecture Highlights
* **Zero Mock Persistence**: Fully modeled relational persistence backed by PostgreSQL 16; zero mock endpoints or static fixture bypasses.
* **Fail-Closed Multi-Tenancy**: Organization-scoped queries enforced via custom ORM managers and `TenantContextMiddleware`.
* **Fine-Grained RBAC**: 10 enterprise personas with organization-wide and site-scoped access control.
* **Immutable Audit Trail**: Append-only audit ledger secured by PostgreSQL engine-level triggers preventing `UPDATE` and `DELETE` operations.
* **Comprehensive Automated Verification**: **713 automated tests** passing across 49 test suites (100% pass rate).

---

## 2. Integrated Enterprise Modules (M01 – M15)

1. **M01 — Site & Location Master**: Multi-tier facilities, zones, service areas, operating calendars, and contact hierarchies.
2. **M02 — Asset Registry & Hierarchy**: Equipment tree parent-child relations, technical specifications, and lifecycle states.
3. **M03 — Asset Identification**: Non-enumerable UUIDs, QR/barcode generation, label printing, and meter logging.
4. **M04 — Preventive Maintenance**: Time-based and meter-based recurrence engines, automated work order generation, and concurrency locks.
5. **M05 — Incidents & Service Requests**: Public/client intake, automated duplicate detection, triage pipeline, and work order conversion.
6. **M06 — Work Orders & Dispatch**: Complete work order state machine (`DRAFT` -> `PLANNED` -> `DISPATCHED` -> `IN_PROGRESS` -> `ON_HOLD` -> `COMPLETED` -> `SUPERVISOR_REVIEW` -> `CLOSED`), scheduling, and closure approval.
7. **M07 — Technician Workspace**: Mobile-responsive execution sheet, travel logging, labor recording, parts consumption, completion evidence, and customer digital sign-off.
8. **M08 — Checklists & Safety Inspections**: Dynamic inspection templates, scoring, photo verification, and mandatory completion gates.
9. **M09 — Inventory & Parts Requisitions**: Stock catalog, warehouse bins, stock reservations, parts issuance, and vendor receipt logging.
10. **M10 — Contracts & Coverage**: Vendor master (`ServiceProvider`), service contract management, and automated warranty/coverage checks.
11. **M11 — Service Level Agreements (SLA)**: Priority-based resolution timers and automated escalation triggers.
12. **M12 — Notifications**: In-app notification center and asynchronous Celery email delivery.
13. **M13 — Client Service Portal**: Dedicated portal dashboard, restricted asset visibility, service request tracking, and closure confirmation with star ratings.
14. **M14 — Operational Dashboards**: Real-time KPI aggregation, technician workload tracking, and MTTR/MTBF calculations.
15. **M15 — Immutable Compliance Ledger**: Tamper-proof audit logging capturing actor, timestamp, IP, before/after diffs, and site context.

---

## 3. Quickstart & Local Setup

### Option A: Docker (Recommended)
```bash
python scripts/bootstrap_env.py                      # Generates .env with secure random keys
docker compose up -d --build                         # Starts web, db (PG 16), redis, and celery
docker compose exec web python manage.py migrate     # Applies all 63 migrations
docker compose exec -e FIELDOPS_ALLOW_DEMO_SEED=true web python manage.py seed_dev_demo
```
Access the application at `http://localhost:8080/`.

### Option B: Local Python venv + PostgreSQL Container
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install pytest pytest-django pytest-cov ruff

# Launch PostgreSQL 16 container
docker run -d --name fieldops-pg -e POSTGRES_USER=fieldops -e POSTGRES_PASSWORD=fieldops -e POSTGRES_DB=fieldops -p 55432:5432 postgres:16-alpine

# Set Environment Variables
$env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'
$env:DJANGO_SECRET_KEY = 'dev-secret-key-change-in-production'
$env:DATABASE_URL = 'postgres://fieldops:fieldops@localhost:55432/fieldops'
$env:PYTHONPATH = 'src'

# Migrate, Seed, and Run
python manage.py migrate
python manage.py seed_dev_demo
python manage.py runserver 8000
```
Access the application at `http://localhost:8000/`.

---

## 4. Demo User Accounts

All seed accounts share the default password: **`FieldOps-Dev-2026!`**

| Login Email | Enterprise Role Persona | Scope & Visibility |
|---|---|---|
| `platform@fieldops.local` | Platform Super Admin | Global cross-organization administration |
| `owner@demo.local` | Organization Owner | Full tenant access across all sites and modules |
| `admin@demo.local` | Organization Admin | User management, RBAC, inventory, and facility config |
| `planner@demo.local` | Maintenance Planner | Work order planning, PM scheduling, and dispatch |
| `supervisor@demo.local` | Maintenance Supervisor | Work order review, closure approval, and site operations |
| `technician@demo.local` | Field Service Technician | Assigned work orders, travel log, parts consumption, workspace |
| `requester@demo.local` | Client Requester | Client Service Portal (`/portal/`), service request tracking |

---

## 5. Verification & Test Execution

Run the complete 713-test automated QA test suite:
```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.test'
$env:DATABASE_URL = 'postgres://fieldops:fieldops@localhost:55432/fieldops'
$env:PYTHONPATH = 'src'
python -m pytest tests/ -v
```
**Results**: `713 passed in ~4.5 minutes (100% pass rate)`.

---

## 6. Day-30 Deliverable Documentation

Detailed checkpoint documentation is located in `docs/`:
- [Requirements Traceability Matrix](docs/REQUIREMENTS_TRACEABILITY_MATRIX.md)
- [Day-30 Checkpoint Audit Report](docs/DAY30_CHECKPOINT_AUDIT_REPORT.md)
- [Actual Test Results Report](docs/DAY30_ACTUAL_TEST_RESULTS.md)
- [Open Defects Register & Resolution Log](docs/DAY30_OPEN_DEFECTS_REGISTER.md)
- [REST API Documentation](docs/DAY30_API_DOCUMENTATION.md)
- [Deployment & Setup Instructions](docs/DAY30_DEPLOYMENT_INSTRUCTIONS.md)
- [End-to-End Demo Script](docs/DAY30_END_TO_END_DEMO_SCRIPT.md)
- [Source vs Development ZIP Comparison Report](docs/DAY30_SOURCE_VS_ZIP_COMPARISON.md)
