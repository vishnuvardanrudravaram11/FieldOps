"""M05 read side: organization + site-scope restricted querysets (see ``sites.selectors``)."""
from __future__ import annotations

import uuid

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.files.models import Attachment
from apps.rbac import services as rbac
from apps.sites.selectors import scoped_get

from .models import Downtime, ServiceRequest, ServiceRequestComment, ServiceRequestHistory

ORDERINGS = {"-created_at": "-created_at", "created_at": "created_at", "all": "-created_at", "": "-created_at", "title": "title", "-title": "-title",
             "name": "title", "-name": "-title", "number": "number", "-number": "-number",
             "severity": "severity", "status": "status"}


def is_owned_asset_reporter(membership) -> bool:
    """Client requesters may create reports only for assets explicitly assigned to their membership."""
    if membership is None or not rbac.has_permission_anywhere(membership, "incident.report_owned"):
        return False
    return not rbac.has_permission_anywhere(membership, "incident.create")


def requests_for(membership, org, code: str = "incident.view"):
    qs = ServiceRequest.objects.for_organization(org).select_related(
        "asset", "site", "reported_by__user", "downtime", "organization"
    )
    from apps.rbac.models import MembershipRole

    role_keys = set(MembershipRole.objects.filter(membership=membership).values_list("role__system_key", flat=True))
    if "client_requester" in role_keys and not rbac.has_permission_anywhere(membership, "incident.create"):
        return qs.filter(reported_by=membership)
    # Technician templates historically also carried ``incident.view``. Keep the visible request set limited to
    # their own reports and assigned work even if an additive role sync left that older grant in place.
    if code == "incident.view":
        broader_roles = {"owner", "admin", "service_dispatcher", "operations_manager", "asset_manager", "maintenance_planner",
                         "supervisor", "stores_manager", "stores_inventory", "service_manager", "auditor", "compliance"}
        if "technician" in role_keys and not (role_keys & broader_roles):
            code = "incident.view_assigned"
    if code == "incident.view_assigned":
        cond = Q(pk__isnull=True)  # matches nothing
        full = rbac.site_scope(membership, "incident.view")
        if full.all_sites:
            return qs
        if full.site_ids:
            cond |= Q(site_id__in=full.site_ids)
        mine = rbac.site_scope(membership, "incident.view_assigned")
        linked = Q(reported_by=membership)
        if apps.is_installed("apps.workorders"):  # M06: the source of work assigned to oneself
            from apps.workorders.models import WorkOrder

            assigned_source_numbers = WorkOrder.objects.for_organization(org).filter(
                assigned_to=membership,
                source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT),
            ).values("source_reference")
            linked |= Q(number__in=assigned_source_numbers)
        if mine.all_sites:
            cond |= linked
        elif mine.site_ids:
            cond |= linked & Q(site_id__in=mine.site_ids)
        return qs.filter(cond).distinct()
    return rbac.site_scope(membership, code).filter(qs, "site_id")


def get_request(membership, org, pk, code: str = "incident.view") -> ServiceRequest:
    return scoped_get(requests_for(membership, org, code), pk, "Request")


def _uuid_or_none(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def filter_requests(qs, params):
    for param, field in (("site", "site_id"), ("asset", "asset_id"), ("reported_by", "reported_by_id")):
        value = (params.get(param) or "").strip()
        if value:
            parsed = _uuid_or_none(value)
            qs = qs.filter(**{field: parsed}) if parsed else qs.none()
    for param, field, choices in (("status", "status", ServiceRequest.Status.values),
                                  ("severity", "severity", ServiceRequest.Severity.values),
                                  ("kind", "kind", ServiceRequest.Kind.values)):
        value = (params.get(param) or "").strip()
        if value:
            qs = qs.filter(**{field: value}) if value in choices else qs.none()
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q) | Q(asset__asset_tag__icontains=q)
                       | Q(asset__name__icontains=q))
    return qs.order_by(ORDERINGS.get(params.get("ordering") or "", "-created_at"), "-id")


def history_for(org, sr: ServiceRequest):
    return ServiceRequestHistory.objects.for_organization(org).filter(request=sr).select_related("changed_by")


def downtime_for(org, sr: ServiceRequest) -> Downtime | None:
    return Downtime.objects.for_organization(org).filter(request=sr).first()


def evidence_for(org, sr: ServiceRequest):
    return Attachment.objects.for_organization(org).filter(
        content_type=ContentType.objects.get_for_model(ServiceRequest), object_id=str(sr.pk)).select_related(
        "uploaded_by")


def comments_for(membership, org, sr: ServiceRequest):
    qs = ServiceRequestComment.objects.for_organization(org).filter(request=sr).select_related(
        "author", "author_membership__user"
    ).order_by("created_at", "id")
    from apps.ui.utils import is_client_membership
    if is_client_membership(membership):
        return qs.filter(is_internal=False)
    return qs


def attach_linked_work_orders(org, requests) -> dict:
    """Batch-fetch linked WorkOrders for a page of ServiceRequests in a single query.

    Populates ``sr.linked_work_order`` on every request and returns
    ``{sr.pk: [{"id", "number", "status"}, ...]}`` sorted by ``created_at``.
    """
    sr_list = list(requests)
    if not sr_list or not apps.is_installed("apps.workorders"):
        for sr in sr_list:
            sr.linked_work_order = None
        return {}

    from collections import defaultdict

    from apps.workorders.models import WorkOrder

    sr_ids = [sr.pk for sr in sr_list]
    sr_numbers = [sr.number for sr in sr_list]
    wos = list(
        WorkOrder.objects.for_organization(org)
        .filter(
            Q(source_request_id__in=sr_ids)
            | Q(source_id__in=sr_ids)
            | Q(
                source_reference__in=sr_numbers,
                source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT),
            )
        )
        .select_related("assigned_to__user")
        .order_by("created_at")
    )

    by_sr_id = defaultdict(list)
    by_sr_num = defaultdict(list)
    seen_by_sr = defaultdict(set)
    by_id_lookup = {sr.pk: sr for sr in sr_list}
    by_num_lookup = {sr.number: sr for sr in sr_list}

    for wo in wos:
        targets = []
        if wo.source_request_id and wo.source_request_id in by_id_lookup:
            targets.append(by_id_lookup[wo.source_request_id])
        if wo.source_id and wo.source_id in by_id_lookup:
            targets.append(by_id_lookup[wo.source_id])
        if (
            wo.source_reference
            and wo.source_type in (WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT)
            and wo.source_reference in by_num_lookup
        ):
            targets.append(by_num_lookup[wo.source_reference])
        for sr in targets:
            if wo.pk not in seen_by_sr[sr.pk]:
                seen_by_sr[sr.pk].add(wo.pk)
                by_sr_id[sr.pk].append(wo)
                if (
                    wo.source_reference == sr.number
                    and wo.source_type in (WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT)
                ):
                    by_sr_num[sr.pk].append(wo)

    work_orders_payload = {}
    for sr in sr_list:
        matched = by_sr_id.get(sr.pk, [])
        live = next(
            (w for w in matched if w.status not in (WorkOrder.Status.CANCELLED, WorkOrder.Status.CLOSED)),
            None,
        )
        sr.linked_work_order = live if live is not None else (matched[-1] if matched else None)
        serial_list = by_sr_num.get(sr.pk, [])
        work_orders_payload[sr.pk] = [
            {"id": str(w.pk), "number": w.order_number, "status": w.status}
            for w in serial_list
        ]
    return work_orders_payload
