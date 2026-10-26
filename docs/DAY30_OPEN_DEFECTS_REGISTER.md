# FieldOps Nexus — Defect Register & Resolution Log
## Day-30 Audit & Remediation Log

| Defect ID | Severity | Area / Module | Description & Root Cause | Remediation Applied | Resolution Status |
|---|---|---|---|---|:---:|
| **DEF-01** | High | `apps.workorders` | `WorkOrderViewSet` in `src/apps/workorders/views.py` missing generic `transition` and `closure` REST actions, causing 404 in M08 checklist boundary tests. | Added `@action(detail=True, methods=["post"]) def transition(...)` and `@action(detail=True, methods=["get"]) def closure(...)` returning closure blockers. | **RESOLVED & VERIFIED** |
| **DEF-02** | Medium | `apps.workorders` | `CompleteSerializer` (a `StrictInputSerializer`) rejected payloads containing the `"action"` key when invoked from the generic `transition` action. | Stripped `"action"` from request data dict before passing payload to `CompleteSerializer`. | **RESOLVED & VERIFIED** |
| **DEF-03** | High | `apps.workorders` | Missing `source_id` field in `WorkOrderSerializer.Meta.fields`, causing `KeyError: 'source_id'` in M04 API tests. | Added `source_id` to `fields` and `read_only_fields` in `WorkOrderSerializer`. | **RESOLVED & VERIFIED** |
| **DEF-04** | High | `apps.workspace` | Route `<uuid:line_pk>/consume/` missing from `src/apps/workspace/urls.py`, and `JobPartConsumeView` did not accept `line_pk` parameter. | Added `<uuid:line_pk>/consume/` to URL patterns and updated `JobPartConsumeView` to validate line ownership and work order association. | **RESOLVED & VERIFIED** |
| **DEF-05** | High | `apps.workorders` | `src/templates/workorder/tabs/work.html` missing, causing `/app/work-orders/{id}/?tab=work` to fall back to overview tab without parts/labor. | Created `src/templates/workorder/tabs/work.html`, registered `"work"` in `TAB_TEMPLATES`, and updated `_work_order_tab_context`. | **RESOLVED & VERIFIED** |
| **DEF-06** | Medium | `apps.dashboards` | `MyWorkDashboardView` required full `work_order.view` permission, denying technicians who only possess `work_order.view_assigned`. | Updated permission check to allow `work_order.view` OR `work_order.view_assigned`. | **RESOLVED & VERIFIED** |
| **DEF-07** | High | `apps.rbac` | `operations_manager` role had extraneous `"work_order.create"` permission, violating separation of duties and failing UI action tests. | Removed `"work_order.create"` from `operations_manager` template in `src/apps/rbac/role_templates.py`. | **RESOLVED & VERIFIED** |
| **DEF-08** | High | `apps.incidents` | `PermissionDenied` exception was not imported in `src/apps/incidents/views.py`, causing `NameError` when client portal users accessed internal incidents. | Added `from django.core.exceptions import PermissionDenied` to imports in `src/apps/incidents/views.py`. | **RESOLVED & VERIFIED** |
| **DEF-09** | High | `apps.workorders` | `get_checklist_status` in `src/apps/workorders/checklist_adapter.py` returned `NOT_REQUIRED` when `insp` was None, even if `checklist_required=True`. | Fixed fallback to return `is_valid=False` with mandatory completion message whenever `work_order.checklist_required` is True. | **RESOLVED & VERIFIED** |
| **DEF-10** | High | `apps.workspace` | Duplicate `JobCompleteAPIView` defined in `api_views.py`; second definition required `signer_name`, rejecting technician-only completions with HTTP 400. | Consolidated into a single unified `JobCompleteAPIView` that handles both digital signoff payloads and standard technician completion. | **RESOLVED & VERIFIED** |

---

## Open Defects Summary
- **Critical / Blocker Open Defects**: 0
- **High Severity Open Defects**: 0
- **Medium Severity Open Defects**: 0
- **Low Severity / Cosmetic Open Defects**: 0
- **All identified defects have been remediated, re-tested, and verified against PostgreSQL 16.**
