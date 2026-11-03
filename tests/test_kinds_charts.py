"""forge.py kinds added in 0.4: breakdown (bar, donut, pie) and radar, on desktop and phone."""

from __future__ import annotations

import itertools
import re
from pathlib import Path
from xml.dom import minidom

import pytest

import forge
import poster
import themes
import validate_svg
from test_integration import FACES, overflow

LANGUAGES = [
    {"label": name, "value": value}
    for name, value in [
        ("Python", 512000),
        ("TypeScript", 301000),
        ("JavaScript", 120400),
        ("Rust", 98000),
        ("Go", 64000),
        ("Shell", 31000),
        ("HTML", 22000),
        ("CSS", 18000),
        ("Dockerfile", 9000),
        ("Jupyter Notebook", 8800),
        ("Makefile", 3000),
        ("Lua", 1200),
        ("Nix", 600),
    ]
]
LONG_AXES = {
    "title": "Platform skills",
    "axes": [
        {"label": label, "value": 40 + 7 * k, "compare": 30 + 5 * k}
        for k, label in enumerate(
            [
                "Observability",
                "Infrastructure",
                "Kubernetes",
                "Terraform",
                "Networking",
                "Databases",
                "Security reviews",
                "Incident response",
            ]
        )
    ],
}
THREE = [{"label": x, "value": v} for x, v in (("a", 1), ("b", 2), ("c", 0.5))]
SAMPLES = [  # the sample data of each variant: what a --size canvas is tested with
    pytest.param("breakdown", {}, id="breakdown-bar"),
    pytest.param("breakdown", {"variant": "donut"}, id="breakdown-donut"),
    pytest.param("breakdown", {"variant": "pie"}, id="breakdown-pie"),
    pytest.param("radar", {}, id="radar"),
]
VARIANTS = [
    *SAMPLES,
    pytest.param("breakdown", {"data": LANGUAGES}, id="breakdown-bar-other"),
    pytest.param("breakdown", {"variant": "donut", "data": LANGUAGES}, id="breakdown-donut-other"),
    pytest.param("breakdown", {"variant": "pie", "data": THREE}, id="breakdown-pie-three"),
    pytest.param("radar", {"data": LONG_AXES}, id="radar-eight-long"),
    pytest.param("radar", {"data": THREE}, id="radar-three-plain"),
]
DEVICES = ["desktop", "phone"]
TIMINGS = ["short", "medium", "long"]


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the GitHub page(s) the file is shown on."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def boxes(svg: str) -> list[tuple[str, float, float, float, float]]:
    """Estimated box (text, left, top, right, bottom) of every text element."""
    out = []
    for t in minidom.parseString(svg).getElementsByTagName("text"):
        face, spacing = FACES[t.getAttribute("class").rsplit("-", 1)[-1]]
        size = float(t.getAttribute("font-size"))
        text = "".join(n.data for n in t.childNodes if n.nodeType == n.TEXT_NODE)
        width = forge.text_width(text, size, face, spacing)
        anchor = {"start": 0.0, "middle": 0.5, "end": 1.0}[t.getAttribute("text-anchor") or "start"]
        left = float(t.getAttribute("x")) - width * anchor
        y = float(t.getAttribute("y"))
        out.append((text, left, y - 0.75 * size, left + width, y + 0.25 * size))
    return out


def overlaps(svg: str) -> list[str]:
    """Pairs of texts whose estimated boxes cross."""
    return [
        f"{a[0]!r} and {b[0]!r}"
        for a, b in itertools.combinations(boxes(svg), 2)
        if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]
    ]


def legend(svg: str) -> list[tuple[str, float]]:
    """(label, percent) of each breakdown legend entry, in order."""
    found = re.findall(
        r'class="[\w-]+-m"[^>]*>([^<]+)</text><text class="[\w-]+-m"[^>]*>([\d.]+)%</text>', svg
    )
    return [(label, float(pct)) for label, pct in found]


def swatches(svg: str) -> list[str]:
    """Fill of each legend swatch: the filled circles of a bar breakdown."""
    return re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="[\d.]+" fill="(#[0-9a-f]{6})"/>', svg)


# ---------------------------------------------------------------- every variant


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize(("kind", "options"), VARIANTS)
def test_variant_is_valid_poster_safe_and_deterministic(
    kind: str, options: dict[str, object], theme: str, device: str
) -> None:
    for timing in TIMINGS:
        svg = forge.render(kind, theme=theme, device=device, timing=timing, **options)

        check(svg)
        assert overflow(svg) == []
        assert poster.problems(svg) == []
        assert svg == forge.render(kind, theme=theme, device=device, timing=timing, **options)
        assert svg.endswith("</svg>\n") and "\r" not in svg


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize(("kind", "options"), VARIANTS)
def test_pair_halves_read_on_their_own_page(
    kind: str, options: dict[str, object], device: str
) -> None:
    for page in ("dark", "light"):
        svg = forge.render(kind, theme=page, pair=True, device=device, **options)

        check(svg, page)


@pytest.mark.parametrize("spec", ["nord", "solarized-light", "transparent-light", "#0ea5e9"])
@pytest.mark.parametrize(("kind", "options"), VARIANTS)
def test_other_themes_read_on_their_page(kind: str, options: dict[str, object], spec: str) -> None:
    theme = forge.load_theme(spec)[0]

    check(forge.render(kind, theme=spec, **options), theme.mode if theme.transparent else "both")


@pytest.mark.parametrize("kind", ["breakdown", "radar"])
def test_cli_theme_and_device_both_write_four_files(kind: str, tmp_path: Path) -> None:
    out = tmp_path / f"{kind}.svg"

    assert (
        forge.main(["--kind", kind, "--theme", "both", "--device", "both", "--out", str(out)]) == 0
    )

    for theme in ("dark", "light"):
        for suffix in ("", "-mobile"):
            check((tmp_path / f"{kind}-{theme}{suffix}.svg").read_text(encoding="utf-8"), theme)


@pytest.mark.parametrize(("kind", "options"), VARIANTS)
def test_phone_layout_is_320_wide_with_phone_text(kind: str, options: dict[str, object]) -> None:
    svg = forge.render(kind, device="phone", **options)

    root = minidom.parseString(svg).documentElement
    assert root.getAttribute("width") == str(forge.PHONE_W)
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]
    assert sizes and min(sizes) >= forge.PHONE_TEXT


@pytest.mark.parametrize("size", ["icon-128", "card", "og", "linkedin-banner", "square", "story"])
@pytest.mark.parametrize(("kind", "options"), SAMPLES)
def test_native_layout_fits_any_canvas(kind: str, options: dict[str, object], size: str) -> None:
    svg = forge.render(kind, size=size, **options)

    check(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]
    assert min(sizes) >= forge.FONT_FLOOR


@pytest.mark.parametrize("kind", ["breakdown", "radar"])
def test_default_card_size(kind: str) -> None:
    root = minidom.parseString(forge.render(kind)).documentElement

    expected = {"breakdown": ("495", "195"), "radar": ("400", "320")}[kind]
    assert (root.getAttribute("width"), root.getAttribute("height")) == expected


@pytest.mark.parametrize(("kind", "options"), VARIANTS)
def test_one_clock_a_short_entrance_and_few_moving_parts(
    kind: str, options: dict[str, object]
) -> None:
    short = check(forge.render(kind, timing="short", **options))
    looped = forge.render(kind, timing="medium", **options)

    assert short.stats["longest_s"] <= 1.5 and short.stats["infinite"] == 0
    assert len(set(re.findall(r'dur="([\d.]+)s"', looped))) == 1
    assert check(looped).stats["animated_elements"] <= 14


@pytest.mark.parametrize(("kind", "options"), VARIANTS)
@pytest.mark.parametrize("device", DEVICES)
def test_labels_never_overlap(kind: str, options: dict[str, object], device: str) -> None:
    assert overlaps(forge.render(kind, device=device, **options)) == []


# ---------------------------------------------------------------- breakdown


@pytest.mark.parametrize("variant", ["bar", "donut", "pie"])
@pytest.mark.parametrize("data", [None, LANGUAGES, LANGUAGES[:3], [{"label": "a", "value": 1}] * 3])
def test_breakdown_legend_percents_add_up_to_100(variant: str, data: object) -> None:
    entries = legend(forge.render("breakdown", variant=variant, data=data))

    assert entries
    assert sum(pct for _, pct in entries) == pytest.approx(100, abs=1e-9)


def test_breakdown_merges_more_than_ten_items_into_other() -> None:
    entries = legend(forge.render("breakdown", data=LANGUAGES))

    assert len(entries) == forge.BREAKDOWN_NAMED + 1
    assert entries[-1][0] == "OTHER"
    tail = sum(it["value"] for it in LANGUAGES[forge.BREAKDOWN_NAMED :])
    total = sum(it["value"] for it in LANGUAGES)
    assert entries[-1][1] == pytest.approx(100 * tail / total, abs=0.1)


def test_breakdown_shows_largest_first_and_other_joins_the_tail() -> None:
    data = [{"label": "small", "value": 1}, {"label": "Other", "value": 2}]
    data += [{"label": "big", "value": 7}]

    entries = legend(forge.render("breakdown", data=data))

    assert [label for label, _ in entries] == ["BIG", "SMALL", "OTHER"]
    assert [pct for _, pct in entries] == [70.0, 10.0, 20.0]


@pytest.mark.parametrize(
    "spec",
    [
        "dark",
        "light",
        "nord",
        "solarized-light",
        "high-contrast-dark",
        "transparent-light",
        "#ff6b6b",
    ],
)
def test_breakdown_colors_are_distinct_and_reach_3_to_1(spec: str) -> None:
    theme = forge.load_theme(spec)[0]

    fills = swatches(forge.render("breakdown", theme=spec, data=LANGUAGES))

    assert len(fills) == len(set(fills)) == forge.BREAKDOWN_NAMED + 1
    for ground in forge.mark_grounds(theme):
        assert min(themes.contrast(f, ground) for f in fills) >= 3


def test_breakdown_own_color_is_tuned_like_the_rest() -> None:
    data = [{"label": "dark", "value": 2, "color": "#0b1012"}, {"label": "b", "value": 1}]

    svg = forge.render("breakdown", data=data)

    check(svg)
    assert "#0b1012" not in swatches(svg)


def test_breakdown_donut_names_its_largest_item() -> None:
    svg = forge.render("breakdown", variant="donut", data=LANGUAGES)

    assert re.search(r'class="[\w-]+-b"[^>]*>43\.1%</text>', svg)
    assert ">PYTHON</text>" in svg


def test_breakdown_one_sweep_reveals_the_ring() -> None:
    svg = forge.render("breakdown", variant="pie", timing="medium")

    assert svg.count("<mask") == 1 and svg.count('attributeName="stroke-dashoffset"') == 1


@pytest.mark.parametrize("variant", ["bar", "donut", "pie"])
@pytest.mark.parametrize("text", ['a<b&c"d', "</text><script>alert(1)</script>"])
def test_breakdown_escapes_hostile_text(variant: str, text: str) -> None:
    data = {"title": text, "items": [{"label": text, "value": 2}, {"label": "b", "value": 1}]}

    for device in DEVICES:
        svg = forge.render("breakdown", variant=variant, device=device, data=data)
        check(svg)
        assert "<script" not in svg and "&lt;" in svg


# ---------------------------------------------------------------- radar


def test_radar_compare_draws_a_muted_dashed_polygon_and_a_key() -> None:
    svg = forge.render("radar")

    assert svg.count("<polygon") == 2
    assert re.search(r"<polygon [^>]*stroke-dasharray", svg)
    assert ">THIS RELEASE</text>" in svg and ">LAST RELEASE</text>" in svg


def test_radar_without_compare_has_one_polygon_and_no_key() -> None:
    data = [{"label": x, "value": 50} for x in ("a", "b", "c", "d")]

    svg = forge.render("radar", data=data)

    assert svg.count("<polygon") == 1 and "<line " not in svg


def test_radar_polygon_grows_from_the_center() -> None:
    svg = forge.render("radar")

    grow = re.search(r'<g transform="translate\(([\d.]+) ([\d.]+)\)"><g><animateTransform', svg)
    assert grow and float(grow.group(1)) == 200
    assert 'type="scale" values="0;0;1' in svg


def test_radar_shortens_long_labels_on_a_phone() -> None:
    svg = forge.render("radar", device="phone", data=LONG_AXES)

    assert forge.ELLIPSIS in svg
    assert overlaps(svg) == [] and overflow(svg) == []


@pytest.mark.parametrize("text", ['a<b&c"d', "</text><script>alert(1)</script>"])
def test_radar_escapes_hostile_text(text: str) -> None:
    data = {
        "title": text,
        "series": [text, text],
        "axes": [{"label": text, "value": v, "compare": 1} for v in (1, 2, 3)],
    }

    for device in DEVICES:
        svg = forge.render("radar", device=device, data=data)
        check(svg)
        assert "<script" not in svg and "&lt;" in svg


# ---------------------------------------------------------------- bad data


@pytest.mark.parametrize(
    ("kind", "options"),
    [
        ("breakdown", {"data": []}),
        ("breakdown", {"data": ["Python"]}),
        ("breakdown", {"data": [{"label": "", "value": 1}]}),
        ("breakdown", {"data": [{"label": "a"}]}),
        ("breakdown", {"data": [{"label": "a", "value": -1}]}),
        ("breakdown", {"data": [{"label": "a", "value": 0}]}),
        ("breakdown", {"data": [{"label": "a", "value": 1, "color": "teal"}]}),
        ("breakdown", {"data": [{"label": "a", "value": 1e308}, {"label": "b", "value": 1e308}]}),
        ("breakdown", {"variant": "ring"}),
        ("radar", {"data": [{"label": "a", "value": 1}, {"label": "b", "value": 1}]}),
        ("radar", {"data": [{"label": str(k), "value": 1} for k in range(9)]}),
        ("radar", {"data": {"max": 0, "axes": [{"label": "a", "value": 1}] * 3}}),
        ("radar", {"data": [{"label": "a"}, *THREE[1:]]}),
        ("radar", {"data": ["a", *THREE[1:]]}),
        (
            "radar",
            {"data": [{"label": "a", "value": 1, "compare": 1}] + [{"label": "b", "value": 1}] * 2},
        ),
        ("radar", {"data": {"series": ["one"], "axes": [{"label": "a", "value": 1}] * 3}}),
    ],
)
def test_bad_data_is_a_forge_error(kind: str, options: dict[str, object]) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render(kind, **options)


@pytest.mark.parametrize(
    "argv",
    [
        ["--kind", "breakdown", "--data", "[]"],
        ["--kind", "breakdown", "--variant", "ring"],
        ["--kind", "radar", "--data", '[{"label": "a", "value": 1}]'],
    ],
)
def test_cli_exits_2_on_bad_breakdown_or_radar_data(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert forge.main(argv) == 2
    assert "forge.py: error:" in capsys.readouterr().err
