"""Custom drf-spectacular OpenAPI schema generation and post-processing hooks."""
from __future__ import annotations

import uritemplate
from drf_spectacular.openapi import AutoSchema

_UNPAGINATED_LIST_ACTIONS = {
    ("SiteViewSet", "tree"),
    ("WorkOrderViewSet", "events"),
    ("ChecklistTemplateViewSet", "reorder"),
    ("StockBalanceViewSet", "transfer"),
    ("ServiceRequestViewSet", "comments"),
}


class FieldOpsAutoSchema(AutoSchema):
    """Aligns generated OpenAPI schemas with actual FieldOps API behavior."""

    def _is_list_view(self, serializer=None):
        if self.view.__class__.__name__ == "CoverageViewSet" and getattr(self.view, "action", None) == "list":
            return False
        return super()._is_list_view(serializer)

    def _get_paginator(self):
        if self.method != "GET":
            return None
        if (self.view.__class__.__name__, getattr(self.view, "action", None)) in _UNPAGINATED_LIST_ACTIONS:
            return None
        return super()._get_paginator()

    def _get_parameters(self):
        path_vars = set(uritemplate.variables(self.path))
        return [
            param
            for param in super()._get_parameters()
            if not (param.get("in") == "path" and param.get("name") not in path_vars)
        ]


def strip_unused_path_parameters(result, generator, request, public):
    """Remove documented `in: path` parameters whose name is absent from the URL path template."""
    paths = result.get("paths") or {}
    http_methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_vars = set(uritemplate.variables(path))
        if "parameters" in path_item:
            filtered = [
                p
                for p in path_item["parameters"]
                if not (p.get("in") == "path" and p.get("name") not in path_vars)
            ]
            if filtered:
                path_item["parameters"] = filtered
            else:
                path_item.pop("parameters", None)
        for method in http_methods:
            op = path_item.get(method)
            if isinstance(op, dict) and "parameters" in op:
                filtered = [
                    p
                    for p in op["parameters"]
                    if not (p.get("in") == "path" and p.get("name") not in path_vars)
                ]
                if filtered:
                    op["parameters"] = filtered
                else:
                    op.pop("parameters", None)
    result["paths"] = {p: item for p, item in paths.items() if "//" not in p}
    return result


def filter_api_v1_endpoints(endpoints):
    """Filter OpenAPI schema endpoints to strictly include only /api/v1 routes."""
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if (path.startswith("/api/v1") or path.startswith("^/api/v1")) and "//" not in path
    ]


