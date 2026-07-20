from __future__ import annotations

from typing import Any


def merged_spec(template_name: str, role: str, spec: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    template_overrides = variant.get("layout_overrides", {}).get(template_name, {})
    return {**spec, **template_overrides.get(role, {})}


def resolve_obstacles(template_name: str, template: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    """Resolve fixed visual regions, including per-variant geometry overrides."""
    obstacles = {
        str(name): dict(value) if isinstance(value, dict) else value
        for name, value in template.get("obstacles", {}).items()
    }
    overrides = variant.get("obstacle_overrides", {}).get(template_name, {})
    for name, override in overrides.items():
        if override is None:
            obstacles.pop(str(name), None)
        elif isinstance(override, dict) and isinstance(obstacles.get(str(name)), dict):
            obstacles[str(name)] = {**obstacles[str(name)], **override}
        else:
            obstacles[str(name)] = override
    return obstacles


def resolve_elements(
    template_name: str,
    template: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    elements = {
        role: merged_spec(template_name, role, spec, variant)
        for role, spec in template.get("elements", {}).items()
    }
    groups = {
        name: dict(spec)
        for name, spec in template.get("alignment_groups", {}).items()
    }
    for name, override in variant.get("alignment_overrides", {}).get(template_name, {}).items():
        if name not in groups:
            raise ValueError(f"{template_name}: alignment override references unknown group {name!r}")
        groups[name] = {**groups[name], **override}

    source_boxes = {
        role: list(spec["box"])
        for role, spec in elements.items()
        if "box" in spec
    }
    constrained_roles: set[str] = set()
    for name, group in groups.items():
        if not bool(group.get("enabled", True)):
            continue
        members = list(group.get("members", []))
        if not members:
            raise ValueError(f"{template_name}.{name}: alignment group has no members")
        edge = str(group.get("edge", "left"))
        if edge not in {"left", "center", "right"}:
            raise ValueError(f"{template_name}.{name}: unsupported alignment edge {edge!r}")
        physical_align = group.get("physical_align")
        if physical_align is not None and str(physical_align) not in {"left", "center", "right"}:
            raise ValueError(f"{template_name}.{name}: unsupported physical alignment {physical_align!r}")
        has_position = "position" in group
        has_anchor = "anchor_role" in group
        if has_position == has_anchor:
            raise ValueError(f"{template_name}.{name}: set exactly one of position or anchor_role")
        if has_anchor:
            anchor_role = str(group["anchor_role"])
            if anchor_role not in source_boxes:
                raise ValueError(f"{template_name}.{name}: anchor role {anchor_role!r} has no box")
            anchor_x, _, anchor_width, _ = source_boxes[anchor_role]
            if edge == "right":
                position = float(anchor_x) + float(anchor_width)
            elif edge == "center":
                position = float(anchor_x) + float(anchor_width) / 2
            else:
                position = float(anchor_x)
        else:
            position = float(group["position"])

        for role in members:
            if role not in elements:
                raise ValueError(f"{template_name}.{name}: unknown alignment member {role!r}")
            if role not in source_boxes:
                raise ValueError(f"{template_name}.{name}: member {role!r} has no box")
            if role in constrained_roles:
                raise ValueError(f"{template_name}: role {role!r} belongs to multiple alignment groups")
            constrained_roles.add(role)
            _, y, width, height = source_boxes[role]
            if edge == "right":
                x = position - float(width)
            elif edge == "center":
                x = position - float(width) / 2
            else:
                x = position
            resolved_x: int | float = int(x) if x.is_integer() else x
            resolved_spec = {**elements[role], "box": [resolved_x, y, width, height]}
            if physical_align is not None and resolved_spec.get("type") in {"text", "icon_text"}:
                resolved_spec["physical_align"] = str(physical_align)
            elements[role] = resolved_spec
    return elements
