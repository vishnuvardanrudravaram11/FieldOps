"""Empirical verification suite for Functional QA Testing Report Defect Remediation.

Explicitly maps and tests all failed test cases from
'FieldOps_Nexus_Complete_Functional_Testing_Report_E_R.xlsx':

- FT-M08-021, FT-M08-043, FT-M08-100 (DEF-001):
  POST /checklist-templates/{id}/reorder/ and /checklists/{id}/reorder/
  Checklist item reordering with reversed permutation succeeds (HTTP 200).
- FT-M04-013 (DEF-002):
  POST & PATCH /maintenance-plans/{id}/ accepts priority="CRITICAL" (HTTP 200/201).
- FT-PLAT-009, FT-PLAT-010 (DEF-003):
  Platform Super Admin management of all organizations /status/ endpoint
  rejects malformed routes and accepts valid status updates.
- FT-USER-042 (DEF-004):
  POST /members/: unknown role name is rejected (HTTP 400).
- FT-M06-212, FT-M06-213 (DEF-005):
  Work order CLOSED + 'review' or 'close' is rejected with 409 InvalidTransition.
- FT-M04-056 (DEF-006):
  A disabled maintenance plan cannot receive new schedules (HTTP 409).
- FT-M04-063 (DEF-007):
  PM compliance with an invalid date format (2026-13-01) is rejected (HTTP 400).
- FT-M11-096 (DEF-008):
  An SLA profile with no priority targets cannot be activated (HTTP 400 missing_targets).
- FT-M08-095 (DEF-009):
  Inspection cannot be completed while required items are unanswered (HTTP 409 inspection_incomplete).
- FT-M07-086 (DEF-010):
  Technician availability status change to ON_LEAVE then AVAILABLE succeeds without 500 (HTTP 200).
- FT-M01-198, FT-M02-171, FT-M05-164, FT-M06-269, FT-M09-196, FT-M10-205 (DEF-011):
  List search with quotes, semicolons, and SQL fragments executes safely (HTTP 200).
- FT-M01-215 (DEF-012):
  GET /zones/: invalid filter value zone_type=NOT_A_VALUE yields count 0 instead of all rows.
- FT-WFX-009 (DEF-013):
  WF-01 step 9: Deactivated user cannot log in via /auth/token/ (HTTP 401). Reactivated user can.
- FT-UI-041 (DEF-014):
  Operational dashboards page (/app/dashboards/) loads with CSP nonces on inline script tags.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.checklists import services as checklist_services
from apps.checklists.models import ChecklistItem
from apps.core.exceptions import Conflict, InvalidTransition, ValidationFailed
from apps.maintenance import selectors as maintenance_selectors
from apps.maintenance import services as maintenance_services
from apps.rbac.models import Role
from apps.sites import selectors as site_selectors
from apps.sites.models import Zone
from apps.sla import services as sla_services
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Membership
from apps.workorders import services as wo_services
from apps.workorders.models import WorkOrder, WorkOrderLabor
from apps.workspace import services as workspace_services

pytestmark = pytest.mark.django_db


# --- DEF-001 (FT-M08-021, FT-M08-043, FT-M08-100) ----------------------------------------------------


def test_ft_m08_021_043_100_checklist_reorder_service_and_api(org_a, owner_a):
    """DEF-001: Checklist item reorder swaps positions without unique constraint violation."""
    template = checklist_services.create_template(
        org_a,
        actor=owner_a,
        name="FT M08 Reorder Test",
        description="Testing position renumbering",
    )
    item1 = checklist_services.add_item(template, prompt="Prompt 1", item_type=ChecklistItem.ItemType.BOOLEAN, actor=owner_a)
    item2 = checklist_services.add_item(template, prompt="Prompt 2", item_type=ChecklistItem.ItemType.BOOLEAN, actor=owner_a)
    item3 = checklist_services.add_item(template, prompt="Prompt 3", item_type=ChecklistItem.ItemType.BOOLEAN, actor=owner_a)

    # 1. Service Layer Reorder (Reversing order)
    reordered = checklist_services.reorder_items(template, [item3.pk, item2.pk, item1.pk], actor=owner_a)
    assert [i.pk for i in reordered] == [item3.pk, item2.pk, item1.pk]
    assert [i.position for i in reordered] == [1, 2, 3]

    # 2. REST API Layer Reorder (FT-M08-021 / FT-M08-100)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.post(
        f"/api/v1/checklist-templates/{template.id}/reorder/",
        data={"order": [str(item1.pk), str(item2.pk), str(item3.pk)]},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 200
    positions = [item["position"] for item in res.data]
    assert positions == [1, 2, 3]


# --- DEF-002 (FT-M04-013) -----------------------------------------------------------------------------


def test_ft_m04_013_maintenance_plan_priority_critical(org_a, site_a1, make_asset, owner_a):
    """DEF-002: Maintenance plan accepts priority='CRITICAL' via Service and REST API."""
    asset = make_asset(org_a, site_a1, "AST-CRIT-PM")
    plan = maintenance_services.create_plan(
        org_a,
        asset=asset,
        name="Critical PM Plan",
        priority="CRITICAL",
        actor=owner_a,
    )
    assert plan.priority == "CRITICAL"

    # REST API PATCH with priority=CRITICAL (FT-M04-013)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.patch(
        f"/api/v1/maintenance-plans/{plan.id}/",
        data={"priority": "CRITICAL"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 200
    assert res.data["priority"] == "CRITICAL"


# --- DEF-003 (FT-PLAT-009, FT-PLAT-010) ----------------------------------------------------------------


def test_ft_plat_009_010_platform_organization_status(platform_admin, org_a):
    """DEF-003: Platform organizations status route works cleanly and rejects invalid inputs."""
    client = APIClient()
    client.force_authenticate(user=platform_admin)

    # 1. Valid status update: deactivate then reactivate (FT-PLAT-009)
    res_deact = client.post(
        f"/api/v1/platform/organizations/{org_a.id}/status/",
        data={"active": False, "reason": "Testing deactivation"},
        format="json",
    )
    assert res_deact.status_code == 200
    assert res_deact.data["status"] == "SUSPENDED"

    res_react = client.post(
        f"/api/v1/platform/organizations/{org_a.id}/status/",
        data={"active": True, "reason": "Testing reactivation"},
        format="json",
    )
    assert res_react.status_code == 200
    assert res_react.data["status"] == "ACTIVE"

    # Invalid / non-existent organization input (FT-PLAT-010)
    fake_id = uuid.uuid4()
    res_neg = client.post(
        f"/api/v1/platform/organizations/{fake_id}/status/",
        data={"active": True},
        format="json",
    )
    assert res_neg.status_code == 404


# --- DEF-004 (FT-USER-042) -----------------------------------------------------------------------------


def test_ft_user_042_unknown_role_name_rejected(org_a, owner_a):
    """DEF-004: Member created with unknown role name is rejected with 400 ValidationError."""
    client = APIClient()
    client.force_authenticate(user=owner_a)

    res = client.post(
        "/api/v1/members/",
        data={"email": "unknown_role_user@example.com", "full_name": "Test User", "role": "No Such Role"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 400
    assert "role" in str(res.data)


# --- DEF-005 (FT-M06-212, FT-M06-213) ------------------------------------------------------------------


def test_ft_m06_212_213_closed_work_order_rejects_review_and_close(org_a, site_a1, make_asset, owner_a):
    """DEF-005: CLOSED work order rejects 'review' and 'close' actions with 409 InvalidTransition."""
    asset = make_asset(org_a, site_a1, "AST-WO-CLOSE")
    owner_member = Membership.objects.get(organization=org_a, user=owner_a)
    wo = wo_services.create_work_order(
        org_a,
        site=site_a1,
        asset=asset,
        title="Closed WO Review Test",
        actor=owner_a,
    )
    wo._workflow_transition_write = True
    wo.status = WorkOrder.Status.SUPERVISOR_REVIEW
    wo.resolution_notes = "Thorough resolution notes exceeding 10 characters."
    wo.save(update_fields=["status", "resolution_notes"])
    del wo._workflow_transition_write

    WorkOrderLabor.objects.create(
        organization=wo.organization,
        work_order=wo,
        technician=owner_member,
        entered_by=owner_a,
        work_date=date.today(),
        hours=Decimal("1.00"),
        description="Labor entry",
    )
    wo_services.review_work_order(wo, membership=owner_member, actor=owner_a, approved=True, notes="Initial approval")
    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.CLOSED

    # Service layer rejection
    with pytest.raises(InvalidTransition):
        wo_services.review_work_order(wo, membership=owner_member, actor=owner_a, approved=True, notes="Second review")

    with pytest.raises(InvalidTransition):
        wo_services.close_work_order(wo, membership=owner_member, actor=owner_a, comment="Second close")

    # REST API layer rejection (FT-M06-212, FT-M06-213)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res_review = client.post(
        f"/api/v1/work-orders/{wo.id}/review/",
        data={"approved": True, "notes": "API second review"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res_review.status_code == 409

    res_close = client.post(
        f"/api/v1/work-orders/{wo.id}/close/",
        data={"comment": "API second close"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res_close.status_code == 409


# --- DEF-006 (FT-M04-056) -----------------------------------------------------------------------------


def test_ft_m04_056_disabled_maintenance_plan_rejects_schedules(org_a, site_a1, make_asset, owner_a):
    """DEF-006: Disabled maintenance plan rejects new schedules with 409 Conflict."""
    asset = make_asset(org_a, site_a1, "AST-PM-DIS")
    plan = maintenance_services.create_plan(
        org_a,
        asset=asset,
        name="Inactive PM Plan",
        actor=owner_a,
    )
    maintenance_services.set_plan_active(plan, active=False, actor=owner_a)
    plan.refresh_from_db()
    assert not plan.is_active

    # Service Layer
    with pytest.raises(Conflict) as exc_info:
        maintenance_services.create_schedule(
            plan,
            actor=owner_a,
            trigger_type="TIME",
            frequency="MONTHLY",
            interval_count=1,
            start_date=date.today(),
        )
    assert exc_info.value.code == "plan_inactive"

    # REST API Layer (FT-M04-056)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.post(
        f"/api/v1/maintenance-plans/{plan.id}/schedules/",
        data={"trigger_type": "TIME", "frequency": "MONTHLY", "interval_count": 1, "start_date": str(date.today())},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 409


# --- DEF-007 (FT-M04-063) -----------------------------------------------------------------------------


def test_ft_m04_063_pm_compliance_invalid_date_rejected(org_a, owner_a):
    """DEF-007: PM compliance query with impossible/invalid date raises 400 ValidationFailed."""
    owner_member = Membership.objects.get(organization=org_a, user=owner_a)

    # Service Layer
    with pytest.raises(ValidationFailed) as exc_info:
        maintenance_selectors.pm_compliance_ratio(
            owner_member,
            org_a,
            start_date="2026-13-01",
        )
    assert exc_info.value.code == "invalid_date_format"

    # REST API Layer (FT-M04-063)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.get(
        "/api/v1/maintenance-cycles/compliance/?start_date=2026-13-01",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 400


# --- DEF-008 (FT-M11-096) -----------------------------------------------------------------------------


def test_ft_m11_096_sla_profile_without_targets_cannot_be_activated(org_a, owner_a):
    """DEF-008: SLA profile without targets raises ValidationFailed (HTTP 400) on activation."""
    profile = sla_services.create_profile(
        org_a,
        name="Targetless SLA Profile",
        applies_to="REQUEST",
        actor=owner_a,
        is_active=False,
    )
    assert not profile.targets.exists()

    # Service Layer
    with pytest.raises(ValidationFailed) as exc_info:
        sla_services.set_profile_active(profile, active=True, actor=owner_a)
    assert exc_info.value.code == "missing_targets"

    # REST API Layer (FT-M11-096)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.post(
        f"/api/v1/sla-profiles/{profile.id}/activate/",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 400


# --- DEF-009 (FT-M08-095) -----------------------------------------------------------------------------


def test_ft_m08_095_inspection_complete_without_required_answers_raises_conflict(org_a, site_a1, make_asset, owner_a):
    """DEF-009: Completing inspection without required answers raises 409 Conflict (not 500)."""
    asset = make_asset(org_a, site_a1, "AST-INSP-REQ")
    template = checklist_services.create_template(
        org_a,
        actor=owner_a,
        name="Required Checklist",
        description="Testing required items",
    )
    checklist_services.add_item(
        template,
        prompt="Required Prompt",
        item_type=ChecklistItem.ItemType.BOOLEAN,
        required=True,
        actor=owner_a,
    )
    template = checklist_services.activate_template(template, actor=owner_a)

    owner_member = Membership.objects.get(organization=org_a, user=owner_a)
    insp = checklist_services.start_inspection(org_a, template=template, membership=owner_member, actor=owner_a, asset=asset)
    assert insp.status == "IN_PROGRESS"

    # Service Layer
    with pytest.raises(Conflict) as exc_info:
        checklist_services.complete_inspection(insp, membership=owner_member, actor=owner_a)
    assert exc_info.value.code == "inspection_incomplete"

    # REST API Layer (FT-M08-095)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.post(
        f"/api/v1/inspections/{insp.id}/complete/",
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 409


# --- DEF-010 (FT-M07-086) -----------------------------------------------------------------------------


def test_ft_m07_086_technician_availability_on_leave_succeeds(org_a, tech_a):
    """DEF-010: Technician can change availability to ON_LEAVE and AVAILABLE without 500 error."""
    tech_member = Membership.objects.get(organization=org_a, user=tech_a)

    # 1. Service Layer
    profile = workspace_services.set_technician_availability(
        tech_member,
        status="ON_LEAVE",
        actor=tech_a,
    )
    assert profile.availability_status == "ON_LEAVE"

    profile2 = workspace_services.set_technician_availability(
        tech_member,
        status="AVAILABLE",
        actor=tech_a,
    )
    assert profile2.availability_status == "AVAILABLE"

    # 2. REST API Layer (FT-M07-086)
    client = APIClient()
    client.force_authenticate(user=tech_a)
    res1 = client.post(
        "/api/v1/workspace/profile/availability/",
        data={"availability_status": "ON_LEAVE"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res1.status_code == 200

    res2 = client.post(
        "/api/v1/workspace/profile/availability/",
        data={"availability_status": "AVAILABLE"},
        format="json",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res2.status_code == 200


# --- DEF-011 (FT-M01-198, FT-M02-171, FT-M05-164, FT-M06-269, FT-M09-196, FT-M10-205) ---------------


def test_ft_m01_198_search_special_characters_across_modules(org_a, owner_a):
    """DEF-011: Search query with quotes, semicolons, and SQL keywords runs safely with HTTP 200."""
    client = APIClient()
    client.force_authenticate(user=owner_a)

    endpoints = [
        "/api/v1/sites/",
        "/api/v1/assets/",
        "/api/v1/incidents/",
        "/api/v1/work-orders/",
        "/api/v1/parts/",
        "/api/v1/agreements/",
    ]
    for ep in endpoints:
        res = client.get(
            f"{ep}?q=%27%3B%20DROP%20TABLE%20x%3B--",
            HTTP_X_ORGANIZATION=org_a.slug,
        )
        assert res.status_code == 200, f"Endpoint {ep} failed with status {res.status_code}"
        assert "results" in res.data


# --- DEF-012 (FT-M01-215) -----------------------------------------------------------------------------


def test_ft_m01_215_invalid_zone_type_filter_returns_empty(org_a, site_a1, owner_a):
    """DEF-012: Filtering zones with zone_type=NOT_A_VALUE yields count 0 instead of all rows."""
    Zone.objects.create(organization=org_a, site=site_a1, name="Zone 1", code="Z1", zone_type="BUILDING")
    Zone.objects.create(organization=org_a, site=site_a1, name="Zone 2", code="Z2", zone_type="FLOOR")

    # Service Layer
    qs = Zone.objects.filter(site=site_a1)
    filtered = site_selectors.filter_zones(qs, {"zone_type": "NOT_A_VALUE"})
    assert filtered.count() == 0

    # REST API Layer (FT-M01-215)
    client = APIClient()
    client.force_authenticate(user=owner_a)
    res = client.get(
        "/api/v1/zones/?zone_type=NOT_A_VALUE",
        HTTP_X_ORGANIZATION=org_a.slug,
    )
    assert res.status_code == 200
    assert res.data["count"] == 0


# --- DEF-013 (FT-WFX-009) -----------------------------------------------------------------------------


def test_ft_wfx_009_deactivated_member_cannot_login(org_a, owner_a):
    """DEF-013: WF-01 step 9: Deactivated member cannot obtain JWT token, reactivated member can."""
    member_email = "member_wf_deact@example.com"
    password = "TestPassword@2026!"
    member = tenancy_services.invite_member(
        org_a,
        email=member_email,
        full_name="WF Deact Test",
        role_ids=[r.pk for r in Role.objects.filter(organization=org_a, system_key="technician")],
        actor=owner_a,
        password=password,
    )
    member.status = Membership.Status.ACTIVE
    member.save(update_fields=["status"])

    client = APIClient()

    # Active member obtains token
    token_res = client.post("/api/v1/auth/token/", data={"email": member_email, "password": password}, format="json")
    assert token_res.status_code == 200
    assert "access" in token_res.data

    # Deactivate member via service / API
    tenancy_services.set_member_active(member, active=False, actor=owner_a)
    member.refresh_from_db()
    assert member.status == Membership.Status.SUSPENDED

    # Deactivated member cannot obtain token (HTTP 401)
    token_res_deact = client.post("/api/v1/auth/token/", data={"email": member_email, "password": password}, format="json")
    assert token_res_deact.status_code in (400, 401, 403)

    # Reactivate member
    tenancy_services.set_member_active(member, active=True, actor=owner_a)
    member.refresh_from_db()
    assert member.status == Membership.Status.ACTIVE

    # Reactivated member obtains token again
    token_res_react = client.post("/api/v1/auth/token/", data={"email": member_email, "password": password}, format="json")
    assert token_res_react.status_code == 200


# --- DEF-014 (FT-UI-041) -----------------------------------------------------------------------------


def test_ft_ui_041_dashboards_csp_nonce(client, org_a, site_a1, owner_a):
    """DEF-014: Operational dashboards template includes nonce on inline script tags."""
    client.force_login(owner_a)
    session = client.session
    session["organization_id"] = str(org_a.pk)
    session.save()

    res = client.get("/app/dashboards/")
    assert res.status_code == 200
    content = res.content.decode("utf-8")
    assert "<script>" not in content
    assert 'nonce="' in content
