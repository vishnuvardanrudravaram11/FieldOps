"""Automated regression suite verifying resolution of all smoke test report defects.

Covers:
- DEF-001, DEF-002: Token authentication & logout revocation scoping
- DEF-003: POST /api/v1/workspace/profile/availability/ with non-dict input returns 400 (not 500)
- DEF-004: GET /api/v1/incidents/{id}/downtime/ returns 200 well-formed downtime object (not 404)
- DEF-005: POST /api/v1/notifications/read-all/ with non-dict input returns 400
- DEF-006 - DEF-009: Elimination of double slashes (//) in OpenAPI routes
- DEF-010: POST /api/v1/platform/users/ with non-dict input returns 400 (not 500)
- DEF-011: POST /api/v1/sla-trackings/process/ with non-dict input returns 400
- DEF-012, DEF-013, DEF-021: POST /api/v1/work-orders/{id}/transition/ with non-dict input returns 400/404 (not 500)
- DEF-014: OpenAPI schema contains /health/live/ and /health/ready/
- DEF-016: GET /api/v1/users/ as Client returns 403
- DEF-017: GET /api/v1/audit-logs/ as Client returns 403
- DEF-018: GET /api/v1/roles/ as Client returns 403
- DEF-019: POST /api/v1/warehouses/ with [] as Client returns 403
- DEF-020, DEF-024: GET /api/v1/portal/accounts/ as Client returns 200
- FSM-DSH-0017: GET /api/v1/dashboards/ includes count and results list of sections
"""
import uuid

import pytest
import yaml
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.incidents.models import ServiceRequest
from apps.portal.models import PortalAccount
from apps.rbac import services as rbac
from apps.tenancy.models import Membership, Organization

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Password123!"


@pytest.fixture
def test_setup(db):
    org, _ = Organization.objects.get_or_create(
        slug="smoke-test-org",
        defaults={"name": "Smoke Test Organization"},
    )
    rbac.seed_system_roles(org, prune_extra=True)

    from apps.sites.models import Site
    site, _ = Site.objects.get_or_create(
        organization=org, code="SMK-01",
        defaults={"name": "Smoke Site"}
    )
    from apps.assets.models import Asset, AssetCategory
    cat, _ = AssetCategory.objects.get_or_create(
        organization=org, name="Smoke Category"
    )
    asset, _ = Asset.objects.get_or_create(
        organization=org, asset_tag="AST-01",
        defaults={"name": "Smoke Asset", "site": site, "category": cat}
    )

    # 1. Admin / Owner user
    owner_user = User.objects.filter(email="owner@smoketest.example.com").first() or User.objects.create_user(
        email="owner@smoketest.example.com", password=PASSWORD, full_name="Smoke Owner"
    )
    owner_membership, _ = Membership.objects.unscoped().get_or_create(
        organization=org, user=owner_user, defaults={"status": Membership.Status.ACTIVE}
    )
    owner_role = rbac.system_role_by_key(org, "owner")
    rbac.set_membership_roles(owner_membership, [owner_role], actor=None, system=True)

    # 2. Client / Requester user
    client_user = User.objects.filter(email="client.requester@smoketest.example.com").first() or User.objects.create_user(
        email="client.requester@smoketest.example.com", password=PASSWORD, full_name="Client Requester"
    )
    client_membership, _ = Membership.objects.unscoped().get_or_create(
        organization=org, user=client_user, defaults={"status": Membership.Status.ACTIVE}
    )
    client_role = rbac.system_role_by_key(org, "client_requester")
    rbac.set_membership_roles(client_membership, [client_role], actor=None, system=True)
    portal_account, _ = PortalAccount.objects.unscoped().get_or_create(
        organization=org, membership=client_membership,
        defaults={"company_name": "Smoke Client Corp", "is_enabled": True}
    )

    # 3. Platform Admin user
    platform_admin = User.objects.filter(email="platform.admin@smoketest.example.com").first() or User.objects.create_user(
        email="platform.admin@smoketest.example.com", password=PASSWORD, full_name="Platform Admin",
        is_platform_admin=True, is_staff=True, is_superuser=True
    )

    # 4. Technician user
    tech_user = User.objects.filter(email="tech@smoketest.example.com").first() or User.objects.create_user(
        email="tech@smoketest.example.com", password=PASSWORD, full_name="Field Tech"
    )
    tech_membership, _ = Membership.objects.unscoped().get_or_create(
        organization=org, user=tech_user, defaults={"status": Membership.Status.ACTIVE}
    )
    tech_role = rbac.system_role_by_key(org, "technician")
    rbac.set_membership_roles(tech_membership, [tech_role], actor=None, system=True)

    return {
        "org": org,
        "site": site,
        "asset": asset,
        "owner_user": owner_user,
        "owner_membership": owner_membership,
        "client_user": client_user,
        "platform_admin": platform_admin,
        "tech_user": tech_user,
    }


def _auth_client(user, org=None):
    client = APIClient()
    client.force_authenticate(user=user)
    if org:
        client.defaults["HTTP_X_ORGANIZATION"] = org.slug
    return client


def test_def_016_client_forbidden_from_users(test_setup):
    """DEF-016: GET /api/v1/users/ as Client returns 403."""
    c = _auth_client(test_setup["client_user"], test_setup["org"])
    res = c.get("/api/v1/users/")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_def_017_client_forbidden_from_audit_logs(test_setup):
    """DEF-017: GET /api/v1/audit-logs/ as Client returns 403."""
    c = _auth_client(test_setup["client_user"], test_setup["org"])
    res = c.get("/api/v1/audit-logs/")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_def_018_client_forbidden_from_roles(test_setup):
    """DEF-018: GET /api/v1/roles/ as Client returns 403."""
    c = _auth_client(test_setup["client_user"], test_setup["org"])
    res = c.get("/api/v1/roles/")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_def_019_client_cannot_create_warehouse(test_setup):
    """DEF-019: POST /api/v1/warehouses/ with [] as Client returns 403 (not 400)."""
    c = _auth_client(test_setup["client_user"], test_setup["org"])
    res = c.post("/api/v1/warehouses/", data=[], format="json")
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_def_020_def_024_client_can_read_portal_accounts(test_setup):
    """DEF-020 & DEF-024: GET /api/v1/portal/accounts/ as Client returns 200."""
    c = _auth_client(test_setup["client_user"], test_setup["org"])
    res = c.get("/api/v1/portal/accounts/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    results = data if isinstance(data, list) else data.get("results", [])
    assert len(results) >= 1
    assert results[0]["company_name"] == "Smoke Client Corp"


def test_def_003_technician_availability_malformed_body(test_setup):
    """DEF-003: POST /api/v1/workspace/profile/availability/ with [] returns 400 (not 500)."""
    c = _auth_client(test_setup["tech_user"], test_setup["org"])
    res = c.post("/api/v1/workspace/profile/availability/", data=[], format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_def_010_platform_users_malformed_body(test_setup):
    """DEF-010: POST /api/v1/platform/users/ with [] returns 400 (not 500)."""
    c = _auth_client(test_setup["platform_admin"])
    res = c.post("/api/v1/platform/users/", data=[], format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_def_012_def_013_work_order_transition_malformed_body(test_setup):
    """DEF-012, DEF-013, DEF-021: POST /api/v1/work-orders/{id}/transition/ with [] returns 400/404 (not 500)."""
    c = _auth_client(test_setup["owner_user"], test_setup["org"])
    fake_id = uuid.uuid4()
    res = c.post(f"/api/v1/work-orders/{fake_id}/transition/", data=[], format="json")
    assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND)
    assert res.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


def test_def_005_notifications_read_all_list_rejected(test_setup):
    """DEF-005: POST /api/v1/notifications/read-all/ with [] returns 400."""
    c = _auth_client(test_setup["owner_user"], test_setup["org"])
    res = c.post("/api/v1/notifications/read-all/", data=[], format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_def_011_sla_tracking_process_list_rejected(test_setup):
    """DEF-011: POST /api/v1/sla-trackings/process/ with [] returns 400."""
    c = _auth_client(test_setup["owner_user"], test_setup["org"])
    res = c.post("/api/v1/sla-trackings/process/", data=[], format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_def_004_downtime_returns_200_when_no_record(test_setup):
    """DEF-004: GET /api/v1/incidents/{id}/downtime/ returns 200 with downtime fields."""
    sr = ServiceRequest.objects.create(
        organization=test_setup["org"],
        site=test_setup["site"],
        asset=test_setup["asset"],
        title="Smoke Test Incident",
        description="Testing downtime return",
        reported_by=test_setup["owner_membership"],
        occurred_at=timezone.now(),
    )

    c = _auth_client(test_setup["owner_user"], test_setup["org"])
    res = c.get(f"/api/v1/incidents/{sr.pk}/downtime/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "started_at" in data
    assert "duration_seconds" in data


def test_fsm_dsh_0017_dashboards_catalog_discoverability(test_setup):
    """FSM-DSH-0017: GET /api/v1/dashboards/ returns discoverable results and sections."""
    c = _auth_client(test_setup["owner_user"], test_setup["org"])
    res = c.get("/api/v1/dashboards/")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    assert data["results"][0]["id"] == "operations"

    res_sec = c.get("/api/v1/dashboards/operations/")
    assert res_sec.status_code == status.HTTP_200_OK


def test_def_006_to_009_def_014_openapi_schema():
    """DEF-006 - DEF-009 & DEF-014: OpenAPI schema contains no double slashes and has health routes."""
    c = Client()
    res = c.get("/api/v1/schema/", HTTP_HOST="localhost", follow=True)
    assert res.status_code == 200
    data = yaml.safe_load(res.content)
    paths = data.get("paths", {})

    double_slashes = [p for p in paths if "//" in p]
    assert double_slashes == []

    health_paths = [p for p in paths if "/health/" in p]
    assert len(health_paths) >= 2


def test_def_001_def_002_token_obtain_and_logout(test_setup):
    """DEF-001 & DEF-002: Obtain token, verify /me, and logout without global session invalidation."""
    client = APIClient()
    # 1. Obtain token
    res = client.post(
        "/api/v1/auth/token/",
        data={"email": test_setup["owner_user"].email, "password": PASSWORD},
        format="json",
    )
    assert res.status_code == status.HTTP_200_OK
    token_data = res.json()
    access = token_data["access"]
    refresh = token_data["refresh"]

    # 2. Verify identity on /api/v1/auth/me/
    auth_client = APIClient()
    auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    res_me = auth_client.get("/api/v1/auth/me/")
    assert res_me.status_code == status.HTTP_200_OK
    assert res_me.json()["email"] == test_setup["owner_user"].email

    # 3. Test logout with refresh token
    res_logout = client.post("/api/v1/auth/logout/", data={"refresh": refresh}, format="json")
    assert res_logout.status_code == status.HTTP_200_OK
    assert "Logged out successfully" in res_logout.json().get("message", "")
