"""TDD regression and query-scaling tests for list endpoints (DEF-004, DEF-005, RT-DEF004, DEF-001)."""

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.checklists import services as checklist_services
from apps.contracts.models import CoverageAgreement, CoverageExclusion, CoveredAsset, ServiceProvider
from apps.files import services as file_services
from apps.incidents import services as incident_services
from apps.maintenance import services as maintenance_services
from apps.portal import services as portal_services
from apps.portal.models import PortalAssetGrant
from apps.sla.models import SLAPauseEvent, SLATracking
from apps.workorders import services as workorder_services
from apps.workorders.models import WorkOrder
from apps.workspace.models import TechnicianProfile

pytestmark = pytest.mark.django_db


def _non_savepoint_queries(ctx: CaptureQueriesContext) -> list[str]:
    return [
        q["sql"]
        for q in ctx.captured_queries
        if not q["sql"].lstrip().upper().startswith(("SAVEPOINT ", "RELEASE SAVEPOINT "))
    ]


def _write_queries(ctx: CaptureQueriesContext) -> list[str]:
    return [
        sql
        for sql in _non_savepoint_queries(ctx)
        if sql.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE "))
    ]


def test_portal_requests_list_constant_queries_def004(sla_, make_portal_client, as_user):
    """DEF-004: GET /api/v1/portal/requests/ and /requests scale in O(1) queries with SLA & attachments."""
    org = sla_["org"]
    asset = sla_["asset"]
    client_user, client_membership, portal_account = make_portal_client(org, "portal.perf@alpha.test")
    PortalAssetGrant.objects.get_or_create(organization=org, portal_account=portal_account, asset=asset)
    api = as_user(client_user, org)

    def _create_portal_request(idx: int):
        sr = portal_services.create_portal_service_request(
            client_membership,
            asset=asset,
            title=f"Portal Perf Request {idx}",
            severity="HIGH",
            override_duplicate=True,
            override_reason="Perf test",
        )
        if idx % 2 == 0:
            file_services.attach(
                SimpleUploadedFile(f"p{idx}.txt", b"portal proof"),
                target=sr,
                organization=org,
                user=client_user,
            )
        return sr

    for i in range(2):
        _create_portal_request(i)

    # Warm up auth/cache/content-type lookups
    assert api.get("/api/v1/portal/requests/").status_code == 200

    with CaptureQueriesContext(connection) as q_small:
        r_small = api.get("/api/v1/portal/requests/")
    assert r_small.status_code == 200
    assert r_small.json()["count"] == 2

    for i in range(2, 10):
        _create_portal_request(i)

    with CaptureQueriesContext(connection) as q_large:
        r_large = api.get("/api/v1/portal/requests/")
    assert r_large.status_code == 200
    data_large = r_large.json()
    assert data_large["count"] == 10
    assert any(item["attachments_count"] == 1 for item in data_large["results"])
    assert any(item["sla_commitment"] and item["sla_commitment"]["has_sla"] for item in data_large["results"])

    with CaptureQueriesContext(connection) as q_noslash:
        r_noslash = api.get("/api/v1/portal/requests")
    assert r_noslash.status_code == 200

    small_sql = _non_savepoint_queries(q_small)
    large_sql = _non_savepoint_queries(q_large)
    noslash_sql = _non_savepoint_queries(q_noslash)
    assert len(large_sql) == len(small_sql), f"N+1 detected: 2 rows={len(small_sql)}, 10 rows={len(large_sql)}"
    assert len(noslash_sql) == len(small_sql)


def test_workorders_list_constant_queries_and_no_writes_def005(p3, as_user, owner_a):
    """DEF-005: GET /api/v1/work-orders/ & /workorders/ run O(1) queries, no DISTINCT, and no UPDATEs."""
    org = p3["org"]
    site = p3["site"]
    asset = p3["asset"]
    planner = p3["planner"]
    tech = p3["tech"]

    tmpl = checklist_services.create_template(
        org, name="Corrective Safety Gate", work_type="CORRECTIVE", is_required=True, actor=owner_a
    )
    checklist_services.add_item(tmpl, actor=owner_a, prompt="Lockout verified?", item_type="BOOLEAN")
    checklist_services.activate_template(tmpl, actor=owner_a)

    api = as_user(owner_a, org)

    def _create_wo(idx: int):
        wo = workorder_services.create_work_order(
            org,
            site_id=site.pk,
            membership=planner,
            actor=planner.user,
            title=f"Perf Work Order {idx}",
            asset=asset,
            work_type=WorkOrder.WorkType.CORRECTIVE,
            priority=WorkOrder.Priority.HIGH,
        )
        if idx % 2 == 1:
            start = timezone.now() + timedelta(days=idx + 1)
            wo = workorder_services.plan_work_order(
                wo, membership=planner, actor=planner.user, planned_start=start,
                planned_end=start + timedelta(hours=2), due_at=start + timedelta(days=1), estimated_hours=2,
            )
            wo = workorder_services.assign_work_order(wo, membership=planner, actor=planner.user, assignee_id=tech.pk)
            wo = workorder_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
            wo = workorder_services.start_work_order(wo, membership=tech, actor=tech.user)
            checklist_services.start_inspection(org, template=tmpl, membership=tech, actor=tech.user, work_order=wo)
        return wo

    for i in range(2):
        _create_wo(i)

    assert api.get("/api/v1/work-orders/").status_code == 200

    with CaptureQueriesContext(connection) as q_small:
        r_small = api.get("/api/v1/work-orders/")
    assert r_small.status_code == 200
    assert r_small.json()["count"] == 2

    for i in range(2, 10):
        _create_wo(i)

    with CaptureQueriesContext(connection) as q_large:
        r_large = api.get("/api/v1/work-orders/")
    assert r_large.status_code == 200
    assert r_large.json()["count"] == 10

    with CaptureQueriesContext(connection) as q_alias:
        r_alias = api.get("/api/v1/workorders/")
    assert r_alias.status_code == 200
    assert r_alias.json()["count"] == 10

    small_sql = _non_savepoint_queries(q_small)
    large_sql = _non_savepoint_queries(q_large)
    alias_sql = _non_savepoint_queries(q_alias)

    assert not any(sql.lstrip().upper().startswith("UPDATE ") for sql in large_sql), "GET list must not UPDATE rows"
    assert not any("SELECT DISTINCT" in sql.upper() for sql in large_sql), "Redundant DISTINCT on workorders list"
    assert len(large_sql) == len(small_sql), f"N+1 detected: 2 rows={len(small_sql)}, 10 rows={len(large_sql)}"
    assert len(alias_sql) == len(small_sql)


def test_incidents_list_constant_queries_rt_def004(p3, as_user, owner_a):
    """RT-DEF004-incidents: GET /api/v1/incidents/ scales in O(1) queries with linked work orders."""
    org = p3["org"]
    asset = p3["asset"]
    ops = p3["ops"]
    planner = p3["planner"]
    api = as_user(owner_a, org)

    def _create_sr_with_wo(idx: int):
        sr = incident_services.create_request(
            org,
            asset=asset,
            reporter=ops,
            actor=ops.user,
            title=f"Incident Perf {idx}",
            severity="HIGH",
            override_duplicate=True,
            override_reason="Perf test",
        )
        sr = incident_services.transition(sr, action="triage", actor=ops.user)
        sr = incident_services.transition(sr, action="approve", actor=ops.user)
        incident_services.create_work_order_for_request(sr, actor=planner.user, membership=planner)
        return sr

    for i in range(2):
        _create_sr_with_wo(i)

    assert api.get("/api/v1/incidents/").status_code == 200

    with CaptureQueriesContext(connection) as q_small:
        r_small = api.get("/api/v1/incidents/")
    assert r_small.status_code == 200

    for i in range(2, 10):
        _create_sr_with_wo(i)

    with CaptureQueriesContext(connection) as q_large:
        r_large = api.get("/api/v1/incidents/")
    assert r_large.status_code == 200
    results = r_large.json()["results"]
    assert all(len(item["work_orders"]) == 1 and item["linked_work_order"] is not None for item in results)

    small_sql = _non_savepoint_queries(q_small)
    large_sql = _non_savepoint_queries(q_large)
    assert len(large_sql) == len(small_sql), f"N+1 detected: 2 rows={len(small_sql)}, 10 rows={len(large_sql)}"


def test_checklist_templates_and_members_constant_queries_rt_def004(p3, make_member, as_user, owner_a):
    """RT-DEF004-checklist-templates & RT-DEF004-members scale in O(1) queries."""
    org = p3["org"]
    api = as_user(owner_a, org)

    for i in range(2):
        t = checklist_services.create_template(org, name=f"Tmpl Perf {i}", actor=owner_a)
        checklist_services.add_item(t, actor=owner_a, prompt="Step 1", item_type="BOOLEAN")
        checklist_services.add_item(t, actor=owner_a, prompt="Step 2", item_type="TEXT")
        make_member(org, f"perf.member.{i}@alpha.test", "technician")

    assert api.get("/api/v1/checklist-templates/").status_code == 200
    assert api.get("/api/v1/members/").status_code == 200

    with CaptureQueriesContext(connection) as q_tmpl_small:
        r_ts = api.get("/api/v1/checklist-templates/")
    with CaptureQueriesContext(connection) as q_mem_small:
        r_ms = api.get("/api/v1/members/")
    assert r_ts.status_code == 200 and r_ms.status_code == 200

    for i in range(2, 10):
        t = checklist_services.create_template(org, name=f"Tmpl Perf {i}", actor=owner_a)
        checklist_services.add_item(t, actor=owner_a, prompt="Step 1", item_type="BOOLEAN")
        make_member(org, f"perf.member.{i}@alpha.test", "technician")

    with CaptureQueriesContext(connection) as q_tmpl_large:
        r_tl = api.get("/api/v1/checklist-templates/")
    with CaptureQueriesContext(connection) as q_mem_large:
        r_ml = api.get("/api/v1/members/")
    assert r_tl.status_code == 200 and r_ml.status_code == 200

    assert len(_non_savepoint_queries(q_tmpl_large)) == len(_non_savepoint_queries(q_tmpl_small))
    assert len(_non_savepoint_queries(q_mem_large)) == len(_non_savepoint_queries(q_mem_small))


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/sites/",
        "/api/v1/zones/",
        "/api/v1/assets/",
        "/api/v1/maintenance-plans/",
        "/api/v1/incidents/",
        "/api/v1/work-orders/",
        "/api/v1/checklist-templates/",
        "/api/v1/parts/",
        "/api/v1/warehouses/",
        "/api/v1/stock-balances/",
        "/api/v1/agreements/",
        "/api/v1/audit-logs/",
    ],
)
def test_search_query_sql_fragment_safe_in_django_functional_def001(org_a, owner_a, as_user, endpoint):
    """Functional Report DEF-001: Django endpoints handle ?q='; DROP TABLE x;-- safely with HTTP 200."""
    api = as_user(owner_a, org_a)
    resp = api.get(endpoint, {"q": "'; DROP TABLE x;--"})
    assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}: {resp.content[:200]}"


def test_agreements_and_expiring_list_constant_queries(org_a, site_a1, owner_a, make_asset, as_user):
    """GET /api/v1/agreements/ and /expiring/ execute O(1) queries with exclusions, covered assets, and renewals."""
    provider = ServiceProvider.objects.create(
        organization=org_a, name="O1 Contract Care", contact_name="Dana", is_active=True,
    )
    today = date.today()
    prev = None

    def _seed(idx: int):
        nonlocal prev
        asset = make_asset(org_a, site_a1, f"CON-AST-{idx:02d}")
        agr = CoverageAgreement.objects.create(
            organization=org_a,
            provider=provider,
            site=site_a1,
            reference=f"CON-REF-{idx:03d}",
            title=f"Contract {idx}",
            kind=CoverageAgreement.Kind.AMC,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=15),
            renewal_alert_days=30,
            is_active=True,
            renewed_from=prev,
            created_by=owner_a,
        )
        CoverageExclusion.objects.create(organization=org_a, agreement=agr, work_type="EMERGENCY")
        CoveredAsset.objects.create(organization=org_a, agreement=agr, asset=asset)
        prev = agr

    for i in range(2):
        _seed(i)

    api = as_user(owner_a, org_a)
    with CaptureQueriesContext(connection) as q_list_2:
        r_list_2 = api.get("/api/v1/agreements/")
    with CaptureQueriesContext(connection) as q_exp_2:
        r_exp_2 = api.get("/api/v1/agreements/expiring/")
    assert r_list_2.status_code == 200 and r_exp_2.status_code == 200

    for i in range(2, 10):
        _seed(i)

    with CaptureQueriesContext(connection) as q_list_10:
        r_list_10 = api.get("/api/v1/agreements/")
    with CaptureQueriesContext(connection) as q_exp_10:
        r_exp_10 = api.get("/api/v1/agreements/expiring/")
    assert r_list_10.status_code == 200 and r_exp_10.status_code == 200

    assert len(_non_savepoint_queries(q_list_10)) == len(_non_savepoint_queries(q_list_2))
    assert len(_non_savepoint_queries(q_exp_10)) == len(_non_savepoint_queries(q_exp_2))
    assert _write_queries(q_list_10) == []
    assert _write_queries(q_exp_10) == []


def test_sla_trackings_and_maintenance_schedules_constant_queries(sla_, as_user):
    """GET /api/v1/sla-trackings/ and /maintenance-schedules/ scale in O(1) queries."""
    org = sla_["org"]
    owner = sla_["ops"].user
    now = timezone.now()
    today = date.today()

    def _seed(idx: int):
        asset = sla_["asset"] if idx == 0 else sla_["asset2"]
        sr = incident_services.create_request(
            org,
            asset=asset,
            reporter=sla_["ops"],
            title=f"SLA Scale SR {idx}",
            severity="HIGH",
            override_duplicate=True,
            override_reason="Perf test seed",
            actor=owner,
        )
        trk = SLATracking.objects.get(request=sr)
        SLAPauseEvent.objects.create(
            organization=org,
            tracking=trk,
            reason="Waiting spares",
            workflow_state="WORK_ORDER:ON_HOLD",
            started_at=now - timedelta(minutes=15),
            ended_at=now - timedelta(minutes=5),
            duration_seconds=600,
            paused_by=owner,
            approved_by=owner,
        )
        plan = maintenance_services.create_plan(org, asset=asset, name=f"Scale PM Plan {idx}", actor=owner)
        maintenance_services.create_schedule(
            plan,
            actor=owner,
            trigger_type="TIME",
            frequency="MONTHLY",
            interval_count=1,
            start_date=today,
        )

    for i in range(2):
        _seed(i)

    api = as_user(owner, org)
    with CaptureQueriesContext(connection) as q_sla_2:
        r_sla_2 = api.get("/api/v1/sla-trackings/")
    with CaptureQueriesContext(connection) as q_pm_2:
        r_pm_2 = api.get("/api/v1/maintenance-schedules/")
    assert r_sla_2.status_code == 200 and r_pm_2.status_code == 200

    for i in range(2, 10):
        _seed(i)

    with CaptureQueriesContext(connection) as q_sla_10:
        r_sla_10 = api.get("/api/v1/sla-trackings/")
    with CaptureQueriesContext(connection) as q_pm_10:
        r_pm_10 = api.get("/api/v1/maintenance-schedules/")
    assert r_sla_10.status_code == 200 and r_pm_10.status_code == 200

    assert len(_non_savepoint_queries(q_sla_10)) == len(_non_savepoint_queries(q_sla_2))
    assert len(_non_savepoint_queries(q_pm_10)) == len(_non_savepoint_queries(q_pm_2))
    assert _write_queries(q_sla_10) == []
    assert _write_queries(q_pm_10) == []


def test_technicians_bulk_init_and_constant_queries(org_a, owner_a, make_member, as_user):
    """GET /api/v1/workspace/technicians/ batch-creates missing profiles once and stays read-only/O(1) thereafter."""
    for i in range(2):
        make_member(org_a, f"tech.scale.{i}@alpha.test", "technician")
    assert TechnicianProfile.objects.filter(organization=org_a).count() == 0

    api = as_user(owner_a, org_a)
    with CaptureQueriesContext(connection) as q_cold_2:
        r_cold_2 = api.get("/api/v1/workspace/technicians/")
    assert r_cold_2.status_code == 200
    assert len(r_cold_2.json()) == 2
    assert len(_write_queries(q_cold_2)) <= 1

    with CaptureQueriesContext(connection) as q_warm_2:
        r_warm_2 = api.get("/api/v1/workspace/technicians/")
    assert r_warm_2.status_code == 200
    assert _write_queries(q_warm_2) == []

    for i in range(2, 10):
        make_member(org_a, f"tech.scale.{i}@alpha.test", "technician")

    with CaptureQueriesContext(connection) as q_cold_10:
        r_cold_10 = api.get("/api/v1/workspace/technicians/")
    assert r_cold_10.status_code == 200
    assert len(r_cold_10.json()) == 10
    assert len(_write_queries(q_cold_10)) <= 1

    with CaptureQueriesContext(connection) as q_warm_10:
        r_warm_10 = api.get("/api/v1/workspace/technicians/")
    assert r_warm_10.status_code == 200
    assert _write_queries(q_warm_10) == []
    assert len(_non_savepoint_queries(q_warm_10)) == len(_non_savepoint_queries(q_warm_2))


def test_work_order_detail_and_checklist_status_are_readonly(org_a, site_a1, owner_a, make_asset, as_user):
    """GET /api/v1/work-orders/{id}/ and /checklist-status/ must perform zero DB writes."""
    asset = make_asset(org_a, site_a1, "RO-WO-AST-01")
    wo = workorder_services.create_work_order(
        org_a,
        site=site_a1,
        asset=asset,
        title="Read-only GET verification WO",
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
        actor=owner_a,
    )
    api = as_user(owner_a, org_a)

    with CaptureQueriesContext(connection) as q_detail:
        r_detail = api.get(f"/api/v1/work-orders/{wo.pk}/")
    with CaptureQueriesContext(connection) as q_status:
        r_status = api.get(f"/api/v1/work-orders/{wo.pk}/checklist-status/")

    assert r_detail.status_code == 200
    assert r_status.status_code == 200
    assert "required" in r_status.json()
    assert _write_queries(q_detail) == []
    assert _write_queries(q_status) == []
