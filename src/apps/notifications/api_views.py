from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.exceptions import NotFound, ValidationFailed
from apps.tenancy.api import TenantAPIMixin

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "level", "title", "body", "link", "source", "read_at", "created_at"]


class NotificationViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    """The caller's own notifications in the active organization."""

    serializer_class = NotificationSerializer
    permission_map = {"list": "__member__", "retrieve": "__member__", "read": "__member__", "read_all": "__member__"}
    filterset_fields: list = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.for_organization(self.request.organization).filter(recipient=self.request.user)

    def _assert_not_readonly_audit(self, request):
        membership = getattr(request, "membership", None)
        if not membership:
            return
        roles = []
        if hasattr(membership, "roles"):
            roles = list(membership.roles.all())
        if not roles and hasattr(membership, "membership_roles"):
            roles = [mr.role for mr in membership.membership_roles.select_related("role").all()]
        if not roles:
            return
        audit_keys = {"auditor", "compliance", "compliance_officer", "audit"}
        is_all_audit = all(
            ((getattr(r, "system_key", "") or "").lower() in audit_keys) or
            ("audit" in (getattr(r, "name", "") or "").lower()) or
            ("compliance" in (getattr(r, "name", "") or "").lower())
            for r in roles
        )
        if is_all_audit:
            raise PermissionDenied("Read-only audit roles cannot perform state-changing operations.")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        self._assert_not_readonly_audit(request)
        try:
            n = self.get_queryset().get(pk=pk)
        except (Notification.DoesNotExist, ValueError, Exception) as exc:
            raise NotFound("Notification not found.") from exc
        n.mark_read()
        return Response(NotificationSerializer(n).data)

    @extend_schema(request=None, responses={200: inline_serializer("NotificationReadAllResponse", fields={"marked": serializers.IntegerField()})})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self._assert_not_readonly_audit(request)
        if isinstance(request.data, list):
            raise ValidationFailed("Request body must be a JSON object.", code="validation_failed")
        n = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked": n}, status=status.HTTP_200_OK)
