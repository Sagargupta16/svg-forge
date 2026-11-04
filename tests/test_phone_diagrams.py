"""Phone layouts of flow, timeline, logos, calendar and ring: 320 px wide, text at 10.5 px or
more, contrast on both pages and per half of a pair, text inside the card, a finished static
frame, the same bytes every time, and a different file from the desktop one."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from xml.dom import minidom

import pytest
from test_integration import overflow

import forge
import poster
import validate_svg

DATA = Path(__file__).resolve().parent.parent / "examples" / "data"
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]
FLOW_TEXT = "push -> build -> unit, e2e -> deploy"
FLOW_RETURN = FLOW_TEXT + "; deploy -[rollback]-> build"
LONG_RINGS = [
    {"label": "Integration test coverage", "value": 81},
    {"label": "Open blocking issues closed", "value": 14, "max": 19, "tone": "warn"},
    {"label": "Docs", "value": 9, "max": 10, "tone": "ok"},
]
STACK = ["Python", "TypeScript", "GitHub Actions", "Kubernetes", "Terraform", "PostgreSQL"]
STACK += ["Redis", "DigitalOcean", "Cloudflare Workers", "Docker", "Vite", "React", "Rust", "Go"]


def example(name: str) -> object:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def hostile(kind: str, s: str) -> dict[str, object]:
    return {
        "flow": {
            "title": s,
            "nodes": [s, {"id": "b", "label": s}, "c"],
            "edges": [[s, "b", s], ["b", "c"], ["c", s, s]],  # the last one is a return arc
        },
        "timeline": {
            "title": s,
            "items": [
                {"start": "2020", "title": s, "subtitle": s},
                {"start": s, "end": s, "title": s, "subtitle": s, "current": True},
            ],
        },
        "logos": {"title": s, "items": [{"label": s}, {"label": s, "color": "#f472b6"}, "ok"]},
        "calendar": {"title": s, "start": "2026-01-01", "counts": [1, 0, 3]},
        "ring": {"title": s, "items": [{"label": s, "value": 3, "max": 4}, {"label": s}]},
    }[kind]


CASES: dict[str, tuple[str, dict[str, object]]] = {
    "flow": ("flow", {}),
    "flow-text": ("flow", {"data": FLOW_TEXT}),
    "flow-return": ("flow", {"data": FLOW_RETURN, "timing": "long"}),
    "flow-once": ("flow", {"data": example("pipeline.json"), "loop": False}),
    "flow-architecture": ("flow", {"data": example("architecture.json"), "accent": "#f472b6"}),
    "flow-columns": ("flow", {"data": "build -[ok]-> deploy"}),
    "timeline": ("timeline", {}),
    "timeline-career": ("timeline", {"data": example("career.json"), "timing": "short"}),
    "logos": ("logos", {}),
    "logos-capped": ("logos", {"data": {"title": "Stack", "items": STACK}}),
    "logos-marquee": ("logos", {"timing": "ambient"}),
    "calendar": ("calendar", {}),
    "calendar-accent": ("calendar", {"variant": "accent", "timing": "medium"}),
    "ring": ("ring", {}),
    "ring-goals": ("ring", {"data": example("goals.json")}),
    "ring-list": ("ring", {"data": {"title": "Release readiness", "items": LONG_RINGS}}),
}
CASES |= {
    f"{kind}-hostile-{i}": (kind, {"title": s, "data": hostile(kind, s)})
    for kind in ("flow", "timeline", "logos", "calendar", "ring")
    for i, s in enumerate(HOSTILE)
}
IDS = list(CASES)


def phone(case: str, **extra: object) -> str:
    kind, options = CASES[case]
    return forge.render(kind, device="phone", **options, **extra)


def check(svg: str, theme: str) -> None:
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings


def font_sizes(svg: str) -> list[float]:
    found = re.findall(r'font-size="([\d.]+)"', svg) + re.findall(r"font-size:\s*([\d.]+)px", svg)
    return [float(v) for v in found]


def root_of(svg: str) -> minidom.Element:
    return minidom.parseString(svg).documentElement


@pytest.mark.parametrize("kind", ["flow", "timeline", "logos", "calendar", "ring"])
def test_kind_has_a_phone_layout(kind: str) -> None:
    assert forge.KINDS[kind].phone


@pytest.mark.parametrize("case", IDS)
def test_phone_card_is_320_wide_with_phone_text(case: str) -> None:
    svg = phone(case)

    root = root_of(svg)
    assert root.getAttribute("width") == "320"
    assert root.getAttribute("viewBox").split()[2] == "320"
    sizes = font_sizes(svg)
    assert sizes
    assert min(sizes) >= forge.PHONE_TEXT


@pytest.mark.parametrize("case", IDS)
def test_phone_card_reads_on_both_pages(case: str) -> None:
    check(phone(case), "both")


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("case", IDS)
def test_phone_pair_reads_on_its_page(case: str, theme: str) -> None:
    kind, options = CASES[case]
    svg, _ = forge.build(kind, theme=theme, pair=True, device="phone", **options)

    check(svg, theme)
    assert min(font_sizes(svg)) >= forge.PHONE_TEXT


@pytest.mark.parametrize("case", IDS)
def test_phone_text_stays_inside_and_the_static_frame_is_finished(case: str) -> None:
    svg = phone(case)

    assert overflow(svg) == []
    assert poster.problems(svg) == []


@pytest.mark.parametrize("case", IDS)
def test_phone_render_is_stable_and_not_the_desktop_file(case: str) -> None:
    kind, options = CASES[case]
    svg = phone(case)

    assert svg == phone(case)
    assert svg != forge.render(kind, **options)


@pytest.mark.parametrize("kind", ["flow", "timeline", "logos", "calendar", "ring"])
@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_text_is_escaped_on_a_phone(kind: str, text: str) -> None:
    svg = forge.render(kind, device="phone", title=text, data=hostile(kind, text))

    assert "<script" not in svg
    assert "&lt;" in svg
    if "&" in text:
        assert "&amp;" in svg


def node_boxes(svg: str) -> list[tuple[float, float]]:
    """(x, y) of each flow node: the 30 px tall rects outside <defs>."""
    root = root_of(svg)
    return sorted(
        {
            (float(r.getAttribute("x")), float(r.getAttribute("y")))
            for r in root.getElementsByTagName("rect")
            if r.getAttribute("height") == "30"
        }
    )


def test_flow_keeps_its_columns_when_the_labels_fit() -> None:
    boxes = node_boxes(phone("flow-columns"))

    assert len(boxes) == 2
    assert boxes[0][1] == boxes[1][1]  # side by side, as on the desktop


def test_flow_stacks_one_rank_per_row_when_the_columns_are_too_narrow() -> None:
    svg = phone("flow-text")  # four ranks: push, build, unit and e2e, deploy

    boxes = node_boxes(svg)
    assert len({y for _, y in boxes}) == 4
    assert all(0 < x < forge.PHONE_W for x, _ in boxes)
    for label in ("PUSH", "BUILD", "UNIT", "E2E", "DEPLOY"):
        assert f">{label}</text>" in svg  # whole, not cut


def test_flow_return_arc_runs_down_the_right_side() -> None:
    svg = phone("flow-return")

    arcs = re.findall(
        r'<path d="M([\d.]+) ([\d.]+) C([\d.]+) [^"]*"[^>]*stroke-dasharray="4 4"', svg
    )
    assert len(arcs) == 1
    start_x, _, bend_x = (float(v) for v in arcs[0])
    assert bend_x > start_x
    assert bend_x == forge.PHONE_W - 10
    assert ">ROLLBACK</text>" in svg


def test_timeline_phone_is_vertical_even_when_horizontal_is_asked() -> None:
    svg = phone("timeline", variant="horizontal")

    rail = re.search(r'<path d="M([\d.]+) ([\d.]+) V([\d.]+)"', svg)
    assert rail is not None
    assert float(rail.group(3)) > float(rail.group(2))


def test_timeline_phone_wraps_a_long_title_instead_of_cutting_it() -> None:
    title = "Principal engineer for the developer platform team"
    svg = forge.render("timeline", device="phone", data=[{"start": "2024", "title": title}])

    lines = re.findall(r'class="[\w-]+-s"[^>]*>([^<]*)</text>', svg)
    assert len(lines) == 2
    assert " ".join(lines) == title
    assert forge.ELLIPSIS not in svg


def test_logos_phone_caps_a_long_wall_with_a_more_pill() -> None:
    svg = phone("logos-capped")

    shown = [label.upper() for label in STACK if f">{label.upper()}</text>" in svg]
    assert f">+{len(STACK) - len(shown)} MORE</text>" in svg
    assert shown == [label.upper() for label in STACK[: len(shown)]]
    pills = [r for r in root_of(svg).getElementsByTagName("rect") if r.getAttribute("rx") == "19.5"]
    assert len(pills) == len(shown) + 1
    assert {round(float(p.getAttribute("width"))) for p in pills} == {140, 291}  # half and full


def test_calendar_phone_shows_the_last_26_weeks() -> None:
    svg = phone("calendar")

    desc = root_of(svg).getElementsByTagName("desc")[0].firstChild.data
    first, last = (date.fromisoformat(d) for d in re.findall(r"\d{4}-\d{2}-\d{2}", desc)[:2])
    assert 25 * 7 < (last - first).days + 1 <= 26 * 7
    assert first.weekday() == 6  # weeks start on Sunday


def ring_centers(svg: str) -> list[tuple[float, float]]:
    root = root_of(svg)
    return [
        (float(c.getAttribute("cx")), float(c.getAttribute("cy")))
        for c in root.getElementsByTagName("circle")
        if c.getAttribute("opacity") == "0.6"
    ]


def test_ring_phone_puts_three_in_a_row_when_their_labels_fit() -> None:
    centers = ring_centers(phone("ring"))

    assert len(centers) == 3
    assert len({cy for _, cy in centers}) == 1


def test_ring_phone_lists_one_per_row_when_labels_are_long() -> None:
    svg = phone("ring-list")

    centers = ring_centers(svg)
    assert len({cx for cx, _ in centers}) == 1
    assert len({cy for _, cy in centers}) == 3
    assert "OPEN BLOCKING ISSUES CLOSED" in svg


@pytest.mark.parametrize(
    ("kind", "data"),
    [("flow", FLOW_TEXT), ("timeline", None), ("ring", {"items": LONG_RINGS})],
)
def test_phone_height_too_short_for_the_text_is_refused(kind: str, data: object) -> None:
    with pytest.raises(forge.ForgeError, match="height of at least"):
        forge.render(kind, device="phone", height=60, data=data)


def test_logos_phone_height_holds_fewer_rows() -> None:
    svg = forge.render("logos", device="phone", height=120, data={"items": STACK})

    assert root_of(svg).getAttribute("height") == "120"
    assert re.search(r">\+\d+ MORE</text>", svg)
    assert overflow(svg) == []
