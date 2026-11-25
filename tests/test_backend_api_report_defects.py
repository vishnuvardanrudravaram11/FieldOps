"""Regression tests for defects identified in the Backend API Testing Report.

DEF-001: Client persona must receive 403 on all 23 affected admin/restricted endpoints
DEF-002: Client persona must receive 403 on all 6 affected write endpoints
DEF-003: Repeated DELETE of a platform organization must return 404 (idempotent failure)
DEF-004: No malformed // paths in OpenAPI schema; platform org status works cleanly
DEF-005: provisional-checklist endpoint must appear in the OpenAPI schema
DEF-006: Platform org status action in OpenAPI schema must match routed /status/ path
DEF-007: Constant O(1) query scaling on /requests/, /service-requests/, /incidents/, /workorders/, /work-orders/
"""
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets import services as asset_services
from apps.checklists.models import ChecklistTemplate
from apps.core.models import IntegrationEvent, WebhookEndpoint
from apps.incidents import services as incident_services
from apps.inventory.models import Part
from apps.portal.models import PortalAccount
from apps.rbac import services as rbac
from apps.rbac.models import MembershipRole, Role
from apps.sites.models import Site
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Membership, Organization
from apps.ui.utils import is_client_membership
from apps.workorders import services as wo_services
from apps.workorders.models import WorkOrder


def _seed_org_with_owner():
    """Create a test org with an active owner membership."""
    org, owner_membership = tenancy_services.create_organization(
        name=f"QA-API-Org-{uuid.uuid4().hex[:8]}",
        owner_name="QA Owner",
        owner_email=f"qa-owner-{uuid.uuid4().hex[:6]}@test.local",
        owner_password="TestPass123!",
    )
    owner_membership.status = Membership.Status.ACTIVE
    owner_membership.save(update_fields=["status"])
    return org, owner_membership.user, owner_membership


def _create_client_membership(org, *, email_prefix="portal.member", with_portal_account=False):
    """Create a client_requester membership in the org."""
    email = f"{email_prefix}-{uuid.uuid4().hex[:6]}@test.local"
    user = User.objects.create_user(email=email, password="TestPass123!", full_name="QA Client")
    membership = Membership.objects.create(user=user, organization=org, status=Membership.Status.ACTIVE)
    client_role = Role.objects.filter(organization=org, system_key="client_requester").first()
    if not client_role:
        rbac.sync_system_roles(org)
        client_role = Role.objects.filter(organization=org, system_key="client_requester").first()
    assert client_role is not None, "client_requester role must exist in org"
    MembershipRole.objects.create(membership=membership, role=client_role)
    if with_portal_account:
        PortalAccount.objects.create(
            organization=org,
            membership=membership,
            company_name="Acme Portal Client",
            is_enabled=True,
        )
    return user, membership


def _api_client_for(user, org=None):
    """Return an APIClient authenticated as user (optionally bound to org)."""
    client = APIClient()
    client.force_authenticate(user=user)
    if org is not None:
        client.credentials(HTTP_X_ORGANIZATION=str(org.pk))
    return client


@pytest.mark.django_db(transaction=True)
class TestDEF001AndDEF002ClientRBAC:
    """DEF-001 (23 TCs) & DEF-002 (6 TCs): Verify all 29 endpoints return 403 for Client persona."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.org, self.owner_user, self.owner_m = _seed_org_with_owner()
        self.template = ChecklistTemplate.objects.create(
            organization=self.org,
            key=uuid.uuid4(),
            version=1,
            name="QA Inspection Checklist",
            created_by=self.owner_user,
        )
        self.part = Part.objects.create(
            organization=self.org,
            part_number=f"QA-PART-{uuid.uuid4().hex[:6]}",
            name="QA Filter Part",
        )
        WebhookEndpoint.objects.create(
            organization=self.org,
            name="QA Hook",
            target_url="https://hooks.example.invalid/events",
            event_pattern="work_order.*",
            is_active=False,
        )
        IntegrationEvent.objects.create(
            organization=self.org,
            event_type="work_order.created",
            aggregate_type="work_order",
            aggregate_id=str(uuid.uuid4()),
            payload={},
        )
        # Test both role-only client (non-'client.' email) and portal-linked seeded-style client
        self.role_only_user, self.role_only_m = _create_client_membership(
            self.org, email_prefix="external.requester", with_portal_account=False
        )
        self.portal_client_user, self.portal_client_m = _create_client_membership(
            self.org, email_prefix="client.requester", with_portal_account=True
        )

    def test_both_client_variants_detected_as_client_membership(self):
        assert is_client_membership(self.role_only_m)
        assert is_client_membership(self.portal_client_m)

    @pytest.mark.parametrize("use_portal_account", [False, True])
    def test_all_23_def001_endpoints_return_403_for_client(self, use_portal_account):
        user = self.portal_client_user if use_portal_account else self.role_only_user
        api = _api_client_for(user, self.org)
        tpl_id = str(self.template.pk)
        part_id = str(self.part.pk)
        member_id = str(self.owner_m.pk)

        def001_cases = [
            ("GET", "/api/v1/audit-logs/", None),                            # API-AUDITLOGS-004
            ("GET", "/api/v1/audit-logs/metrics/", None),                    # API-AUDITLOGS-035
            ("GET", "/api/v1/audit-logs/reports/", None),                    # API-AUDITLOGS-040
            ("PATCH", f"/api/v1/checklist-templates/{tpl_id}/", {"name": "X"}),          # API-CHECKLISTS-040
            ("POST", f"/api/v1/checklist-templates/{tpl_id}/activate/", {}),             # API-CHECKLISTS-046
            ("POST", f"/api/v1/checklist-templates/{tpl_id}/deactivate/", {}),           # API-CHECKLISTS-053
            ("PATCH", f"/api/v1/checklists/{tpl_id}/", {"name": "X"}),                   # API-CHECKLISTS-138
            ("POST", f"/api/v1/checklists/{tpl_id}/activate/", {}),                      # API-CHECKLISTS-144
            ("POST", f"/api/v1/checklists/{tpl_id}/deactivate/", {}),                    # API-CHECKLISTS-151
            ("GET", "/api/v1/integration-events/", None),                    # API-INTEGRATIO-004
            ("GET", "/api/v1/members/", None),                               # API-USERSMEMBE-004
            ("GET", f"/api/v1/members/{member_id}/", None),                  # API-USERSMEMBE-031
            ("PATCH", f"/api/v1/parts/{part_id}/", {"name": "X"}),           # API-INVENTORYS-059
            ("POST", f"/api/v1/parts/{part_id}/activate/", {}),              # API-INVENTORYS-065
            ("POST", f"/api/v1/parts/{part_id}/deactivate/", {}),            # API-INVENTORYS-072
            ("GET", "/api/v1/permissions/", None),                           # API-RBACROLESP-004
            ("GET", "/api/v1/roles/", None),                                 # API-RBACROLESP-009
            ("PATCH", f"/api/v1/spare-parts/{part_id}/", {"name": "X"}),     # API-INVENTORYS-120
            ("POST", f"/api/v1/spare-parts/{part_id}/activate/", {}),        # API-INVENTORYS-126
            ("POST", f"/api/v1/spare-parts/{part_id}/deactivate/", {}),      # API-INVENTORYS-133
            ("GET", "/api/v1/users/", None),                                 # API-USERSMEMBE-067
            ("GET", f"/api/v1/users/{member_id}/", None),                    # API-USERSMEMBE-094
            ("GET", "/api/v1/webhooks/", None),                              # API-INTEGRATIO-032
        ]
        assert len(def001_cases) == 23

        for method, path, payload in def001_cases:
            fn = getattr(api, method.lower())
            resp = fn(path) if payload is None else fn(path, payload, format="json")
            assert resp.status_code == 403, (
                f"[DEF-001 portal={use_portal_account}] {method} {path}: expected 403, got {resp.status_code}"
            )

    @pytest.mark.parametrize("use_portal_account", [False, True])
    def test_all_6_def002_endpoints_return_403_for_client(self, use_portal_account):
        user = self.portal_client_user if use_portal_account else self.role_only_user
        api = _api_client_for(user, self.org)
        tpl_id = str(self.template.pk)

        def002_cases = [
            ("/api/v1/checklist-templates/", {"name": "QA Blocked"}),                    # API-CHECKLISTS-024
            (f"/api/v1/checklist-templates/{tpl_id}/new-version/", {}),                  # API-CHECKLISTS-087
            ("/api/v1/checklists/", {"name": "QA Blocked"}),                             # API-CHECKLISTS-122
            (f"/api/v1/checklists/{tpl_id}/new-version/", {}),                           # API-CHECKLISTS-185
            ("/api/v1/parts/", {"part_number": "QA-PN-1", "name": "QA Blocked"}),        # API-INVENTORYS-043
            ("/api/v1/spare-parts/", {"part_number": "QA-PN-2", "name": "QA Blocked"}),  # API-INVENTORYS-104
        ]
        assert len(def002_cases) == 6

        for path, payload in def002_cases:
            resp = api.post(path, payload, format="json")
            assert resp.status_code == 403, (
                f"[DEF-002 portal={use_portal_account}] POST {path}: expected 403, got {resp.status_code}"
            )

    def test_owner_retains_full_access_to_admin_endpoints(self):
        api = _api_client_for(self.owner_user, self.org)
        for path in ("/api/v1/audit-logs/", "/api/v1/members/", "/api/v1/roles/", "/api/v1/parts/"):
            assert api.get(path).status_code == 200


@pytest.mark.django_db(transaction=True)
class TestDEF003DoubleDeleteReturns404:
    """DEF-003: Second DELETE on soft-deleted or hard-deleted org must return 404."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.admin = User.objects.create_superuser(
            email=f"qa-platform-{uuid.uuid4().hex[:6]}@test.local",
            password="TestPass123!",
            full_name="QA Platform Admin",
        )
        self.admin.is_platform_admin = True
        self.admin.save(update_fields=["is_platform_admin"])
        self.api = _api_client_for(self.admin)

    def test_double_delete_decommissioned_org_returns_404(self):
        resp = self.api.post("/api/v1/platform/organizations/", {
            "name": f"QA-Delete-{uuid.uuid4().hex[:8]}",
            "owner_name": "QA Owner",
            "owner_email": f"qa-del-owner-{uuid.uuid4().hex[:6]}@test.local",
        }, format="json")
        assert resp.status_code == 201
        org_id = resp.data["id"]

        resp1 = self.api.delete(f"/api/v1/platform/organizations/{org_id}/")
        assert resp1.status_code == 200

        resp2 = self.api.delete(f"/api/v1/platform/organizations/{org_id}/")
        assert resp2.status_code == 404

    def test_double_delete_hard_deleted_org_returns_404(self):
        org = Organization.objects.create(
            name=f"QA-Bare-{uuid.uuid4().hex[:8]}",
            slug=f"qa-bare-{uuid.uuid4().hex[:8]}",
        )
        resp1 = self.api.delete(f"/api/v1/platform/organizations/{org.pk}/")
        assert resp1.status_code == 200

        resp2 = self.api.delete(f"/api/v1/platform/organizations/{org.pk}/")
        assert resp2.status_code == 404

    def test_billing_suspended_org_can_still_be_deleted_once_then_404(self):
        org, _ = _seed_org_with_owner()[:2]
        tenancy_services.set_organization_status(
            org, active=False, actor=self.admin, reason="Payment overdue"
        )
        resp1 = self.api.delete(f"/api/v1/platform/organizations/{org.pk}/")
        assert resp1.status_code == 200

        resp2 = self.api.delete(f"/api/v1/platform/organizations/{org.pk}/")
        assert resp2.status_code == 404


@pytest.mark.django_db
class TestDEF004DEF005DEF006OpenAPIAndRouting:
    """DEF-004, DEF-005, DEF-006: OpenAPI schema matches callable routes with no // or stale set_status/."""

    def test_openapi_schema_routes_and_provisional_checklist(self):
        admin = User.objects.create_superuser(
            email=f"qa-schema-{uuid.uuid4().hex[:6]}@test.local",
            password="TestPass123!",
        )
        api = _api_client_for(admin)
        resp = api.get("/api/v1/schema/", HTTP_ACCEPT="application/json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})

        # DEF-004: Zero double-slash paths anywhere in OpenAPI spec
        assert [p for p in paths if "//" in p] == []

        # DEF-005: provisional-checklist documented with request + 200 response
        prov_path = "/api/v1/work-orders/{id}/provisional-checklist/"
        assert prov_path in paths
        assert "post" in paths[prov_path]
        assert "requestBody" in paths[prov_path]["post"]
        assert "200" in paths[prov_path]["post"]["responses"]

        # DEF-006: status/ documented in OpenAPI, set_status/ absent from OpenAPI
        status_path = "/api/v1/platform/organizations/{id}/status/"
        assert status_path in paths
        assert "post" in paths[status_path]
        assert "patch" in paths[status_path]
        assert "/api/v1/platform/organizations/{id}/set_status/" not in paths

    def test_platform_status_and_legacy_set_status_routes_resolve(self):
        fake_uuid = str(uuid.uuid4())
        status_match = resolve(f"/api/v1/platform/organizations/{fake_uuid}/status/")
        assert status_match is not None
        assert status_match.func.actions.get("post") == "set_status"

        legacy_match = resolve(f"/api/v1/platform/organizations/{fake_uuid}/set_status/")
        assert legacy_match is not None
        assert legacy_match.func.actions.get("post") == "set_status"

    def test_def004_platform_status_returns_200_not_html_403(self):
        org, _, _ = _seed_org_with_owner()
        admin = User.objects.create_superuser(
            email=f"qa-plat2-{uuid.uuid4().hex[:6]}@test.local",
            password="TestPass123!",
            is_platform_admin=True,
        )
        api = _api_client_for(admin)
        resp = api.post(
            f"/api/v1/platform/organizations/{org.pk}/status/",
            {"active": False, "reason": "QA suspend check"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUSPENDED"


@pytest.mark.django_db
def test_def007_all_five_list_endpoints_scale_with_constant_queries():
    """DEF-007: /requests/, /service-requests/, /incidents/, /workorders/, /work-orders/ execute O(1) SQL queries."""
    org, owner, owner_m = _seed_org_with_owner()
    site = Site.objects.create(organization=org, code="DEF7-S1", name="DEF7 Site")
    cat = asset_services.create_category(org, name="DEF7 Assets", actor=owner)
    asset = asset_services.create_asset(org, site=site, category=cat, actor=owner, asset_tag="DEF7-A1", name="DEF7 A1")
    api = _api_client_for(owner, org)

    def _seed_one(idx: int):
        incident_services.create_request(
            org,
            asset=asset,
            reporter=owner_m,
            title=f"DEF7 SR {idx}",
            severity="MEDIUM",
            override_duplicate=True,
            override_reason="DEF7 query scaling test",
            actor=owner,
        )
        wo_services.create_work_order(
            org,
            site_id=site.pk,
            asset=asset,
            membership=owner_m,
            actor=owner,
            title=f"DEF7 WO {idx}",
            work_type=WorkOrder.WorkType.CORRECTIVE,
            priority=WorkOrder.Priority.HIGH,
        )

    for i in range(2):
        _seed_one(i)

    endpoints = [
        "/api/v1/requests/",
        "/api/v1/service-requests/",
        "/api/v1/incidents/",
        "/api/v1/workorders/",
        "/api/v1/work-orders/",
    ]
    # Warm caches/content-types before measuring
    for ep in endpoints:
        assert api.get(ep).status_code == 200

    def _count_queries(ctx: CaptureQueriesContext) -> int:
        return sum(
            1
            for q in ctx.captured_queries
            if not q["sql"].lstrip().upper().startswith(("SAVEPOINT ", "RELEASE SAVEPOINT "))
        )

    baseline_counts = {}
    for ep in endpoints:
        with CaptureQueriesContext(connection) as ctx:
            resp = api.get(ep)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2
        baseline_counts[ep] = _count_queries(ctx)

    for i in range(2, 8):
        _seed_one(i)

    for ep in endpoints:
        with CaptureQueriesContext(connection) as ctx:
            resp = api.get(ep)
        assert resp.status_code == 200
        assert resp.json()["count"] == 8
        actual = _count_queries(ctx)
        assert actual == baseline_counts[ep], (
            f"[DEF-007] Query count grew on {ep}: {baseline_counts[ep]} (2 rows) -> {actual} (8 rows)"
        )
