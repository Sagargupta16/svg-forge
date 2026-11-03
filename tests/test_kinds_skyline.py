"""forge.py skyline: the contribution year as an isometric line figure of rounded blocks."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from xml.dom import minidom

import pytest

import check as repo_check
import forge
import poster
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"
CONTRIBUTIONS = json.loads((DATA / "contributions.json").read_text(encoding="utf-8"))
ACTIVITY = json.loads((DATA / "activity.json").read_text(encoding="utf-8"))
MIDWEEK = {"start": "2025-10-05", "counts": forge.sample_counts(369)}  # ends on a Thursday
RENDERS: list[dict[str, object]] = [
    {},
    {"theme": "light"},
    {"variant": "accent", "accent": "#a78bfa"},
    {"timing": "medium"},
    {"timing": "long", "theme": "light"},
    {"device": "phone"},
    {"device": "phone", "theme": "light", "title": "Contributions"},
    {"data": CONTRIBUTIONS},
    {"data": ACTIVITY, "timing": "medium", "variant": "accent"},
    {"data": CONTRIBUTIONS, "device": "phone", "loop": True},
]


def ids(opts: dict[str, object]) -> str:
    return ",".join(f"{k}={'json' if k == 'data' else v}" for k, v in opts.items()) or "sample"


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the given GitHub page(s); parses."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def overflow(svg: str) -> list[str]:
    """Text whose estimated box leaves the viewBox: tests/test_integration.py's check."""
    from test_integration import overflow as outside

    return outside(svg)


def days_of(svg: str) -> list[tuple[str, float, float]]:
    """(symbol, x, y) of every day in paint order: k0 to k4 by level, kp the busiest."""
    out = []
    for node in minidom.parseString(svg).getElementsByTagName("use"):
        name = node.getAttribute("href").rsplit("-", 1)[-1]
        if name != "skirt":
            out.append((name, float(node.getAttribute("x")), float(node.getAttribute("y"))))
    return out


def world(days: list[tuple[str, float, float]], weeks: int) -> list[tuple[int, int, int]]:
    """Each day's (x + y, row, col) in world space, recovered from where it sits on screen.

    The 2:1 view puts a day at world (x, y) = (row, weeks - 1 - col) pitches on screen at
    ((x - y) cos 45, (x + y) sin 45 k), so a step in x - y moves 1 / k times as far across as a
    step in x + y moves down. The first week is always whole, so x - y starts at 1 - weeks
    (its Sunday) and x + y runs from 0 (the last Sunday) to weeks + 5 (the first Saturday).
    """
    xs, ys = [x for _, x, _ in days], [y for *_, y in days]
    uy = (max(ys) - min(ys)) / (weeks + 5)
    ux = uy / forge.ISO_K
    out = []
    for _, sx, sy in days:
        u = round((sx - min(xs)) / ux) - (weeks - 1)
        v = round((sy - min(ys)) / uy)
        x, y = (u + v) // 2, (v - u) // 2
        out.append((x + y, x, weeks - 1 - y))
    return out


def window(data: dict[str, object], weeks: int) -> list[float]:
    """The counts a skyline of `weeks` weeks shows, Sunday first."""
    days = forge.calendar_days(data)
    last = max(days)
    first = last - timedelta(days=(last.weekday() + 1) % 7 + (weeks - 1) * 7)
    return [days.get(first + timedelta(days=k), 0.0) for k in range((last - first).days + 1)]


@pytest.mark.parametrize("opts", RENDERS, ids=ids)
def test_renders_valid_on_both_pages(opts: dict[str, object]) -> None:
    svg = forge.render("skyline", **opts)

    report = check(svg)
    assert report.stats["animated_elements"] <= 40
    assert len(svg.encode("utf-8")) < 50 * 1024
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert svg == forge.render("skyline", **opts)
    assert svg.endswith("</svg>\n") and "\r" not in svg


@pytest.mark.parametrize("timing", list(forge.PRESETS))
@pytest.mark.parametrize("loop", [None, True, False])
def test_every_preset_keeps_the_finished_city_in_the_static_frame(
    timing: str, loop: bool | None
) -> None:
    svg = forge.render("skyline", timing=timing, loop=loop, data=CONTRIBUTIONS)

    report = check(svg)
    assert poster.problems(svg) == []
    assert report.stats["animated_elements"] <= 40
    loops = forge.PRESETS[timing].loop if loop is None else loop
    assert ('repeatCount="indefinite"' in svg) is loops


@pytest.mark.parametrize("device", ["desktop", "phone"])
@pytest.mark.parametrize(
    "data", [None, CONTRIBUTIONS, ACTIVITY, MIDWEEK], ids=["sample", "days", "counts", "midweek"]
)
def test_blocks_paint_back_to_front(device: str, data: object) -> None:
    svg = forge.render("skyline", device=device, data=data)

    weeks = 26 if device == "phone" else 53
    days = world(days_of(svg), weeks)
    depth = [d for d, _, _ in days]
    assert depth == sorted(depth)
    assert len({(row, col) for _, row, col in days}) == len(days)
    assert all(0 <= row < 7 and 0 <= col < weeks for _, row, col in days)


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("data", [CONTRIBUTIONS, ACTIVITY, MIDWEEK], ids=["days", "counts", "mid"])
@pytest.mark.parametrize("device", ["desktop", "phone"])
def test_one_bright_day_and_it_is_the_busiest(theme: str, data: object, device: str) -> None:
    svg = forge.render("skyline", theme=theme, data=data, device=device, timing="medium")

    weeks = 26 if device == "phone" else 53
    days = days_of(svg)
    counts = window(data, weeks)
    col, row = divmod(counts.index(max(counts)), 7)
    lit = [
        (spot, x, y)
        for (name, x, y), spot in zip(days, world(days, weeks), strict=True)
        if name == "kp"
    ]
    assert [(r, c) for (_, r, c), _, _ in lit] == [(row, col)]
    th = forge.THEMES[theme]
    hi = forge.tune(th.ink, marks=forge.mark_grounds(th))
    head, body = svg.split("</defs>", 1)
    assert f'stroke="{hi}"' not in head
    spot = r'transform="translate\(([-\d.]+) ([-\d.]+)\)"'
    edges = re.findall(rf'<path[^>]*{spot}[^>]*stroke="{hi}"', body)
    assert [(float(x), float(y)) for x, y in edges] == [(lit[0][1], lit[0][2])]


def test_no_contributions_light_nothing() -> None:
    svg = forge.render(
        "skyline", timing="medium", data={"start": "2026-01-01", "counts": [0, 0, 0]}
    )

    check(svg)
    assert {name for name, *_ in days_of(svg)} == {"k0"}
    assert "stroke-opacity" not in svg


def test_outlines_hidden_from_the_validator_still_meet_their_contrast() -> None:
    """validate_svg does not follow <use>, so the plates and outlines in <defs> are checked
    here: plates are the card color, outlines reach 3:1 on it or stay under half opacity."""
    for opts in ({}, {"theme": "light"}, {"variant": "accent"}, {"theme": "nord"}):
        svg = forge.render("skyline", **opts)
        doc = minidom.parseString(svg)
        card = next(
            r.getAttribute("fill")
            for r in doc.getElementsByTagName("rect")
            if r.hasAttribute("fill")
        )
        bg = validate_svg.parse_color(card)
        defs = doc.getElementsByTagName("defs")[0]
        nodes = [defs, *defs.getElementsByTagName("*")]
        fills = {
            n.getAttribute("fill") for n in nodes if n.getAttribute("fill") not in ("", "none")
        }
        assert fills == {card}
        strokes = {n.getAttribute("stroke") for n in nodes if n.getAttribute("stroke")}
        assert len(strokes) >= 5
        for stroke in strokes:
            color = validate_svg.parse_color(stroke)
            if color[3] >= validate_svg.DECORATIVE_ALPHA:
                shown = validate_svg.over(color, bg)
                assert validate_svg.contrast_ratio(shown, bg) >= 3, (opts, stroke)


def test_phone_layout_is_320_wide_with_larger_text_and_half_the_weeks() -> None:
    desktop = forge.render("skyline", data=CONTRIBUTIONS)
    phone = forge.render("skyline", data=CONTRIBUTIONS, device="phone", title="My year")

    root = minidom.parseString(phone).documentElement
    assert root.getAttribute("width") == "320"
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', phone)]
    assert sizes and min(sizes) >= forge.PHONE_TEXT
    assert len(days_of(phone)) <= 26 * 7 < len(days_of(desktop))
    assert overflow(phone) == []
    check(phone)


def test_phone_shows_the_last_26_weeks_at_the_years_levels() -> None:
    desktop = days_of(forge.render("skyline", data=ACTIVITY))
    phone = days_of(forge.render("skyline", data=ACTIVITY, device="phone"))

    wide = {(r, c): n for (n, *_), (_, r, c) in zip(desktop, world(desktop, 53), strict=True)}
    narrow = {(r, c): n for (n, *_), (_, r, c) in zip(phone, world(phone, 26), strict=True)}
    assert len(narrow) == len(window(ACTIVITY, 26))
    pairs = [(n, wide[(r, c + 27)]) for (r, c), n in narrow.items()]
    same = [(a, b) for a, b in pairs if "kp" not in (a, b)]
    assert len(same) >= len(pairs) - 2 and all(a == b for a, b in same)


def test_pairs_and_device_sets_validate_on_their_own_page(tmp_path: Path) -> None:
    out = tmp_path / "sky.svg"
    argv = ["--kind", "skyline", "--variant", "accent", "--theme", "both", "--device", "both"]

    assert forge.main([*argv, "--data", str(DATA / "activity.json"), "--out", str(out)]) == 0

    files = sorted(tmp_path.glob("sky-*.svg"))
    assert [f.name for f in files] == [
        "sky-dark-mobile.svg",
        "sky-dark.svg",
        "sky-light-mobile.svg",
        "sky-light.svg",
    ]
    for path in files:
        check(path.read_text(encoding="utf-8"), repo_check.svg_theme(path))


@pytest.mark.parametrize("size", ["icon-128", "card", "og", "linkedin-banner", "640x900"])
def test_text_stays_in_the_corners_at_any_size(size: str) -> None:
    svg = forge.render("skyline", size=size, title="Contributions in 2026")

    check(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []


@pytest.mark.parametrize(
    "data",
    [
        {"days": []},
        {"days": [{"date": "2026-13-01", "count": 1}]},
        {"days": [{"date": "2026-01-01", "count": -1}]},
        {"start": "2026-01-01", "counts": [1, "x"]},
        {"counts": [1, 2]},
        {"weeks": 3},
        {"start": "0001-01-01", "counts": [1]},
        7,
    ],
)
def test_bad_data_is_rejected(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("skyline", data=data)


def test_bad_variant_is_rejected_and_the_cli_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(forge.ForgeError, match="variant"):
        forge.render("skyline", variant="red")

    assert forge.main(["--kind", "skyline", "--data", '{"days": []}']) == 2
    assert "calendar days" in capsys.readouterr().err
