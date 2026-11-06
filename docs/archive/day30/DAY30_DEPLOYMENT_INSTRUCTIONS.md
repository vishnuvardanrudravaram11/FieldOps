# FieldOps Nexus — Deployment & Setup Guide
## Day-30 Release & Environment Setup

This guide provides step-by-step instructions for configuring, deploying, and validating FieldOps Nexus.

---

## 1. Prerequisites

- **Python**: 3.11 or 3.12 (tested on 3.12.10)
- **Database**: PostgreSQL 15+ (tested on PostgreSQL 16)
- **Cache/Broker**: Redis 7+
- **Docker**: Docker Desktop / Docker Engine (optional, for containerized run)

---

## 2. Option A: Containerized Deployment (Recommended for Quickstart)

1. **Bootstrap Environment Secrets**:
   ```bash
   python scripts/bootstrap_env.py
   ```
   This generates a secure `.env` file with unique secret keys and DB credentials.

2. **Build and Launch Containers**:
   ```bash
   docker compose up -d --build
   ```
   Services launched:
   - `web`: Django application (Gunicorn) on port `8080`
   - `db`: PostgreSQL 16 on port `5432`
   - `redis`: Redis 7 on port `6379`
   - `celery_worker`: Asynchronous background task consumer
   - `celery_beat`: Periodic scheduler (PM generation, reminder tasks)

3. **Apply Database Migrations & Seed Demo Data**:
   ```bash
   docker compose exec web python manage.py migrate
   docker compose exec -e FIELDOPS_ALLOW_DEMO_SEED=true web python manage.py seed_dev_demo
   ```

4. **Verify Application Health**:
   - Web UI: `http://localhost:8080/accounts/login/`
   - Health Probes: `http://localhost:8080/health/live/` and `http://localhost:8080/health/ready/`

---

## 3. Option B: Local Development Setup (Python venv + PostgreSQL Container)

1. **Create and Activate Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Locked Dependencies**:
   ```powershell
   pip install -r requirements.lock
   pip install pytest pytest-django pytest-cov ruff
   ```

3. **Start PostgreSQL Test Database Container**:
   ```powershell
   docker run -d --name fieldops-pg -e POSTGRES_USER=fieldops -e POSTGRES_PASSWORD=fieldops -e POSTGRES_DB=fieldops -p 55432:5432 postgres:16-alpine
   ```

4. **Configure Environment Variables**:
   ```powershell
   $env:DJANGO_SETTINGS_MODULE = 'config.settings.dev'
   $env:DJANGO_SECRET_KEY = 'dev-secret-key-change-in-production'
   $env:DATABASE_URL = 'postgres://fieldops:fieldops@localhost:55432/fieldops'
   $env:PYTHONPATH = 'src'
   ```

5. **Execute Migrations & Seed Data**:
   ```powershell
   python manage.py migrate
   python manage.py seed_dev_demo
   ```

6. **Start Django Development Server**:
   ```powershell
   python manage.py runserver 8000
   ```
   Access the application at `http://localhost:8000/`.

---

## 4. Production Deployment Best Practices

1. **Secret Key & Host Protection**:
   - `DJANGO_SECRET_KEY`: Never commit secrets to source control. Inject via vault or container runtime.
   - `DJANGO_ALLOWED_HOSTS`: Set strictly to your production domain (e.g., `erp.vpdtechnologies.com`).
   - `DJANGO_CSRF_TRUSTED_ORIGINS`: Set to `https://erp.vpdtechnologies.com`.

2. **Static Asset Pipeline**:
   - Static files are bundled using Whitenoise with Brotli/Gzip compression.
   - Execute before starting:
     ```bash
     python manage.py collectstatic --noinput
     ```

3. **Database Security & Immutability**:
   - The PostgreSQL user should own the schema.
   - Migration `0002_audit_immutable_trigger.py` automatically binds an engine-level PL/pgSQL trigger to table `audit_auditlog` prohibiting `UPDATE` and `DELETE` operations.

4. **Worker Processes**:
   - Always run Celery workers for email dispatch and audit serialization:
     ```bash
     celery -A config worker -l INFO
     celery -A config beat -l INFO
     ```
