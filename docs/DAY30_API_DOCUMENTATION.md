# FieldOps Nexus — REST API Documentation
## API Version: `v1` (Base URL: `/api/v1/`)

FieldOps Nexus provides a modular, multi-tenant, versioned REST API. All endpoints enforce strict tenant isolation and permission checks.

Interactive documentation:
- **Swagger UI**: `/api/v1/docs/`
- **ReDoc**: `/api/v1/redoc/`
- **OpenAPI Schema**: `/api/v1/schema/`

---

## 1. Authentication & Security Headers

### Bearer Token Authentication (JWT)
1. Obtain token pair:
   - `POST /api/v1/auth/token/`
   - Request Body: `{"email": "user@example.com", "password": "SecretPassword!"}`
   - Response: `{"access": "<JWT>", "refresh": "<JWT>"}`
2. Include in all subsequent requests:
   - Header: `Authorization: Bearer <access_token>`

### Session Authentication (CSRF)
For browser-based sessions, standard Django session cookies are accepted. Mutation requests (`POST`, `PUT`, `PATCH`, `DELETE`) require the `X-CSRFToken` header.

### Multi-Tenant Scope Header (Optional)
If a user belongs to multiple organizations, they can explicitly scope their API requests:
- Header: `X-Organization-Id: <UUID>`

---

## 2. API Endpoints by Domain

### 2.1 Core Health & Diagnostics
- `GET /health/live/` — Liveness probe (HTTP 200 OK)
- `GET /health/ready/` — Readiness probe (validates PostgreSQL DB and Redis cache connectivity)

### 2.2 Sites & Facility Structure (M01)
- `GET /api/v1/sites/` — List accessible sites (supports search, status filtering, pagination)
- `POST /api/v1/sites/` — Create new site (`site.create`)
- `GET /api/v1/sites/{id}/` — Retrieve site details
- `PATCH /api/v1/sites/{id}/` — Update site (`site.manage`)
- `GET /api/v1/sites/{id}/locations/` — Retrieve hierarchical location tree (buildings, zones)

### 2.3 Asset Management & Equipment Trees (M02 / M03)
- `GET /api/v1/assets/` — List assets (supports site, category, status, and tag filtering)
- `POST /api/v1/assets/` — Register equipment (`asset.create`)
- `GET /api/v1/assets/{id}/` — Retrieve asset details and specifications
- `PATCH /api/v1/assets/{id}/` — Update asset attributes (`asset.manage`)
- `GET /api/v1/assets/{id}/hierarchy/` — View parent-child equipment relationships
- `POST /api/v1/assets/{id}/meter/` — Log meter readings (`meter.record`)

### 2.4 Preventive Maintenance & Recurrence (M04)
- `GET /api/v1/maintenance-plans/` — List preventive maintenance plans
- `POST /api/v1/maintenance-plans/` — Create maintenance plan (`maintenance.plan`)
- `GET /api/v1/maintenance-schedules/` — List schedules (time-based & meter-based)
- `POST /api/v1/maintenance-schedules/{id}/generate/` — Trigger work order generation (`maintenance.schedule`)

### 2.5 Incidents & Service Requests (M05)
- `GET /api/v1/incidents/` — List service requests and incidents
- `POST /api/v1/incidents/` — Report an incident (`incident.create` or `incident.report_owned`)
- `GET /api/v1/incidents/{id}/` — Retrieve incident detail
- `POST /api/v1/incidents/{id}/triage/` — Triage request (`incident.triage`)
- `POST /api/v1/incidents/{id}/convert-work-order/` — Convert approved request to work order (`work_order.create`)

### 2.6 Work Orders & Field Dispatch (M06)
- `GET /api/v1/work-orders/` — List work orders (filters: status, priority, site, assignee)
- `POST /api/v1/work-orders/` — Create work order (`work_order.create`)
- `GET /api/v1/work-orders/{id}/` — Retrieve work order details
- `POST /api/v1/work-orders/{id}/plan/` — Schedule start/end dates and hours (`work_order.plan`)
- `POST /api/v1/work-orders/{id}/dispatch/` — Dispatch to technician (`work_order.dispatch`)
- `POST /api/v1/work-orders/{id}/transition/` — Execute status transitions (`work_order.start`, `work_order.complete`)
- `GET /api/v1/work-orders/{id}/closure/` — Check closure blockers (`work_order.view`)
- `POST /api/v1/work-orders/{id}/review/` — Supervisor review and closure approval (`work_order.close`)

### 2.7 Technician Workspace (M07)
- `GET /api/v1/workspace/jobs/` — List jobs assigned to calling technician
- `GET /api/v1/workspace/jobs/{id}/` — Detailed job execution sheet
- `GET /api/v1/workspace/jobs/{id}/drawer/` — Summary metrics for mobile drawer
- `POST /api/v1/workspace/jobs/{id}/start/` — Start execution (`DISPATCHED` -> `IN_PROGRESS`)
- `POST /api/v1/workspace/jobs/{id}/pause/` — Pause job with mandatory hold reason
- `POST /api/v1/workspace/jobs/{id}/resume/` — Resume execution
- `POST /api/v1/workspace/jobs/{id}/travel/` — Log travel hours, distance km, and route details
- `POST /api/v1/workspace/jobs/{id}/labor/` — Record technician labor hours
- `POST /api/v1/workspace/jobs/{id}/materials/` — Record ad-hoc materials used
- `POST /api/v1/workspace/jobs/{id}/parts/consume/` — Mark issued inventory parts as consumed
- `POST /api/v1/workspace/jobs/{id}/evidence/` — Upload completion photos and test documents
- `POST /api/v1/workspace/jobs/{id}/complete/` — Complete job (supports customer digital signature)

### 2.8 Checklists & Safety Inspections (M08)
- `GET /api/v1/checklists/templates/` — List checklist templates
- `POST /api/v1/checklists/templates/` — Create inspection template (`inspection.manage`)
- `GET /api/v1/checklists/inspections/` — List inspections
- `POST /api/v1/checklists/inspections/` — Start inspection on work order (`inspection.execute`)
- `POST /api/v1/checklists/inspections/{id}/submit/` — Submit completed inspection with scoring

### 2.9 Inventory & Parts Management (M09)
- `GET /api/v1/inventory/items/` — List catalog items and stock levels
- `POST /api/v1/inventory/items/` — Create inventory item (`inventory.manage`)
- `GET /api/v1/inventory/warehouses/` — List warehouses and stock bins
- `POST /api/v1/inventory/work-orders/{wo_id}/parts/` — Request part line (`inventory.request`)
- `POST /api/v1/inventory/work-orders/{wo_id}/parts/{id}/reserve/` — Reserve stock (`inventory.manage`)
- `POST /api/v1/inventory/work-orders/{wo_id}/parts/{id}/issue/` — Issue part to technician (`inventory.manage`)

### 2.10 Client Service Portal (M13)
- `GET /api/v1/portal/me/` — Portal account profile and permissions
- `GET /api/v1/portal/requests/` — List client-owned requests
- `POST /api/v1/portal/requests/` — Submit new service request
- `GET /api/v1/portal/requests/{id}/` — Track request status and technician dispatch
- `POST /api/v1/portal/requests/{id}/confirm-closure/` — Client satisfaction signoff and rating (1–5)
- `POST /api/v1/portal/requests/{id}/reopen/` — Reopen unsatisfied resolved request

### 2.11 Immutable Audit Ledger (M15)
- `GET /api/v1/audit/` — Search audit records (`audit.view`)
- `GET /api/v1/audit/{id}/` — Retrieve full event record with before/after state diff

---

## 3. Standard Response Formats & Error Handling

### Standard Success Response
```json
{
  "message": "Operation completed successfully.",
  "data": { ... }
}
```

### Standard Error Response (HTTP 400 / 403 / 404 / 409)
```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to execute this transition at this site.",
    "details": {}
  }
}
```
