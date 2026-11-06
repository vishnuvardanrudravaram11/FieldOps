# FieldOps Nexus — End-to-End Evaluation & Demo Script
## Day-30 Checkpoint Acceptance Demonstration

This script provides an end-to-end walkthrough for evaluators demonstrating the integrated enterprise workflows across Checkpoints A through L.

All demo personas are provisioned by running `python manage.py seed_dev_demo` and share the password:  
**`FieldOps-Dev-2026!`**

---

## Scenario: Pump Seal Failure & Emergency Overhaul Workflow

### Step 1: Customer Reports Incident via Client Portal
1. Navigate to: `http://localhost:8000/accounts/login/`
2. Sign in as **Client Requester**: `requester@demo.local`
3. Notice redirect to **Client Portal Dashboard** (`/portal/`):
   - Internal staff cockpits and settings are forbidden (HTTP 403 / fail-closed).
4. Click **"Report an Issue"** (`/portal/requests/create/`):
   - Select Asset: `AST-PMP-8802 (Flowserve Heavy-Duty Slurry Pump)`
   - Title: `Heavy mechanical seal leakage observed on primary pump`
   - Severity: `HIGH`
   - Impact Notes: `Slurry leaking onto concrete containment floor. Vibration alarms active.`
5. Click **Submit Report**.
   - Note generated service request number: `SR-2026-XXXX`.

---

### Step 2: Operations Triage & Work Order Conversion
1. Sign out and sign in as **Maintenance Planner**: `planner@demo.local`
2. Open **Incidents & Service Requests** (`/app/incidents/`):
   - Locate newly submitted report `SR-2026-XXXX`.
3. Open Incident Details:
   - Click **"Triage Request"** -> Status moves from `INTAKE` to `TRIAGED`.
   - Click **"Approve for Maintenance"** -> Status moves to `APPROVED`.
4. Click **"Convert to Work Order"**:
   - The system creates authoritative work order `WO-2026-YYYY` linked via `source_request`.
   - Work order status: `DRAFT`.

---

### Step 3: Work Order Planning & Parts Requisition
1. On Work Order Details (`/app/work-orders/{id}/`):
   - Click **"Plan Work Order"**:
     - Planned Start: Tomorrow 08:00
     - Planned End: Tomorrow 16:00
     - Estimated Hours: `6.00`
     - Work Type: `CORRECTIVE`
     - Priority: `HIGH`
   - Work order status updates to `PLANNED`.
2. Click **"Assign & Dispatch"**:
   - Assignee: `technician@demo.local (Alex Rivera)`
   - Status transitions to `DISPATCHED`.
3. Switch to the **"Parts"** tab:
   - Click **"Request Part"**:
     - Item: `Mechanical Seal Cartridge 2.5"`
     - Quantity: `1.00`
   - Part line moves to `REQUESTED`.

---

### Step 4: Inventory Reservation & Store Dispatch
1. Sign out and sign in as **Inventory Clerk / Admin**: `admin@demo.local`
2. Open Work Order Parts tab or Inventory Module (`/app/inventory/`):
   - Locate the requested mechanical seal for `WO-2026-YYYY`.
   - Click **"Reserve Stock"** -> Status: `RESERVED` (deducts available stock, updates allocated).
   - Click **"Issue to Technician"** -> Status: `ISSUED` (ready for technician installation).

---

### Step 5: Technician On-Site Execution & Digital Sign-off
1. Sign out and sign in as **Technician**: `technician@demo.local`
2. Notice landing on **Technician Workspace** (`/app/workspace/`):
   - Locate assigned job `WO-2026-YYYY`.
3. Open Job Execution Sheet:
   - **Log Travel**: 1.25 hours, 35 km via Route 9.
   - Click **"Start Job"** -> Work order transitions to `IN_PROGRESS`.
   - **Execute Checklist (M08)**:
     - Open checklist tab, complete all safety and alignment inspection items.
     - Status updates to `COMPLETED` and `VALID`.
   - **Record Labor**: 4.50 hours on seal replacement and laser alignment.
   - **Consume Parts**: Mark issued seal cartridge as `CONSUMED`.
   - **Attach Evidence**: Upload completion pressure test record log.
4. Click **"Complete Job"**:
   - Resolution Notes: `Replaced mechanical seal and flushed casing. Dial indicator shows shaft runout within 0.001". Zero leakage during 30 min pressure test.`
   - Signer Name: `Marcus Vance (Plant Supervisor)`
   - Signer Title: `Lead Facility Engineer`
   - Digital signature captured.
5. Work order status transitions to `COMPLETED`.

---

### Step 6: Supervisor Review & Work Order Closure
1. Sign out and sign in as **Supervisor**: `supervisor@demo.local`
2. Navigate to **Work Orders** (`/app/work-orders/`):
   - Filter by status `COMPLETED`.
   - Open `WO-2026-YYYY`.
3. Inspect completion details:
   - Verify checklist status shows `COMPLETED` / `VALID`.
   - Verify completion evidence photo/log is attached.
   - Verify customer sign-off details are present.
4. Click **"Approve & Close Work Order"**:
   - Supervisor adds confirmation comment: `Verified seal installation and hydrostatic record. Work approved.`
   - Work order status permanently moves to `CLOSED`.

---

### Step 7: Compliance & Audit Verification
1. Sign out and sign in as **Platform Admin / Owner**: `owner@demo.local`
2. Open **Audit Trail** (`/app/audit/`):
   - Observe append-only audit trail capturing all transitions:
     - `incident.reported` -> `incident.triaged` -> `incident.converted_to_work_order`
     - `work_order.planned` -> `work_order.dispatched` -> `work_order.started`
     - `workspace.travel_logged` -> `inventory.part_consumed` -> `inspection.completed`
     - `workspace.job_completed` -> `work_order.closed`
   - Observe tamper-proof timestamps, user attribution, and before/after diffs.
