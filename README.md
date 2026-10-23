# FieldOps Nexus — Enterprise Asset, Maintenance & Field Service ERP

[![CI Pipeline](https://img.shields.io/badge/CI-passing-brightgreen)](#7-automated-testing--verification-baseline)
[![Tests](https://img.shields.io/badge/tests-165%20passed-brightgreen)](#7-automated-testing--verification-baseline)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-5.2%20LTS-green)](https://www.djangoproject.com/)

---

## 1. Project Overview

**FieldOps Nexus** is a modular, multi-tenant enterprise ERP platform built for managing distributed facilities, physical equipment hierarchies, preventive maintenance, incident response, field technician dispatch, inventory, and compliance auditability.

### Core Architecture Highlights
* **Multi-Tenant Isolation**: Strict fail-closed organization boundary enforcement at the database and ORM query level.
* **Fine-Grained RBAC**: 10 enterprise role personas with organization-wide and site-scoped permissions.
* **Immutable Auditing**: Append-only audit ledger secured by PostgreSQL engine-level triggers preventing update and delete operations.
* **Zero Mock Persistence**: Fully modeled relational persistence using Django ORM and PostgreSQL; no mock endpoints or static fixtures.

---

## 2. Technical Stack

* **Backend Framework**: Python 3.11+, Django 5.2 LTS, Django REST Framework (DRF)
* **Database**: PostgreSQL 15+ (Production/Staging on PostgreSQL; containerized PostgreSQL 16 for local execution)
* **Broker & Cache**: Redis 7+ for caching, Celery task broker, and distributed locks
* **Asynchronous Workers**: Celery 5+ (background tasks, notifications, session maintenance)
* **Frontend Design System**: Server-rendered Django Templates + HTMX + vendor-pinned Bootstrap 5 (zero external runtime CDNs)
* **Security & Auth**: `django-axes` brute-force lockout, rate-limiting, CSP, CSRF, and `bandit` AST security validation
* **API Documentation**: OpenAPI / Swagger (`/api/v1/docs/`)

---

## 3. System Architecture & Implemented Modules

### 3.1 Tenancy & Identity Core
* `Organization`: Corporate tenant entity with lifecycle states (`ACTIVE`, `SUSPENDED`).
* `OrganizationMembership`: Maps user accounts to organizations with status tracking (`INVITED`, `ACTIVE`, `SUSPENDED`).
* `User`: Global user identity with non-enumerable UUIDv4 identifiers.
* `TenantContextMiddleware`: Ensures all tenant-scoped queries are fail-closed.

### 3.2 Role-Based Access Control (RBAC)
* Declarative permission catalog (`apps.rbac.catalog`) covering all modules.
* 10 standard role personas:
  * **Platform Super Admin**: Platform console operations (`/platform/`).
  * **Organization Owner**: Full tenant administration (`is_owner=True`).
  * **Asset Manager**: Asset catalog and physical structure mapping.
  * **Maintenance Planner**: Operating schedules, shifts, and PM plans.
  * **Service Dispatcher**: Work order assignment and route tracking.
  * **Field Technician**: Mobile job execution, checklist completion, and labor logs.
  * **Supervisor**: Quality verification, approvals, and SLA compliance.
  * **Stores Manager**: Warehouse inventory, stock issues, and reservations.
  * **Service Manager**: SLA governance and contract oversight.
  * **Client / Requester**: Self-service portal request submission.
  * **Auditor**: Read-only compliance review and audit logs export.
* **Site Scoping**: Roles can be constrained to specific physical sites (`MembershipRole.site`).

### 3.3 Site & Location Master (M01)
* `Site`: Physical facility/campus with unique code, timezone, and operational status (`ACTIVE`, `INACTIVE`).
* `BuildingZone`: Hierarchical zones (`BUILDING`, `ZONE`, `SERVICE_AREA`) with tree validation (maximum depth 6).
* `SiteOperatingCalendar` & `CalendarHoliday`: Operational calendars defining working days and hours.
* `SiteContact`: Escalation contact directory unique per site.

### 3.4 Unified Shell & Portals
* **Operations Shell**: Server-rendered responsive layout (`shell.html`) with organization switcher, search, and notification bell.
* **Client / Requester Portal**: Isolated portal area (`/app/portal/`) for external requesters.
* **Technician Workspace**: Mobile-optimized field execution workspace (`/app/workspace/`).

---

## 4. Database Schema & Initial Migrations

All database tables are managed through automated Django migrations:

| Module App | Migration | Key Entities |
| :--- | :--- | :--- |
| `apps.core` | `0001_initial` | `DocumentSequence` (gap-free numbering) |
| `apps.tenancy` | `0001_initial` | `Organization`, `OrganizationMembership` |
| `apps.accounts` | `0001_initial` | `User`, `TechnicianProfile` |
| `apps.rbac` | `0001_initial`<br>`0002_membership_role_site_scope` | `Role`, `Permission`, `RolePermission`, `MembershipRole` |
| `apps.sites` | `0001_initial` | `Site`, `BuildingZone`, `SiteOperatingCalendar`, `CalendarHoliday`, `SiteContact` |
| `apps.files` | `0001_initial` | `Attachment` (content storage, hash verification, access registry) |
| `apps.notifications` | `0001_initial` | `Notification` (in-app notification delivery) |
| `apps.audit` | `0001_initial`<br>`0002_auditlog_immutable_trigger`<br>`0003_auditlog_site_id_and_more` | `AuditLog` (append-only ledger, DB trigger immutability) |

---

## 5. Quickstart & Local Setup

### Option A: Docker Compose (Recommended)

```bash
# 1. Bootstrap environment variables with secure random secrets
python scripts/bootstrap_env.py

# 2. Build and run containers (web, celery worker, redis, postgres)
docker compose up -d --build

# 3. Seed initial development tenant data
docker compose exec -e FIELDOPS_ALLOW_DEMO_SEED=true web python manage.py seed_dev_demo
```

Access the application at `http://localhost:8080/accounts/login/`.

#### Pre-Configured Demo Credentials:
Local development password: `FieldOps-Dev-2026!`

| Email | Role | Initial View |
| :--- | :--- | :--- |
| `platform@fieldops.local` | Platform Super Admin | `/platform/` (Platform Console) |
| `owner@demo.local` | Org Owner | `/app/` (Operations Console) |
| `admin@demo.local` | Tenant Admin | `/app/sites/` (Site & Location Master) |
| `supervisor@demo.local`| Supervisor | `/app/sites/` (Site & Team Oversight) |
| `technician@demo.local`| Field Technician | `/app/workspace/` (Technician Workspace) |

API Documentation (Swagger): `http://localhost:8080/api/v1/docs/`

---

### Option B: Local Virtual Environment

```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r requirements.lock pytest pytest-django pytest-cov ruff bandit

# 3. Start PostgreSQL container
docker run -d --name fieldops-pg -e POSTGRES_USER=fieldops -e POSTGRES_PASSWORD=fieldops -e POSTGRES_DB=fieldops -p 55432:5432 postgres:16-alpine

# 4. Set environment and apply migrations
export DJANGO_SETTINGS_MODULE=config.settings.dev
export DJANGO_SECRET_KEY=dev-only-secret
export DATABASE_URL=postgres://fieldops:fieldops@localhost:55432/fieldops
export PYTHONPATH=src

python manage.py migrate
python manage.py seed_dev_demo
python manage.py runserver 8000
```

---

## 6. Staging Deployment

The application supports staging deployment with PostgreSQL and background workers:

1. **Bootstrap Staging Secrets**:
   ```bash
   python scripts/bootstrap_prod_env.py
   ```
2. **Provision Database Roles & Schema**:
   ```bash
   python scripts/provision_supabase.py
   python scripts/harden_db_roles.py
   ```
3. **Execute Migrations against Staging**:
   ```bash
   python manage.py migrate --settings=config.settings.prod
   ```

Detailed configuration options are available in [Deployment Guide](docs/DEPLOYMENT.md).

---

## 7. Automated Testing & Verification Baseline

All code modifications are verified against automated test suites and security scans:

```bash
# 1. Linting and formatting
ruff check src tests
ruff format --check src tests

# 2. Static application security testing (AST)
bandit -r src -ll --skip B101,B104,B311

# 3. Migration consistency verification (zero drift)
python manage.py makemigrations --check --dry-run

# 4. Execute test suite (165 tests)
pytest -q
```

---

## 8. Documentation Index

* [Requirement Understanding](docs/REQUIREMENT_UNDERSTANDING.md) — Comprehensive functional requirements, architecture scope, and domain principles
* [Authentication & RBAC Foundation](docs/AUTH_RBAC_FOUNDATION.md) — Multi-tenant identity, 10 role personas, site scoping, and security controls
* [Continuous Integration (CI) Baseline](docs/CI_BASELINE.md) — CI/CD pipelines, linting, security scans, and migration verification
* [Architecture Documentation](docs/ARCHITECTURE.md) — System layers, request pipeline, and tenancy design
* [Architecture Decisions (ADR)](docs/DECISIONS.md) — Architectural decision log and rationale
* [Domain Model Reference](docs/DOMAIN_MODEL.md) — Entity models, constraints, and relationships
* [Entity Relationship Diagram (ERD)](docs/ERD.md) — Visual relational diagram and entity dictionary
* [Master Business Workflow](docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md) — Operational business workflows
* [Deployment Guide](docs/DEPLOYMENT.md) — Environment setup and production hardening
* [Unit Test Reports](docs/testing/M01_UNIT_TESTS.md) — Unit testing execution report
* [Integration Test Reports](docs/testing/M01_INTEGRATION_TESTS.md) — Integration testing execution report
* [Regression Test Reports](docs/testing/M01_REGRESSION_TESTS.md) — Regression test suite report
