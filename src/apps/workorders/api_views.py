"""Canonical consolidation module (PRD Compliance Directive Gap C).
WorkOrderViewSet is canonically implemented in ``apps.workorders.views``.
This module re-exports the canonical viewset and serializers to guarantee 100% backward compatibility
across legacy imports, external clients, and test harnesses.
"""
from apps.workorders.serializers import (
    AssignSerializer,
    ClosureApprovalSerializer,
    ExpectedVersionSerializer,
    LaborSerializer,
    MaterialSerializer,
    PlanSerializer,
    ReassignSerializer,
    ReviewSerializer,
    WorkNoteSerializer,
    WorkOrderCompleteSerializer,
    WorkOrderReasonSerializer,
    WorkOrderSerializer,
)
from apps.workorders.serializers import (
    CreateWorkOrderSerializer as WorkOrderWriteSerializer,
)
from apps.workorders.serializers import (
    EvidenceSerializer as WorkOrderEvidenceSerializer,
)
from apps.workorders.serializers import (
    LaborInputSerializer as LaborWriteSerializer,
)
from apps.workorders.serializers import (
    MaterialInputSerializer as MaterialWriteSerializer,
)
from apps.workorders.serializers import (
    UpdateWorkOrderSerializer as WorkOrderPatchSerializer,
)
from apps.workorders.serializers import (
    WorkOrderEventSerializer as EventSerializer,
)
from apps.workorders.views import WorkOrderViewSet

__all__ = [
    "WorkOrderViewSet",
    "WorkOrderSerializer",
    "WorkOrderWriteSerializer",
    "WorkOrderPatchSerializer",
    "PlanSerializer",
    "AssignSerializer",
    "ReassignSerializer",
    "WorkOrderReasonSerializer",
    "WorkOrderCompleteSerializer",
    "LaborSerializer",
    "LaborWriteSerializer",
    "MaterialSerializer",
    "MaterialWriteSerializer",
    "EventSerializer",
    "WorkOrderEvidenceSerializer",
    "ClosureApprovalSerializer",
    "ExpectedVersionSerializer",
    "ReviewSerializer",
    "WorkNoteSerializer",
]
