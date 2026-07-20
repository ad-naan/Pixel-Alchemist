from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageSequence

try:
    from .layout import resolve_elements, resolve_obstacles
except ImportError:
    from layout import resolve_elements, resolve_obstacles


def variant_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("language") or "default")


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merged_element(template_name: str, role: str, template: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    raw = template.get("elements", {}).get(role, {})
    override = variant.get("layout_overrides", {}).get(template_name, {}).get(role, {})
    return {**raw, **override}


def merged_qa(template_name: str, template: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    return deep_merge(template.get("qa", {}), variant.get("qa_overrides", {}).get(template_name, {}))


def xyxy(box: list[int | float]) -> tuple[float, float, float, float]:
    x, y, width, height = (float(value) for value in box)
    return x, y, x + width, y + height


def find_box(metrics: dict[str, Any], role: str, key: str) -> list[int | float] | None:
    value = metrics.get(role, {}).get(key)
    if isinstance(value, list) and len(value) == 4:
        return value
    return None


def edge_value(box: list[int | float], edge: str) -> float:
    left, top, right, bottom = xyxy(box)
    values = {
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "center_x": (left + right) / 2,
        "center_y": (top + bottom) / 2,
    }
    if edge not in values:
        raise ValueError(f"unsupported alignment edge: {edge}")
    return values[edge]


def add_violation(
    violations: list[dict[str, Any]],
    *,
    variant: str,
    template: str,
    rule: str,
    roles: list[str],
    actual: Any,
    expected: Any,
    severity: str = "error",
) -> None:
    violations.append(
        {
            "variant": variant,
            "template": template,
            "rule": rule,
            "roles": roles,
            "actual": actual,
            "expected": expected,
            "severity": severity,
        }
    )


def required_box(
    metrics: dict[str, Any],
    role: str,
    key: str,
    violations: list[dict[str, Any]],
    context: dict[str, str],
    rule: str,
) -> list[int | float] | None:
    box = find_box(metrics, role, key)
    if box is None:
        add_violation(
            violations,
            **context,
            rule=f"{rule}.missing_metric",
            roles=[role],
            actual=None,
            expected=key,
        )
    return box


def validate_alignment(
    rules: list[Any], metrics: dict[str, Any], violations: list[dict[str, Any]], context: dict[str, str]
) -> None:
    for raw in rules:
        if not isinstance(raw, dict):
            continue
        roles = [str(role) for role in raw.get("roles", [])]
        if len(roles) < 2:
            continue
        key = str(raw.get("metric", "ink_box"))
        edge = str(raw.get("edge", "left"))
        tolerance = float(raw.get("tolerance", 0))
        boxes = [required_box(metrics, role, key, violations, context, "alignment") for role in roles]
        if any(box is None for box in boxes):
            continue
        values = [edge_value(box, edge) for box in boxes if box is not None]
        spread = max(values) - min(values)
        if spread > tolerance:
            add_violation(
                violations,
                **context,
                rule="alignment",
                roles=roles,
                actual={"edge": edge, "values": values, "spread": spread},
                expected={"tolerance": tolerance, "metric": key},
            )


def pair_roles(raw: Any) -> tuple[list[str], dict[str, Any]]:
    if isinstance(raw, dict):
        roles = raw.get("roles") or [raw.get("from"), raw.get("to")]
        return [str(role) for role in roles if role is not None], raw
    if isinstance(raw, list):
        return [str(role) for role in raw], {}
    return [], {}


def validate_spacing(
    rules: list[Any], metrics: dict[str, Any], violations: list[dict[str, Any]], context: dict[str, str]
) -> None:
    for raw in rules:
        roles, options = pair_roles(raw)
        if len(roles) != 2:
            continue
        key = str(options.get("metric", "ink_box"))
        first = required_box(metrics, roles[0], key, violations, context, "spacing")
        second = required_box(metrics, roles[1], key, violations, context, "spacing")
        if first is None or second is None:
            continue
        axis = str(options.get("axis", "y"))
        a_left, a_top, a_right, a_bottom = xyxy(first)
        b_left, b_top, b_right, b_bottom = xyxy(second)
        if axis == "y":
            gap = b_top - a_bottom
        elif axis == "x":
            gap = b_left - a_right
        else:
            raise ValueError(f"unsupported spacing axis: {axis}")
        minimum = float(options.get("min", options.get("min_gap", 0)))
        if gap < minimum:
            add_violation(
                violations,
                **context,
                rule="spacing",
                roles=roles,
                actual={"axis": axis, "gap": gap},
                expected={"min": minimum, "metric": key},
            )


def validate_non_overlap(
    rules: list[Any], metrics: dict[str, Any], violations: list[dict[str, Any]], context: dict[str, str]
) -> None:
    for raw in rules:
        roles, options = pair_roles(raw)
        if len(roles) != 2:
            continue
        key = str(options.get("metric", "ink_box"))
        first = required_box(metrics, roles[0], key, violations, context, "non_overlap")
        second = required_box(metrics, roles[1], key, violations, context, "non_overlap")
        if first is None or second is None:
            continue
        a_left, a_top, a_right, a_bottom = xyxy(first)
        b_left, b_top, b_right, b_bottom = xyxy(second)
        overlap_x = max(0.0, min(a_right, b_right) - max(a_left, b_left))
        overlap_y = max(0.0, min(a_bottom, b_bottom) - max(a_top, b_top))
        if overlap_x > 0 and overlap_y > 0:
            add_violation(
                violations,
                **context,
                rule="non_overlap",
                roles=roles,
                actual={"overlap": [overlap_x, overlap_y], "area": overlap_x * overlap_y},
                expected={"area": 0, "metric": key},
            )


def obstacle_rules(value: Any, metrics: dict[str, Any], template_name: str, template: dict[str, Any], variant: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    if value is True:
        specs = resolve_elements(template_name, template, variant)
        roles = [
            role
            for role, spec in specs.items()
            if role in metrics and str(spec.get("type", "text")) in {"text", "icon_text", "button"}
        ]
        return [{"roles": roles}]
    return []


def validate_obstacle_clearance(
    rules: Any,
    metrics: dict[str, Any],
    template_name: str,
    template: dict[str, Any],
    variant: dict[str, Any],
    violations: list[dict[str, Any]],
    context: dict[str, str],
) -> None:
    obstacles = resolve_obstacles(template_name, template, variant)
    for raw in obstacle_rules(rules, metrics, template_name, template, variant):
        roles = [str(role) for role in raw.get("roles", [])]
        names = [str(name) for name in raw.get("obstacles", obstacles.keys())]
        key = str(raw.get("metric", "ink_box"))
        rule_padding = float(raw.get("padding", 0))
        for role in roles:
            rendered = required_box(metrics, role, key, violations, context, "obstacle_clearance")
            if rendered is None:
                continue
            r_left, r_top, r_right, r_bottom = xyxy(rendered)
            for name in names:
                obstacle = obstacles.get(name)
                raw_box = obstacle.get("box") if isinstance(obstacle, dict) else obstacle
                if not (isinstance(raw_box, list) and len(raw_box) == 4):
                    add_violation(
                        violations,
                        **context,
                        rule="obstacle_clearance.missing_obstacle",
                        roles=[role, f"obstacle:{name}"],
                        actual=None,
                        expected="configured obstacle box",
                    )
                    continue
                padding = float(obstacle.get("padding", rule_padding)) if isinstance(obstacle, dict) else rule_padding
                o_left, o_top, o_right, o_bottom = xyxy(raw_box)
                o_left -= padding
                o_top -= padding
                o_right += padding
                o_bottom += padding
                overlap_x = max(0.0, min(r_right, o_right) - max(r_left, o_left))
                overlap_y = max(0.0, min(r_bottom, o_bottom) - max(r_top, o_top))
                if overlap_x > 0 and overlap_y > 0:
                    add_violation(
                        violations,
                        **context,
                        rule="obstacle_clearance",
                        roles=[role, f"obstacle:{name}"],
                        actual={"overlap": [overlap_x, overlap_y], "area": overlap_x * overlap_y, "metric_box": rendered},
                        expected={"area": 0, "obstacle_box": raw_box, "padding": padding, "metric": key},
                    )


def validate_typography(
    rules: dict[str, Any], metrics: dict[str, Any], violations: list[dict[str, Any]], context: dict[str, str]
) -> None:
    for role, limits in rules.items():
        if not isinstance(limits, dict):
            continue
        actual = metrics.get(role, {})
        checks = [
            ("min_font_size", "font_size", lambda value, limit: value >= limit),
            ("min_font_scale", "font_scale", lambda value, limit: value >= limit),
            ("max_height_density", "height_density", lambda value, limit: value <= limit),
            ("max_lines", "line_count", lambda value, limit: value <= limit),
        ]
        for rule_name, metric_name, predicate in checks:
            if rule_name not in limits:
                continue
            value = actual.get(metric_name)
            if value is None and metric_name == "line_count" and isinstance(actual.get("lines"), list):
                value = len(actual["lines"])
            if value is None and metric_name == "font_scale" and actual.get("font_size") is not None:
                maximum = actual.get("max_font_size")
                if maximum:
                    value = float(actual["font_size"]) / float(maximum)
            if value is None:
                add_violation(
                    violations,
                    **context,
                    rule=f"typography.{rule_name}.missing_metric",
                    roles=[role],
                    actual=None,
                    expected=metric_name,
                )
            elif not predicate(float(value), float(limits[rule_name])):
                add_violation(
                    violations,
                    **context,
                    rule=f"typography.{rule_name}",
                    roles=[role],
                    actual=value,
                    expected=limits[rule_name],
                )
        if limits.get("forbid_unnecessary_wrap"):
            line_count = actual.get("line_count")
            if line_count is None and isinstance(actual.get("lines"), list):
                line_count = len(actual["lines"])
            possible = actual.get("single_line_possible")
            if line_count is None or possible is None:
                add_violation(
                    violations,
                    **context,
                    rule="typography.forbid_unnecessary_wrap.missing_metric",
                    roles=[role],
                    actual={"line_count": line_count, "single_line_possible": possible},
                    expected="line_count and single_line_possible",
                )
            elif int(line_count) > 1 and bool(possible):
                add_violation(
                    violations,
                    **context,
                    rule="typography.unnecessary_wrap",
                    roles=[role],
                    actual={
                        "line_count": int(line_count),
                        "single_line_min_width": actual.get("single_line_min_width"),
                        "available_width": (actual.get("safe_box") or [None, None, None, None])[2],
                    },
                    expected="one line at or above the configured single-line minimum font size",
                )


def containment_rules(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def validate_containment(
    rules: list[Any],
    metrics: dict[str, Any],
    template_name: str,
    template: dict[str, Any],
    variant: dict[str, Any],
    violations: list[dict[str, Any]],
    context: dict[str, str],
) -> None:
    resolved_specs = resolve_elements(template_name, template, variant)
    for raw in rules:
        options = raw if isinstance(raw, dict) else {"role": raw}
        roles = options.get("roles") or [options.get("role")]
        key = str(options.get("metric", "ink_box"))
        tolerance = float(options.get("tolerance", 0))
        for role_value in roles:
            if role_value is None:
                continue
            role = str(role_value)
            ink = required_box(metrics, role, key, violations, context, "containment")
            safe = find_box(metrics, role, str(options.get("safe_metric", "safe_box")))
            if safe is None:
                configured = resolved_specs.get(role, {}).get("box")
                safe = configured if isinstance(configured, list) and len(configured) == 4 else None
            if ink is None:
                continue
            if safe is None:
                add_violation(
                    violations,
                    **context,
                    rule="containment.missing_safe_box",
                    roles=[role],
                    actual=None,
                    expected="safe_box or configured element box",
                )
                continue
            i_left, i_top, i_right, i_bottom = xyxy(ink)
            s_left, s_top, s_right, s_bottom = xyxy(safe)
            overflow = [
                max(0.0, s_left - i_left),
                max(0.0, s_top - i_top),
                max(0.0, i_right - s_right),
                max(0.0, i_bottom - s_bottom),
            ]
            if max(overflow) > tolerance:
                add_violation(
                    violations,
                    **context,
                    rule="containment",
                    roles=[role],
                    actual={"overflow": overflow, "ink_box": ink},
                    expected={"safe_box": safe, "tolerance": tolerance},
                )


def validate_qa(
    qa: dict[str, Any],
    metrics: dict[str, Any],
    template_name: str,
    template: dict[str, Any],
    variant: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
    context = {"variant": variant_id(variant), "template": template_name}
    validate_alignment(qa.get("alignment_groups", []), metrics, violations, context)
    validate_spacing(qa.get("spacing", []), metrics, violations, context)
    validate_non_overlap(qa.get("non_overlap", []), metrics, violations, context)
    validate_obstacle_clearance(
        qa.get("obstacle_clearance", []),
        metrics,
        template_name,
        template,
        variant,
        violations,
        context,
    )
    element_rules = qa.get("elements", qa.get("typography", {}))
    validate_typography(element_rules, metrics, violations, context)
    element_containment = [
        {"role": role, "tolerance": limits["containment_tolerance"]}
        for role, limits in element_rules.items()
        if isinstance(limits, dict) and "containment_tolerance" in limits
    ]
    configured_containment = qa.get("containment", [])
    automatic_containment = [{"role": role} for role in metrics] if configured_containment is True else []
    validate_containment(
        automatic_containment + containment_rules(configured_containment) + element_containment,
        metrics,
        template_name,
        template,
        variant,
        violations,
        context,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate output coverage, dimensions, animation metadata, and explicit layout QA rules.")
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--variants", nargs="*")
    parser.add_argument("--languages", nargs="*", help="Backward-compatible alias.")
    parser.add_argument("--report", type=Path, help="Render report path; defaults to OUTPUT_DIR/render-report.json.")
    parser.add_argument("--json-output", type=Path, help="Also write the validation result to this JSON file.")
    args = parser.parse_args()

    payload = json.loads(args.config.read_text(encoding="utf-8"))
    variants = payload.get("variants") or payload.get("locales") or [{"id": "default", "language": "default"}]
    requested = set(args.variants or args.languages or [variant_id(item) for item in variants])
    report_path = args.report or args.output_dir / "render-report.json"
    report_rows: list[dict[str, Any]] = []
    if report_path.exists():
        report_rows = json.loads(report_path.read_text(encoding="utf-8"))
    report_index = {(str(row.get("variant")), str(row.get("template"))): row for row in report_rows}
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    checked = 0
    for variant in variants:
        identifier = variant_id(variant)
        if identifier not in requested and str(variant.get("language", "default")) not in requested:
            continue
        for template_name, template in payload.get("templates", {}).items():
            output = args.output_dir / identifier / str(template["output"])
            if not output.exists():
                errors.append(f"missing: {output}")
                continue
            with Image.open(output) as image:
                if image.size != tuple(template["canvas"]):
                    errors.append(f"size: {output}: {image.size} != {tuple(template['canvas'])}")
                if output.suffix.lower() == ".gif" and template.get("animation"):
                    expected = template["animation"]
                    if getattr(image, "n_frames", 1) != int(expected.get("frames", image.n_frames)):
                        errors.append(f"frames: {output}: {image.n_frames}")
                    if image.info.get("loop", 0) != int(expected.get("loop", image.info.get("loop", 0))):
                        errors.append(f"loop: {output}: {image.info.get('loop')}")
                    durations = [int(frame.info.get("duration", image.info.get("duration", 100))) for frame in ImageSequence.Iterator(image)]
                    if expected.get("durations_ms") and durations != [int(value) for value in expected["durations_ms"]]:
                        errors.append(f"durations: {output}: {durations}")
            qa = merged_qa(template_name, template, variant)
            if qa:
                row = report_index.get((identifier, template_name))
                if row is None or not isinstance(row.get("metrics"), dict):
                    add_violation(
                        violations,
                        variant=identifier,
                        template=template_name,
                        rule="missing_render_metrics",
                        roles=[],
                        actual=None,
                        expected=str(report_path),
                    )
                else:
                    validate_qa(qa, row["metrics"], template_name, template, variant, violations)
            checked += 1

    errors.extend(
        f"{item['variant']}:{item['template']}:{item['rule']}:{','.join(item['roles'])}"
        for item in violations
        if item.get("severity", "error") == "error"
    )
    result = {"checked": checked, "errors": errors, "violations": violations}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
