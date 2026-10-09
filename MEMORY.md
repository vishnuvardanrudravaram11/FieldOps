# MEMORY.md — FieldOps Nexus Enterprise Master Specification & Agent Memory

> **System Memory Document**: Single Source of Truth for Autonomous Agents, Code Generators & Engineering Teams.  
> **Mandate**: Every AI agent, IDE assistant, and developer **MUST** inspect and analyze this document before making any architectural, database, backend, or UI decisions in this repository.  
> **Status**: Approved Specification Baseline  

---

## 1. System Vision & Non-Negotiable Engagement Mandate

**FieldOps Nexus** is an enterprise-grade Asset Lifecycle, Maintenance, and Field Service Operations ERP. It is engineered for multi-site industrial facilities, equipment fleets, service organizations, and distributed field technicians.

### Non-Negotiable Core Directives:
1. **Extend, Do Not Recreate**: The existing repository foundation must be extended incrementally. Never re-scaffold or rewrite the project.
2. **Real PostgreSQL Persistence Only**: Every UI control, button, form, filter, export, and status update must execute real database transactions.
3. **Zero Fake Functionality (Immediate Rejection Trigger)**:
   - No hardcoded mock screens, demo-only views, or simulated JSON payloads.
   - No frontend-only validation or fake success alerts.
   - No UI buttons that do not trigger persistent server-side actions.
4. **Backend-Enforced RBAC**: Authorization and state machine transitions must be strictly validated in Django/DRF service layers. Hiding buttons on the frontend is not security.
5. **No Secrets in Source Control**: All configuration secrets must be loaded via environment variables from `.env`. Never commit secrets to Git.

---

## 2. 15 Core Functional Modules & Functional Scope

| # | Module Name | Required Functional Scope |
| :--- | :--- | :--- |
| **01** | **Site & Location Master** | Multi-tenant organizations, sites, buildings, zones/floors, service areas, operating calendars, and contact hierarchy. |
| **02** | **Asset Registry** | Unique Asset ID, category, make/model, serial number, commission dates, site/zone location, custodian/owner, warranty status, and technical attachments. |
| **03** | **Asset Hierarchy** | Parent-child assemblies, sub-assemblies, replaceable components, and relationship dependency tree. |
| **04** | **Preventive Maintenance (PM)** | Time-based and meter/telemetry-based maintenance plans, recurring job generation via Celery Beat, checklist bindings, maintenance windows, and advance reminders. |
| **05** | **Incident & Breakdown** | Failure reporting, severity levels, photo/document uploads, asset linkage, downtime start/stop timestamps, and operational impact tracking. |
| **06** | **Work Order Management** | Work order lifecycle (create, prioritize, assign, dispatch, hold, complete, close) with captured labor hours, material costs, and time logs. |
| **07** | **Technician Workspace** | Mobile-first field engineer view: assigned job queue, site navigation, step-by-step checklist execution, notes, photo evidence, parts usage, clock-in/clock-out, and digital signature signoff. |
| **08** | **Inspection & Checklist Engine** | Template-driven safety, quality, and maintenance checklists with mandatory verification fields, numeric bounds, and exception/finding flags. |
| **09** | **Spare Parts & Inventory** | Multi-warehouse stock tracking, technician van inventory, part reservation, stock issues, returns, min/max reorder thresholds, and consumption against work orders. |
| **10** | **Warranty, AMC & Contracts** | Coverage terms, service providers, SLA contracts, exclusions, warranty expiration alerts, renewal workflows, and eligible claim validation. |
| **11** | **SLA & Escalation Engine** | Response time and resolution time targets categorized by priority, automated breach detection, real-time countdowns, and multi-tier supervisor escalation alerts. |
| **12** | **QR / Barcode Identification** | Generation and scanning of opaque, non-sensitive asset identifiers to immediately load asset context or log a service ticket. |
| **13** | **Client / Requester Portal** | Authenticated client portal to submit service requests, view live job progress, review technician visit dates, and provide completion confirmation. |
| **14** | **Operational Dashboards** | Real-time analytics: Mean Time Between Failures (MTBF), Mean Time to Repair (MTTR), asset downtime, technician utilization, SLA breach rates, PM compliance %, and parts consumption. |
| **15** | **Audit & Compliance** | Immutable transactional audit logs, closure approvals, state transition history, CSV/PDF evidence exports, and role-controlled compliance reporting. |

---

## 3. Mandatory Operational State Machines

All state transitions must be enforced via backend service validators with complete audit trails. Direct uncontrolled database updates bypassing the state machine are prohibited.

### A. Service Request Workflow
```
NEW -> TRIAGED -> APPROVED / REJECTED -> WORK ORDER CREATED -> IN SERVICE -> RESOLVED -> CONFIRMED -> CLOSED
```
- `TRIAGED`: Operations reviews request, validates priority and asset linkage.
- `APPROVED / REJECTED`: Manager authorizes work or rejects with mandatory reason.
- `CONFIRMED`: Client confirms satisfactory resolution before final administrative closure.

### B. Work Order Workflow
```
DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN PROGRESS -> ON HOLD -> COMPLETED -> SUPERVISOR REVIEW -> CLOSED
```
- `ASSIGNED`: Validates technician availability and active status (prevents conflicting double-booking).
- `ON HOLD`: Requires explicit reason (e.g., waiting for parts, site inaccessible); pauses SLA timers if configured.
- `COMPLETED`: Requires 100% checklist completion, resolution notes, and attached completion evidence.
- `SUPERVISOR REVIEW`: QA/Supervisor verification prior to final financial/operational closure.

### C. Preventive Maintenance Lifecycle
```
SCHEDULED -> DUE -> GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED -> NEXT CYCLE
```
- Automated scheduler generates work orders without duplicates and handles overdue cycles.

### D. Part Requisition & Inventory Lifecycle
```
REQUESTED -> RESERVED -> ISSUED -> CONSUMED / RETURNED -> RECONCILED
```
- Every state change generates an immutable `StockMovement` ledger entry maintaining transactional integrity.

### E. Asset Operational Status
```
ACTIVE -> UNDER MAINTENANCE -> OUT OF SERVICE -> ACTIVE / RETIRED / DISPOSED
```
- Asset status automatically transitions when critical breakdown work orders are opened or closed.

---

## 4. 42 Core Entities Architecture

All domain models must inherit from `apps.core.models.TimeStampedUUIDModel` (UUID primary keys, `created_at`, `updated_at`).

```
FieldOps Nexus Data Model (42 Entities)
│
├── 1. Organization & Access (7)
│   ├── Organization            # Multi-tenant corporate root
│   ├── Site                    # Physical facility / campus
│   ├── Zone                    # Specific building, floor, or zone
│   ├── User                    # Platform user account
│   ├── Role                    # RBAC role definition
│   ├── TechnicianProfile       # Field skill matrix, van link, license
│   └── Shift                   # Working hours & shift calendar
│
├── 2. Asset Lifecycle (6)
│   ├── Asset                   # Master asset registry
│   ├── AssetCategory           # Classification (HVAC, Electrical, IT, etc.)
│   ├── AssetComponent          # Sub-assembly / component hierarchy
│   ├── AssetDocument           # Manuals, schematics, compliance certs
│   ├── AssetMeter              # Runtime hours, odometer, cycle counters
│   └── AssetStatusHistory      # Audit log of asset status transitions
│
├── 3. Maintenance & Checklists (4)
│   ├── MaintenancePlan         # Preventive maintenance plan definition
│   ├── MaintenanceSchedule     # Calendar / meter recurrence triggers
│   ├── ChecklistTemplate       # Reusable inspection/procedure template
│   └── ChecklistItem           # Granular checklist question/field
│
├── 4. Service & Work Orders (6)
│   ├── ServiceRequest          # Inbound ticket from client/operations
│   ├── Incident                # Breakdown / emergency failure ticket
│   ├── WorkOrder               # Core execution work order
│   ├── WorkOrderAssignment     # Technician allocation & schedule window
│   ├── LaborEntry              # Technician clock-in/out labor hours
│   └── DowntimeRecord          # Asset outage duration & impact record
│
├── 5. Inspection & Quality (5)
│   ├── Inspection              # Executed inspection instance
│   ├── InspectionResponse      # Value recorded for a checklist item
│   ├── Finding                 # Defect/hazard flagged during inspection
│   ├── Attachment              # Photo/video/document evidence
│   └── ClosureApproval         # Formal supervisor sign-off record
│
├── 6. Spare Parts & Inventory (6)
│   ├── Warehouse               # Stock storage facility / technician van
│   ├── Part                    # Spare part catalog item
│   ├── StockBalance            # Quantity on hand per warehouse
│   ├── StockMovement           # Immutable ledger (receipt, issue, return)
│   ├── PartReservation         # Stock reserved for planned work orders
│   └── WorkOrderPart           # Part consumed on an executed work order
│
├── 7. Contracts & SLA (4)
│   ├── Warranty                # Manufacturer warranty coverage terms
│   ├── ServiceContract         # AMC / Third-party vendor contract
│   ├── SLAProfile              # Priority-based response & resolution SLA
│   └── EscalationRule          # Threshold and notification action matrix
│
└── 8. Audit & System (4)
    ├── Notification            # In-app and dispatched notification
    ├── AuditLog                # Immutable log of security/data changes
    ├── ReportSnapshot          # Cached operational analytics snapshot
    └── IntegrationEvent        # Webhook / external sync event record
```

---

## 5. Mandatory API Groups & Authorization Conventions

All public and operational endpoints must be versioned under `/api/v1/`:

| Endpoint Group | Route Prefix | Authorization Scope |
| :--- | :--- | :--- |
| **Authentication** | `/api/v1/auth/` | Public (login, token refresh) |
| **Assets & Hierarchy** | `/api/v1/assets/` | Asset Manager, Maintenance Planner, Read-only scopes |
| **Maintenance & PM** | `/api/v1/maintenance-plans/` | Maintenance Planner, Operations Manager |
| **Work Orders** | `/api/v1/work-orders/` | Planner, Supervisor, Assigned Technician |
| **Checklists & Inspections** | `/api/v1/checklists/` | Role and Assignment-scoped |
| **Inventory & Stock** | `/api/v1/parts/` | Storekeeper / Inventory, Technician (requisition) |
| **SLA & Escalation** | `/api/v1/slas/` | Service Manager, Operations Manager |
| **Client Portal** | `/api/v1/client/` | Authenticated Client / Requester role only |
| **Health & Readiness** | `/api/v1/health/` | Public (orchestrators, load balancers) |

---

## 6. Complex Engineering Rules & Guardrails

1. **Duplicate Prevention**: The PM scheduler must never generate duplicate work orders for the same maintenance cycle.
2. **Technician Conflict Prevention**: The assignment engine must reject assigning a technician who is inactive, on leave, or already assigned to a conflicting time block.
3. **SLA Timer Partitioning**: SLA engines must strictly differentiate **Response Time** (time to triage/assign) from **Resolution Time** (time to complete). Timers may pause **only** in explicitly configured states (e.g., `ON_HOLD`).
4. **Stock Consistency**: Every inventory reservation, issue, and return must be executed within database transactions (`transaction.atomic`) and generate a corresponding `StockMovement` entry.
5. **Mandatory Closure Evidence**: Closing a work order requires 100% completion of mandatory checklist items, technician sign-off, and resolution notes.
6. **Opaque QR Identifiers**: QR and barcode labels must use opaque UUIDs or non-secret hashes, never raw internal sequential database keys.
7. **Celery Scheduling**: Asynchronous background workers must handle PM job generation, SLA breach countdowns, contract expiration alerts, and KPI report caching.

---

## 7. 30 / 60 / 90 Review Checkpoint Delivery Matrix

| Review Gate | Mandatory Functional Deliverables | Acceptance Focus |
| :--- | :--- | :--- |
| **Day 30 Gate 1**<br>*(30–35% Scope)* | • User Auth & RBAC (7 personas)<br>• Site & Location Master hierarchy<br>• Asset Registry & Component Hierarchy<br>• Service Request & Work Order core<br>• Checklist templates & DB schema<br>• CI/CD pipeline & automated test suite | Real PostgreSQL persistence, role boundary enforcement, lifecycle state machine control, and clean code governance. |
| **Day 60 Gate 2**<br>*(65–75% Scope)* | • Celery PM recurring scheduler<br>• Work order dispatch & technician mobile workspace<br>• Inspection execution & defect findings<br>• Inventory reservations, stock issues & returns<br>• Real-time SLA breach & escalation engine<br>• Notifications & beta operational dashboards | End-to-end operational workflows, asynchronous task reliability, transaction safety, API contract compliance, and regression coverage. |
| **Day 90 Gate 3**<br>*(100% Scope - UAT)* | • Warranty / AMC tracking<br>• Client requester self-service portal<br>• QR / Barcode scanning flow<br>• Executive analytics (MTTR, MTBF, utilization)<br>• Audit export (CSV/PDF) & security hardening<br>• Zero open Critical/High defects | Full production readiness, complete deployment reproducibility, comprehensive documentation, and successful 7-step acceptance demonstration. |

---

## 8. The 7-Step Day-90 Acceptance Demonstration

Every build must be verified against this exact 7-step end-to-end acceptance flow:

1. **Site & Asset Setup**: Register an organization, site, and multi-tier asset hierarchy; view the complete status change history.
2. **Preventive Maintenance**: Configure a PM plan with calendar/meter triggers; verify Celery automatically generates scheduled work orders.
3. **Field Execution**: Dispatch a work order to a technician; complete the mobile checklist, requisition spare parts, log labor hours, and submit completion evidence.
4. **SLA Escalation**: Log a high-severity emergency service request; demonstrate response/resolution timers counting down and triggering supervisor escalation.
5. **Inventory Movement**: Issue spare parts from a warehouse and return unused items; prove transactional consistency across stock balances.
6. **QR Scan Event**: Scan/lookup an asset using its opaque QR identifier and log a service request directly from the asset context.
7. **Closure & Analytics**: Confirm client sign-off on completed work, close the ticket with supervisor approval, and verify updated MTTR/MTBF metrics on the dashboard.

---

## 9. Agent Pre-Flight Checklist (Run Before ANY Code Change)

Whenever an AI agent or developer is instructed to build, refactor, or test code in this repository, they **MUST** execute this checklist:

- [ ] **Rule 1**: Am I modifying or extending existing code, rather than recreating scaffolding from scratch?
- [ ] **Rule 2**: Does this feature persist real data in PostgreSQL via Django ORM with proper migrations?
- [ ] **Rule 3**: Have I avoided dummy buttons, static mock screens, and fake success messages?
- [ ] **Rule 4**: Is authorization enforced in the backend (Django view/serializer) rather than merely hiding HTML elements?
- [ ] **Rule 5**: Does this entity use `TimeStampedUUIDModel` with UUID primary keys?
- [ ] **Rule 6**: Are all endpoints prefixed under `/api/v1/` and documented in OpenAPI schemas?
- [ ] **Rule 7**: Have I added automated tests in `tests/` covering positive and negative permission scenarios?
- [ ] **Rule 8**: Are all configuration parameters and secrets loaded strictly from environment variables?
