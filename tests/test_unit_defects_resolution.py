"""Unit Test Defect Resolution Verification Suite (Unit Testing Report Remediation)

Covers all 17 failed unit test cases and 4 defects from FieldOps_Nexus_Complete_Unit_Testing_Report:
- UT-SEC-058: Decimal-encoded loopback (http://2130706433/) rejected (DEF-001)
- UT-SEC-059: Short-form loopback (http://127.1/) rejected (DEF-001)
- UT-SEC-060: Hex-encoded loopback (http://0x7f.0.0.1/) rejected (DEF-001)
- UT-SEC-061: 0-host loopback (http://0/) rejected (DEF-001)
- UT-SEC-062: GCP metadata host (http://metadata.google.internal/) rejected (DEF-001)
- UT-WO-177: services.TRANSITIONS is consistent with workflow.WORK_ORDER_STATUS (DEF-002)
- UT-WO-040: Service layer accepts due == planned_end identically to serializer/form (DEF-003)
- UT-SER-028 to UT-SER-039: 10 Asset ModelSerializers build fields without ImproperlyConfigured (DEF-004)
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.assets.serializers import (
    AssetCategorySerializer,
    AssetComponentSerializer,
    AssetDetailSerializer,
    AssetDocumentSerializer,
    AssetHierarchyNodeSerializer,
    AssetListSerializer,
    AssetMeterReadingSerializer,
    AssetMeterSerializer,
    AssetSerializer,
    AssetStatusHistorySerializer,
)
from apps.core.api_views import WebhookEndpointSerializer
from apps.workorders import services as wo_services
from apps.workorders.models import WorkOrder
from apps.workorders.workflow import WORK_ORDER_STATUS

pytestmark = pytest.mark.django_db


# --- DEF-001: Webhook SSRF Obfuscated Address Rejection (UT-SEC-058 to UT-SEC-062) ---


@pytest.mark.parametrize(
    "target_url",
    [
        "http://2130706433/",
        "http://127.1/",
        "http://0x7f.0.0.1/",
        "http://0/",
        "http://metadata.google.internal/",
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/",
        "http://10.0.0.1/",
    ],
)
def test_webhook_url_obfuscated_loopback_rejected(target_url):
    """DEF-001 (UT-SEC-058..062): Serializer strictly rejects obfuscated loopback and metadata addresses."""
    ser = WebhookEndpointSerializer()
    with pytest.raises(ValidationError):
        ser.validate_target_url(target_url)


def test_webhook_url_valid_public_accepted():
    """DEF-001: Public webhook endpoints are accepted."""
    ser = WebhookEndpointSerializer()
    url = "https://api.github.com/webhook"
    assert ser.validate_target_url(url) == url


# --- DEF-002: Work Order Transition Consistency (UT-WO-177) ---


def test_transition_tables_consistent():
    """DEF-002 (UT-WO-177): services.TRANSITIONS + CANCELLABLE_STATUSES matches workflow.WORK_ORDER_STATUS."""
    combined_service_transitions = {}
    for status, targets in wo_services.TRANSITIONS.items():
        combined_service_transitions[status] = set(targets)
    for status in wo_services.CANCELLABLE_STATUSES:
        combined_service_transitions.setdefault(status, set()).add(WorkOrder.Status.CANCELLED)

    wf_transitions = {}
    for t in WORK_ORDER_STATUS.transitions:
        for src in t.sources:
            wf_transitions.setdefault(src, set()).add(t.target)

    assert combined_service_transitions == wf_transitions


# --- DEF-003: Schedule Window Boundary Consistency (UT-WO-040) ---


def test_due_equal_end_consistent_across_layers():
    """DEF-003 (UT-WO-040): due == planned_end is accepted by the service layer."""
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=4)
    due = end  # Exactly equal to planned_end

    # Should not raise ValidationFailed
    wo_services._validate_schedule_window(start, end, due, Decimal("2.0"))


def test_due_before_end_rejected():
    """DEF-003: due < planned_end is rejected with code due_not_after_end."""
    from apps.core.exceptions import ValidationFailed

    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=4)
    due = end - timedelta(minutes=1)

    with pytest.raises(ValidationFailed) as exc_info:
        wo_services._validate_schedule_window(start, end, due, Decimal("2.0"))
    assert exc_info.value.code == "due_not_after_end"


# --- DEF-004: Asset ModelSerializer Declarations (UT-SER-028 to UT-SER-039) ---


@pytest.mark.parametrize(
    "serializer_cls",
    [
        AssetCategorySerializer,
        AssetComponentSerializer,
        AssetDetailSerializer,
        AssetDocumentSerializer,
        AssetHierarchyNodeSerializer,
        AssetListSerializer,
        AssetMeterReadingSerializer,
        AssetMeterSerializer,
        AssetSerializer,
        AssetStatusHistorySerializer,
    ],
)
def test_asset_serializer_builds_fields_without_error(serializer_cls):
    """DEF-004 (UT-SER-028..039): All 10 asset serializers resolve fields against active models without ImproperlyConfigured."""
    serializer = serializer_cls()
    fields = serializer.fields
    assert len(fields) > 0
