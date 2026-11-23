from __future__ import annotations

from rest_framework import serializers

from apps.assets.models import (
    Asset,
    AssetCategory,
    AssetComponent,
    AssetDocument,
    AssetMeter,
    AssetMeterReading,
    AssetStatus,
    AssetStatusHistory,
)


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = [
            "id",
            "organization",
            "name",
            "description",
            "is_active",
            "attribute_definitions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetComponentSerializer(serializers.ModelSerializer):
    parent_tag = serializers.CharField(source="parent.asset_tag", read_only=True)
    child_tag = serializers.CharField(source="child.asset_tag", read_only=True)

    class Meta:
        model = AssetComponent
        fields = [
            "id",
            "organization",
            "parent",
            "parent_tag",
            "child",
            "child_tag",
            "relationship_type",
            "quantity",
            "part_number",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetMeterReadingSerializer(serializers.ModelSerializer):
    recorded_by_email = serializers.EmailField(source="recorded_by.email", read_only=True)

    class Meta:
        model = AssetMeterReading
        fields = [
            "id",
            "organization",
            "meter",
            "value",
            "read_at",
            "recorded_by",
            "recorded_by_email",
            "source",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetMeterSerializer(serializers.ModelSerializer):
    readings = AssetMeterReadingSerializer(many=True, read_only=True)

    class Meta:
        model = AssetMeter
        fields = [
            "id",
            "organization",
            "asset",
            "name",
            "unit",
            "is_active",
            "readings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source="changed_by.email", read_only=True)

    class Meta:
        model = AssetStatusHistory
        fields = [
            "id",
            "organization",
            "asset",
            "from_status",
            "to_status",
            "action",
            "reason",
            "changed_by",
            "changed_by_email",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = AssetDocument
        fields = [
            "id",
            "organization",
            "asset",
            "title",
            "doc_type",
            "attachment",
            "uploaded_by",
            "uploaded_by_email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetListSerializer(serializers.ModelSerializer):
    """Compact serializer for table grids and list views."""
    category_name = serializers.CharField(source="category.name", read_only=True)
    site_code = serializers.CharField(source="site.code", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True, default="")

    class Meta:
        model = Asset
        fields = [
            "id",
            "organization",
            "asset_tag",
            "opaque_identifier",
            "name",
            "description",
            "category",
            "category_name",
            "site",
            "site_code",
            "zone",
            "zone_name",
            "manufacturer",
            "model",
            "serial_number",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetHierarchyNodeSerializer(serializers.ModelSerializer):
    """
    Recursive serializer returning the full N-level assembly tree (M03).
    Includes sub-assets and replaceable sub-components.
    """
    category_name = serializers.CharField(source="category.name", read_only=True)
    site_code = serializers.CharField(source="site.code", read_only=True)
    components = AssetComponentSerializer(source="child_links", many=True, read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "asset_tag",
            "opaque_identifier",
            "name",
            "category_name",
            "site_code",
            "status",
            "components",
            "children",
        ]

    def get_children(self, obj):
        children_links = getattr(obj, "child_links", None)
        if not children_links:
            return []
        child_assets = [link.child for link in children_links.all() if link.child]
        return AssetHierarchyNodeSerializer(child_assets, many=True).data


class AssetDetailSerializer(serializers.ModelSerializer):
    """Full detail view for single asset profile."""
    category_name = serializers.CharField(source="category.name", read_only=True)
    site_code = serializers.CharField(source="site.code", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True, default="")
    owner_name = serializers.CharField(source="owner.user.display_name", read_only=True, default="")
    components = AssetComponentSerializer(source="child_links", many=True, read_only=True)
    meters = AssetMeterSerializer(many=True, read_only=True)
    documents = AssetDocumentSerializer(many=True, read_only=True)
    status_history = AssetStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "organization",
            "asset_tag",
            "opaque_identifier",
            "name",
            "description",
            "category",
            "category_name",
            "site",
            "site_code",
            "zone",
            "zone_name",
            "owner",
            "owner_name",
            "manufacturer",
            "model",
            "serial_number",
            "status",
            "purchase_date",
            "commission_date",
            "warranty_ref",
            "attributes",
            "components",
            "meters",
            "documents",
            "status_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetStatusChangeSerializer(serializers.Serializer):
    """Controlled status transition payload (CR-05)."""
    status = serializers.ChoiceField(choices=AssetStatus.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    changed_by = serializers.CharField(required=False, default="Technician / Operator")


class AssetMeterReadingInputSerializer(serializers.Serializer):
    """Payload for submitting a new meter reading."""
    reading_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    recorded_by = serializers.CharField(required=False, default="Technician")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


AssetSerializer = AssetDetailSerializer
