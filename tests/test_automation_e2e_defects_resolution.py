import datetime
from decimal import Decimal

import pytest
from django.test import Client
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventory.models import Part, Warehouse
from apps.notifications.models import Notification
from apps.sites.models import Shift as SiteShift
from apps.tenancy.models import Membership
from apps.workorders.models import TechnicianProfile as WOTechnicianProfile


@pytest.mark.django_db
def test_def001_downtime_returns_200_null_contract(make_org, make_member, make_site, make_asset, as_user):
    """DEF-001 (TC-API-156-P): Missing downtime record returns 200 with null fields envelope."""
    from apps.incidents import services as inc_services
    org = make_org("DEF001 Org", "owner@def001.test")
    site = make_site(org, "S-001", "Site 001")
    asset = make_asset(org, site, "A-001")
    member = make_member(org, "tech@def001.test", "technician")
    sr = inc_services.create_request(
        org, asset=asset, title="Downtime Test", severity="LOW", service_impact="NONE",
        reporter=member, actor=member.user,
    )
    client = as_user(member.user, org)
    for path in (f"/api/v1/requests/{sr.pk}/downtime/", f"/api/v1/service-requests/{sr.pk}/downtime/"):
        resp = client.get(path)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data.get("id") is None
        assert data.get("started_at") is None
        assert data.get("ended_at") is None


@pytest.mark.django_db
def test_def002_portal_request_isolation(make_org, make_site, make_asset):
    """DEF-002 (TC-API-252-P, 253-P): Portal requests must be isolated per client account."""
    from apps.incidents import services as inc_services
    from apps.portal import selectors as portal_selectors
    from apps.portal.models import PortalAccount

    org = make_org("DEF002 Org", "owner@def002.test")
    site = make_site(org, "S-002", "Site 002")
    asset = make_asset(org, site, "A-002")

    user_a = User.objects.create_user(email="clienta@def002.test", password="Password123!")
    client_a_member = Membership.objects.create(organization=org, user=user_a, status=Membership.Status.ACTIVE)
    PortalAccount.objects.create(organization=org, membership=client_a_member, company_name="Acme Corp")

    user_b = User.objects.create_user(email="clientb@def002.test", password="Password123!")
    client_b_member = Membership.objects.create(organization=org, user=user_b, status=Membership.Status.ACTIVE)
    PortalAccount.objects.create(organization=org, membership=client_b_member, company_name="Beta LLC")

    sr_a = inc_services.create_request(
        org, asset=asset, title="Request from A", severity="LOW", service_impact="NONE",
        reporter=client_a_member, actor=client_a_member.user,
    )

    # Client A can see their request
    req_a = portal_selectors.get_client_request(client_a_member, sr_a.pk)
    assert req_a is not None
    assert req_a.pk == sr_a.pk

    # Client B cannot see Client A's request
    req_b = portal_selectors.get_client_request(client_b_member, sr_a.pk)
    assert req_b is None


@pytest.mark.django_db
def test_def003_workspace_shift_and_technician_cross_module(make_org, make_member, make_site, as_user):
    """DEF-003 (TC-API-504-P, 508-P): Workspace shift and technician endpoints support cross-module records."""
    org = make_org("DEF003 Org", "owner@def003.test")
    site = make_site(org, "S-003", "Site 003")
    admin = make_member(org, "admin@def003.test", "admin")

    # 1. Site shift accessible via workspace shift detail endpoint
    site_shift = SiteShift.objects.create(
        organization=org,
        site=site,
        name="Morning Shift",
        code="MS-01",
        start_time=datetime.time(8, 0),
        end_time=datetime.time(16, 0),
    )
    client = as_user(admin.user, org)
    resp_shift = client.get(f"/api/v1/workspace/shifts/{site_shift.pk}/")
    assert resp_shift.status_code == status.HTTP_200_OK
    assert resp_shift.data["name"] == "Morning Shift"
    assert resp_shift.data["duration_hours"] == 8.0

    # 2. Workorders TechnicianProfile accessible via workspace technicians endpoint
    tech_member = make_member(org, "tech@def003.test", "technician")
    wo_profile, _ = WOTechnicianProfile.objects.get_or_create(
        organization=org,
        membership=tech_member,
        defaults={"skills": ["HVAC"], "notes": "Experienced tech"},
    )
    resp_tech = client.get(f"/api/v1/workspace/technicians/{wo_profile.pk}/")
    assert resp_tech.status_code == status.HTTP_200_OK
    assert resp_tech.data["email"] == tech_member.user.email


@pytest.mark.django_db
def test_def004_platform_organization_status_endpoint(make_org):
    """DEF-004 (TC-API-222-P): Platform organization status supports POST and double slashes."""
    org = make_org("DEF004 Org", "owner@def004.test")
    platform_admin = User.objects.create_superuser(
        email="platform_admin@def004.test",
        password="SuperPassword123!",
        is_platform_admin=True,
    )
    client = APIClient()
    client.force_authenticate(user=platform_admin)

    # Test POST with double slash
    resp = client.post(f"/api/v1/platform/organizations/{org.pk}//", {"status": "inactive"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    org.refresh_from_db()
    assert org.is_active is False

    # Test POST to status endpoint
    resp2 = client.post(f"/api/v1/platform/organizations/{org.pk}/status/", {"active": True}, format="json")
    assert resp2.status_code == status.HTTP_200_OK
    org.refresh_from_db()
    assert org.is_active is True


@pytest.mark.django_db
def test_def005_logout_unauthenticated_returns_401():
    """DEF-005 (TC-API-059-N01, 518-N01): Unauthenticated logout returns HTTP 401."""
    client = APIClient()
    for path in ("/api/v1/auth/logout/", "/auth/logout/"):
        resp = client.post(path, {"refresh": ""}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_def006_notifications_read_all_readonly_auditor_returns_403(make_org, make_member, as_user):
    """DEF-006 (TC-API-203-N05): Read-only audit role cannot call /notifications/read-all/ (HTTP 403)."""
    org = make_org("DEF006 Org", "owner@def006.test")
    auditor = make_member(org, "auditor@def006.test", "auditor")
    Notification.objects.create(
        organization=org,
        recipient=auditor.user,
        title="Test Notice",
        body="Audit body",
    )
    client = as_user(auditor.user, org)
    resp = client.post("/api/v1/notifications/read-all/", {}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_def007_inventory_workflow_balances_isolated_from_e2e_preconditions(make_org, make_member, make_site):
    """DEF-007 (TC-WF-INV-08): Workflow stock balances start clean from previous E2E test movements."""
    from apps.inventory import services as inv_services
    org = make_org("DEF007 Org", "owner@def007.test")
    site = make_site(org, "S-007", "Site 007")
    admin = make_member(org, "admin@def007.test", "admin")

    wh_a = Warehouse.objects.create(organization=org, site=site, name="WH-A", code="WHA-007")
    wh_b = Warehouse.objects.create(organization=org, site=site, name="WH-B", code="WHB-007")
    part = Part.objects.create(organization=org, name="Widget", part_number="WID-007")

    # Simulate Stage 4 residual synthetic test movements (98 in WH-A, 4 in WH-B)
    inv_services.receive(wh_a, part, 98, actor=admin.user, reference="E2E_SYNTHETIC_01")
    inv_services.receive(wh_b, part, 4, actor=admin.user, reference="E2E_SYNTHETIC_02")

    # Stage 5 Curated workflow: Receive 100 in WH-A
    inv_services.receive(wh_a, part, 100, actor=admin.user, reference="WF-RECEIVE-100")
    # Transfer 30 from WH-A to WH-B
    inv_services.transfer(wh_a, wh_b, part, 30, actor=admin.user, reason="Restock")
    # Adjust -10 in WH-A
    inv_services.adjust(wh_a, part, -10, reason="Damage", actor=admin.user)

    # Check final balances: WH-A = 60, WH-B = 30
    bal_a = wh_a.balances.get(part=part)
    bal_b = wh_b.balances.get(part=part)
    assert bal_a.on_hand == Decimal("60.00")
    assert bal_b.on_hand == Decimal("30.00")


@pytest.mark.django_db
def test_def008_ui_logout_get_ends_session_and_redirects_app(make_org):
    """DEF-008 (TC-UI-008): UI GET /accounts/logout/ ends session, navigating /app/ redirects to login."""
    org = make_org("DEF008 Org", "owner@def008.test")
    owner = Membership.objects.get(organization=org, user__email="owner@def008.test")

    client = Client()
    client.force_login(owner.user)

    # 1. User is authenticated and can access /app/
    resp_app1 = client.get("/app/")
    assert resp_app1.status_code == 200

    # 2. Logout via GET request
    resp_logout = client.get("/accounts/logout/")
    assert resp_logout.status_code in (302, 200)

    # 3. Navigating to /app/ redirects to login
    resp_app2 = client.get("/app/")
    assert resp_app2.status_code == 302
    assert "/accounts/login/" in resp_app2.headers.get("Location", "")
