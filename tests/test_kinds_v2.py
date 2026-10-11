"""forge.py kinds added in 0.2: timeline, logos, calendar, ring, and text specs for flow."""

from __future__ import annotations

import contextlib
import io
import math
import re
import struct
import zlib
from pathlib import Path
from xml.dom import minidom

import pytest

import forge
import poster
import validate_svg

NEW = ["timeline", "logos", "calendar", "ring"]
VARIANTS: list[tuple[str, dict[str, object]]] = [
    ("timeline", {"variant": "vertical"}),
    ("timeline", {"width": 360}),
    ("timeline", {"timing": "short", "loop": True}),
    ("logos", {"timing": "ambient"}),
    ("calendar", {"variant": "accent"}),
    ("ring", {"width": 320, "height": 900}),
    ("flow", {"data": "push -> build -> unit, e2e -> deploy"}),
    ("flow", {"data": "a -> b -[retry]-> a", "timing": "long"}),
]
SIZES = [(320.0, 180.0), (None, None), (1600.0, 900.0)]
FITTED: list[tuple[str, dict[str, object]]] = [
    ("timeline", {}),
    ("timeline", {"variant": "vertical"}),
    ("timeline", {"variant": "horizontal"}),
    ("logos", {}),
    ("calendar", {}),
    ("ring", {}),
]
FACES = {"m": ("mono", forge.MONO_LS), "s": ("sans", 0.0), "r": ("sans", 0.0), "b": ("bold", 0.0)}
LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    'viewBox="0 0 24 24"><defs><linearGradient id="g"><stop offset="0" stop-color="#f00"/>'
    '</linearGradient><clipPath id="c"><rect width="24" height="12"/></clipPath>'
    '<path id="p" d="M0 0h24v24z"/></defs>'
    '<use xlink:href="#p" fill="url(#g)" clip-path="url(&apos;#c&apos;)"/>'
    '<circle cx="12" cy="12" r="4" style="fill:url(#g)"/></svg>'
)


def check(svg: str) -> validate_svg.Report:
    """Validate with no findings at all (contrast as errors, on both GitHub pages) and parse
    with minidom."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error")
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def overflow(svg: str) -> list[str]:
    """Text whose estimated box (forge.text_width) leaves the canvas; clipped strips excepted."""
    root = minidom.parseString(svg).documentElement
    w, h = float(root.getAttribute("width")), float(root.getAttribute("height"))
    out = []
    for t in root.getElementsByTagName("text"):
        node = t.parentNode
        clipped = False
        while node is not None and node.nodeType == node.ELEMENT_NODE:
            clipped = clipped or node.hasAttribute("clip-path")
            node = node.parentNode
        if clipped:
            continue
        face, spacing = FACES[t.getAttribute("class").rsplit("-", 1)[-1]]
        size = float(t.getAttribute("font-size"))
        text = "".join(n.data for n in t.childNodes if n.nodeType == n.TEXT_NODE)
        width = forge.text_width(text, size, face, spacing)
        anchor = {"start": 0.0, "middle": 0.5, "end": 1.0}[t.getAttribute("text-anchor") or "start"]
        left = float(t.getAttribute("x")) - width * anchor
        y = float(t.getAttribute("y"))
        if left < -0.5 or left + width > w + 0.5 or y - 0.75 * size < -0.5 or y + 0.25 * size > h:
            out.append(f"{text!r} spans x {left:.1f}..{left + width:.1f}, y {y:.1f} on {w:g}x{h:g}")
    return out


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    head = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x80\x00\xff")
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


def logo_file(tmp_path: Path, text: str, name: str = "logo.svg") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def svg_ids(svg: str) -> list[str]:
    return re.findall(r'\bid="([^"]+)"', svg)


def prefix_of(svg: str) -> str:
    return re.search(r'<title id="([\w-]+?)title"', svg).group(1)


# ---------------------------------------------------------------- every new kind


@pytest.mark.parametrize("kind", NEW)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_new_kind_is_valid_deterministic_and_poster_safe(kind: str, theme: str) -> None:
    svg = forge.render(kind, theme=theme)

    check(svg)
    assert svg == forge.render(kind, theme=theme)
    assert poster.problems(svg) == []


@pytest.mark.parametrize(("kind", "options"), VARIANTS, ids=lambda v: str(v))
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_variant_is_valid_deterministic_and_poster_safe(
    kind: str, options: dict[str, object], theme: str
) -> None:
    svg = forge.render(kind, theme=theme, **options)

    check(svg)
    assert svg == forge.render(kind, theme=theme, **options)
    assert poster.problems(svg) == []


@pytest.mark.parametrize(("kind", "options"), FITTED, ids=lambda v: str(v))
@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_text_stays_inside_the_canvas_at_any_size(
    kind: str, options: dict[str, object], size: tuple[float | None, float | None]
) -> None:
    svg = forge.render(kind, width=size[0], height=size[1], **options)

    check(svg)
    assert overflow(svg) == []


def test_overflow_check_catches_text_past_the_edge() -> None:
    svg = forge.render("ring", data=[{"label": "a", "value": 5}])
    moved = re.sub(r'(<text class="[\w-]+-m" x=")[\d.]+', r"\g<1>9999", svg, count=1)

    assert overflow(svg) == [] and overflow(moved)


@pytest.mark.parametrize("kind", NEW)
def test_fixed_canvas_size_is_kept(kind: str) -> None:
    doc = minidom.parseString(forge.render(kind, width=500, height=420)).documentElement

    assert (doc.getAttribute("width"), doc.getAttribute("height")) == ("500", "420")


@pytest.mark.parametrize("kind", NEW)
def test_short_entrance_finishes_by_one_and_a_half_seconds(kind: str) -> None:
    report = check(forge.render(kind, timing="short"))

    assert report.stats["longest_s"] <= 1.5
    assert report.stats["infinite"] == 0


@pytest.mark.parametrize("kind", NEW)
def test_fonts_never_drop_below_the_floor(kind: str) -> None:
    svg = forge.render(kind, width=200, height=120)

    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]
    assert sizes and min(sizes) >= forge.FONT_FLOOR


def test_help_epilog_lists_the_new_kinds() -> None:
    text = forge.build_parser().format_help()

    for kind in NEW:
        assert re.search(rf"^  {kind}\s", text, re.M), kind
    assert "text spec" in text


def test_is_dark_follows_the_theme() -> None:
    assert forge.is_dark(forge.THEMES["dark"]) and not forge.is_dark(forge.THEMES["light"])


# ---------------------------------------------------------------- timeline


def test_timeline_current_item_pulses_when_looping() -> None:
    svg = forge.render("timeline", timing="long")

    assert '<animate attributeName="r"' in svg
    assert 'repeatCount="indefinite"' in svg


def test_timeline_played_once_holds_a_still_halo() -> None:
    svg = forge.render("timeline", timing="short")

    assert '<animate attributeName="r"' not in svg
    assert 'opacity="0.45"' in svg  # the halo stays visible on the current node


def test_timeline_narrow_canvas_runs_vertically() -> None:
    narrow = forge.render("timeline", width=360)
    wide = forge.render("timeline")

    assert re.search(r'<path d="M[\d.]+ [\d.]+ V', narrow)
    assert re.search(r'<path d="M[\d.]+ [\d.]+ H', wide)


def test_timeline_open_current_item_reads_now() -> None:
    svg = forge.render("timeline", data=[{"start": "2024", "title": "Lead", "current": True}])

    assert "2024 - NOW" in svg
    assert "(current)" in svg


def test_timeline_long_title_is_cut_with_ellipsis() -> None:
    data = [{"start": "2020", "title": "x" * 60}, {"start": "2021", "title": "y"}]

    svg = forge.render("timeline", data=data, width=560)

    assert forge.ELLIPSIS in svg
    assert "x" * 60 in svg  # the description keeps the full title


@pytest.mark.parametrize(
    "data",
    [
        [],
        ["just text"],
        [{"title": "no start"}],
        [{"start": "2020"}],
        [{"start": "2020", "title": "t", "current": "yes"}],
        [{"start": "2020", "title": "t"}] * 13,
    ],
)
def test_timeline_rejects_bad_items(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("timeline", data=data)


def test_timeline_rejects_unknown_variant() -> None:
    with pytest.raises(forge.ForgeError, match="horizontal or vertical"):
        forge.render("timeline", variant="diagonal")


# ---------------------------------------------------------------- logos


def test_logo_ids_urls_and_hrefs_get_a_per_logo_prefix(tmp_path: Path) -> None:
    data = [{"label": "Acme", "svg": logo_file(tmp_path, LOGO)}]

    svg = forge.render("logos", data=data)

    p = prefix_of(svg)
    check(svg)
    assert all(i.startswith(p) for i in svg_ids(svg))
    assert f'id="{p}l0-g"' in svg and f'id="{p}l0-p"' in svg
    assert f'href="#{p}l0-p"' in svg and "xlink" not in svg
    assert f"url(#{p}l0-g)" in svg and f"url(#{p}l0-c)" in svg
    assert f"fill:url(#{p}l0-g)" in svg
    assert "url(#g)" not in svg and 'href="#p"' not in svg


def test_two_logos_with_the_same_ids_do_not_collide(tmp_path: Path) -> None:
    path = logo_file(tmp_path, LOGO)

    svg = forge.render("logos", data=[{"label": "A", "svg": path}, {"label": "B", "svg": path}])

    check(svg)  # SV012 would flag a repeated id
    ids = svg_ids(svg)
    assert len(ids) == len(set(ids))


def test_logo_symbol_is_used_with_the_entry_color() -> None:
    mark = '<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'

    svg = forge.render("logos", data=[{"label": "A", "svg": mark, "color": "#22c55e"}])

    p = prefix_of(svg)
    ink = forge.accent_ink("#22c55e", forge.THEMES["dark"])  # entry colors are tuned per theme
    assert f'<symbol id="{p}logo0" viewBox="0 0 10 10">' in svg
    assert re.search(rf'<use href="#{p}logo0"[^>]* fill="{ink}" color="{ink}"/>', svg)


def test_logo_editor_metadata_and_aria_are_dropped(tmp_path: Path) -> None:
    text = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:ink="urn:ink" viewBox="0 0 8 8" '
        'role="img" aria-label="x" fill="#123456"><title>Mark</title><metadata>m</metadata>'
        '<ink:guide/><path class="a" ink:label="z" data-n="1" d="M0 0h8v8z"/></svg>'
    )

    svg = forge.render("logos", data=[{"label": "A", "svg": logo_file(tmp_path, text)}])

    check(svg)
    for gone in (">Mark<", "metadata", "urn:ink", "guide", "label=", "data-n", 'class="a"'):
        assert gone not in svg, gone
    assert '<g fill="#123456"><path d="M0 0h8v8z"/></g>' in svg


def test_logo_without_viewbox_uses_width_and_height() -> None:
    mark = '<svg width="32px" height="16"><rect width="32" height="16"/></svg>'

    svg = forge.render("logos", data=[{"label": "A", "svg": mark}])

    assert 'viewBox="0 0 32 16"' in svg


@pytest.mark.parametrize(
    ("markup", "reason"),
    [
        ('<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>', "script"),
        ('<svg viewBox="0 0 1 1"><foreignObject/></svg>', "foreignObject"),
        ('<svg viewBox="0 0 1 1"><style>path{fill:red}</style></svg>', "style"),
        ('<svg viewBox="0 0 1 1"><image href="data:image/png;base64,AA=="/></svg>', "image"),
        ('<svg viewBox="0 0 1 1"><a href="#x"><path d="M0 0"/></a></svg>', "<a>"),
        ('<svg viewBox="0 0 1 1"><set attributeName="href" to="x"/></svg>', "set"),
        ('<svg viewBox="0 0 1 1" onload="x()"><path d="M0 0"/></svg>', "event handler"),
        ('<svg viewBox="0 0 1 1"><use href="https://e.x/a.svg#a"/></svg>', "outside"),
        ('<svg viewBox="0 0 1 1"><use href="data:image/svg+xml,x"/></svg>', "outside"),
        ('<svg viewBox="0 0 1 1"><path fill="url(https://e.x/p)" d="M0 0"/></svg>', "url"),
        ('<svg viewBox="0 0 1 1"><path style="fill:url(//e.x/p)" d="M0 0"/></svg>', "url"),
        ('<svg viewBox="0 0 1 1"><path style="fill:u\\72l(x)" d="M0 0"/></svg>', "escaped"),
        ('<svg viewBox="0 0 1 1"><path fill="javascript:x" d="M0 0"/></svg>', "scripted"),
        ('<!DOCTYPE svg [<!ENTITY a "b">]><svg viewBox="0 0 1 1"><path d="&a;"/></svg>', "DOCTYPE"),
        ('<svg viewBox="0 0 1 1"><path id="a" d="M0 0"/><path id="a" d="M0 0"/></svg>', "repeats"),
        ('<svg viewBox="0 0 1 1"><path d="M0 0"></svg>', "well-formed"),
        ('<html><svg viewBox="0 0 1 1"/></html>', "root"),
        ('<svg><path d="M0 0"/></svg>', "viewBox"),
        ('<svg viewBox="0 0 1 1"><title>t</title></svg>', "nothing to draw"),
    ],
)
def test_unsafe_or_broken_logo_is_rejected(markup: str, reason: str) -> None:
    with pytest.raises(forge.ForgeError, match=re.escape(reason)):
        forge.render("logos", data=[{"label": "A", "svg": markup}])


def test_png_logo_is_embedded_as_a_data_uri(tmp_path: Path) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(tiny_png())

    svg = forge.render("logos", data=[{"label": "A", "image": str(path)}])

    check(svg)
    assert '<image href="data:image/png;base64,' in svg
    assert 'viewBox="0 0 1 1"' in svg


def test_webp_logo_gets_the_webp_type(tmp_path: Path) -> None:
    path = tmp_path / "logo.webp"
    path.write_bytes(b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00" + b"\x00" * 13)

    svg = forge.render("logos", data=[{"label": "A", "image": str(path)}])

    assert "data:image/webp;base64," in svg


def test_raster_logo_must_be_png_or_webp(tmp_path: Path) -> None:
    path = tmp_path / "logo.gif"
    path.write_bytes(b"GIF89a" + b"\x00" * 20)

    with pytest.raises(forge.ForgeError, match="PNG or WebP"):
        forge.render("logos", data=[{"label": "A", "image": str(path)}])


def test_raster_logo_over_64_kb_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "big.png"
    path.write_bytes(tiny_png() + b"\x00" * 50_000)

    with pytest.raises(forge.ForgeError, match="64 KB"):
        forge.render("logos", data=[{"label": "A", "image": str(path)}])


def test_svg_logo_over_64_kb_is_rejected() -> None:
    markup = '<svg viewBox="0 0 1 1">' + '<path d="M0 0"/>' * 5000 + "</svg>"

    with pytest.raises(forge.ForgeError, match="64 KB"):
        forge.render("logos", data=[{"label": "A", "svg": markup}])


def test_missing_logo_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(forge.ForgeError, match="cannot read"):
        forge.render("logos", data=[{"label": "A", "svg": str(tmp_path / "none.svg")}])


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"label": ""}],
        [{"label": "A", "svg": "<svg/>", "image": "x.png"}],
        [{"label": "A", "svg": 5}],
        [5],
        {"items": [{"label": "A"}], "cols": 9},
    ],
)
def test_logos_reject_bad_entries(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("logos", data=data)


def test_entries_without_a_file_render_as_text_pills() -> None:
    svg = forge.render("logos", data=["alpha", {"label": "beta"}])

    check(svg)
    assert "<use" not in svg and "<symbol" not in svg
    assert ">ALPHA</text>" in svg and ">BETA</text>" in svg


def test_logo_grid_balances_rows() -> None:
    svg = forge.render("logos", data=[f"n{i}" for i in range(6)], width=840)

    tops = {float(y) for y in re.findall(r'<rect x="[\d.]+" y="([\d.]+)" width', svg)[1:]}
    assert len(tops) == 2  # 6 pills: two rows of three, not five and one


def test_logo_marquee_duration_follows_speed() -> None:
    def seconds(speed: float) -> float:
        svg = forge.render("logos", timing="ambient", speed=speed)
        return float(re.search(r'animateTransform[^>]* dur="([\d.]+)s"', svg).group(1))

    assert seconds(20) == pytest.approx(seconds(40) * 2, abs=0.002)


def test_logo_marquee_repeats_its_strip_seamlessly() -> None:
    svg = forge.render("logos", timing="ambient")

    span = float(re.search(r'values="0 0;-([\d.]+) 0', svg).group(1))
    xs = sorted(float(x) for x in re.findall(r'<g><rect x="([\d.]+)"', svg))
    assert any(abs(x - (xs[0] + span)) < 0.01 for x in xs)  # second copy starts one span on


# ---------------------------------------------------------------- calendar


def cells(svg: str) -> list[str]:
    """Fills of the day cells (the rects inside the revealed bands)."""
    bands = re.findall(r'<g><animate attributeName="opacity"[^>]*/>(.*?)</g>', svg)
    return [f for band in bands for f in re.findall(r'fill="(#[0-9a-f]{6})"', band)]


def test_calendar_grid_is_53_weeks_sunday_first() -> None:
    svg = forge.render("calendar", data={"days": [{"date": "2026-10-07", "count": 1}]})

    # last date is a Wednesday: 52 full weeks plus Sunday to Wednesday
    assert len(cells(svg)) == 52 * 7 + 4
    assert "from 2025-10-05 to 2026-10-07" in svg  # 2025-10-05 is a Sunday


def test_calendar_days_and_counts_formats_draw_the_same_grid() -> None:
    days = {"days": [{"date": "2026-03-01", "count": 2}, {"date": "2026-03-03", "count": 5}]}
    counts = {"start": "2026-03-01", "counts": [2, 0, 5]}

    assert forge.render("calendar", data=days, id_prefix="c") == forge.render(
        "calendar", data=counts, id_prefix="c"
    )


def test_calendar_bare_list_is_a_days_list() -> None:
    svg = forge.render("calendar", data=[{"date": "2026-01-02", "count": 4}])

    assert "4 contributions on 1 days" in svg


def test_calendar_repeated_dates_add_up() -> None:
    data = {"days": [{"date": "2026-05-05", "count": 2}, {"date": "2026-05-05", "count": 3}]}

    assert "5 contributions on 1 days" in forge.render("calendar", data=data)


def test_calendar_levels_are_quartiles_of_active_days() -> None:
    counts = [*range(1, 13), 1000]

    svg = forge.render("calendar", data={"start": "2026-01-04", "counts": counts})

    ramp = forge.render("calendar")  # noqa: F841 - same theme, ramp from the theme tokens
    used = set(cells(svg))
    assert len(used) == 5  # empty plus all four levels, not one bright day and the rest dim


def test_calendar_draws_month_labels_and_a_legend() -> None:
    svg = forge.render("calendar")

    for text in (">JAN</text>", ">JUN</text>", ">MON</text>", ">LESS</text>", ">MORE</text>"):
        assert text in svg


def test_calendar_green_ramp_ends_at_the_theme_ok_color() -> None:
    for theme in ("dark", "light"):
        svg = forge.render("calendar", theme=theme)
        assert forge.THEMES[theme].ok in cells(svg)


def test_calendar_accent_variant_ramps_the_accent() -> None:
    svg = forge.render("calendar", variant="accent", accent="#a78bfa")

    assert "#a78bfa" in cells(svg)
    assert forge.THEMES["dark"].ok not in cells(svg)


@pytest.mark.parametrize(
    "data",
    [
        {"days": []},
        {"days": ["2026-01-01"]},
        {"days": [{"date": "2026-13-01", "count": 1}]},
        {"days": [{"date": 20260101, "count": 1}]},
        {"days": [{"date": "2026-01-01", "count": -1}]},
        {"days": [{"date": "2026-01-01", "count": "many"}]},
        {"start": "2026-01-01"},
        {"start": "soon", "counts": [1]},
        {"start": "9999-12-30", "counts": [1, 1, 1]},
        {"weeks": 3},
    ],
)
def test_calendar_rejects_bad_data(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("calendar", data=data)


def test_calendar_rejects_unknown_variant() -> None:
    with pytest.raises(forge.ForgeError, match="green or accent"):
        forge.render("calendar", variant="blue")


# ---------------------------------------------------------------- ring


def test_ring_arc_is_dash_math_without_path_length() -> None:
    svg = forge.render("ring", data=[{"label": "a", "value": 25}])

    assert "pathLength" not in svg and "vector-effect" not in svg
    arc = re.search(
        r'<circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)"[^>]*stroke-dasharray="([\d.]+) ([\d.]+)"',
        svg,
    )
    r, dash, gap = (float(v) for v in arc.groups())
    assert dash == pytest.approx(2 * math.pi * r * 0.25, abs=0.02)
    assert gap == pytest.approx(2 * math.pi * r, abs=0.02)
    assert 'stroke-dashoffset="0"' in svg


def test_ring_values_are_static_text() -> None:
    svg = forge.render("ring", data=[{"label": "a", "value": 18, "max": 24}])

    assert re.search(r"<text [^>]*>75%</text>", svg)  # no animate child: nothing counts up
    assert ">18 / 24</text>" in svg


def test_ring_at_zero_draws_only_the_track() -> None:
    svg = forge.render("ring", data=[{"label": "a", "value": 0}])

    assert svg.count("<circle") == 1
    assert ">0%</text>" in svg


def test_ring_percent_is_not_rounded_up_to_full() -> None:
    svg = forge.render("ring", data=[{"label": "a", "value": 99.9}])

    assert ">99%</text>" in svg


def test_ring_wraps_into_rows_on_a_tall_canvas() -> None:
    svg = forge.render("ring", width=320, height=900)

    centers = {c for c in re.findall(r'<circle cx="[\d.]+" cy="([\d.]+)"', svg)}
    assert len(centers) == 3  # one ring per row


@pytest.mark.parametrize(
    "data",
    [[], ["a"], [{"label": "a", "value": 1, "max": 0}], [{"label": "a", "value": "x"}]],
)
def test_ring_rejects_bad_items(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("ring", data=data)


# ---------------------------------------------------------------- text specs for flow


def test_text_spec_chain_with_parallel_branches() -> None:
    spec = forge.parse_flow_text("push -> build -> unit, e2e -> deploy")

    assert spec["nodes"] == ["push", "build", "unit", "e2e", "deploy"]
    assert spec["edges"] == [
        ["push", "build", ""],
        ["build", "unit", ""],
        ["build", "e2e", ""],
        ["unit", "deploy", ""],
        ["e2e", "deploy", ""],
    ]


def test_text_spec_labels_an_edge() -> None:
    spec = forge.parse_flow_text("build -[artifact]-> deploy")

    assert spec["edges"] == [["build", "deploy", "artifact"]]


def test_text_spec_accepts_long_arrows_and_spaces_in_names() -> None:
    spec = forge.parse_flow_text("unit tests --> deploy-prod")

    assert spec["nodes"] == ["unit tests", "deploy-prod"]


def test_text_spec_statements_comments_and_repeated_edges() -> None:
    spec = forge.parse_flow_text("# ci\na -> b\n\nb -> c; a -> b")

    assert spec["nodes"] == ["a", "b", "c"]
    assert spec["edges"] == [["a", "b", ""], ["b", "c", ""]]


def test_text_spec_orders_steps_by_flow() -> None:
    spec = forge.parse_flow_text("b -> c\na -> b")

    assert spec["nodes"] == ["a", "b", "c"]


def test_text_spec_cycle_becomes_a_return_arc() -> None:
    svg = forge.render("flow", data="a -> b -> c -[retry]-> a")

    check(svg)
    assert 'stroke-dasharray="4 4"' in svg and "RETRY" in svg


def test_text_spec_matches_the_same_json() -> None:
    json_data = {"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["a", "c", "x"]]}

    text = forge.render("flow", data="a -> b\na -[x]-> c", id_prefix="f")

    assert text == forge.render("flow", data=json_data, id_prefix="f")


def test_text_spec_names_are_escaped() -> None:
    svg = forge.render("flow", data='a&"b -[</text><script>x</script>]-> c')

    check(svg)
    assert "<script" not in svg and "&amp;" in svg and "&lt;/TEXT&gt;" in svg


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        ("", "at least 2"),
        ("# just a comment", "at least 2"),
        ("a", "at least 2"),
        ("a ->", "empty step"),
        ("-> b", "empty step"),
        ("a -> , b", "empty step"),
        ("a => b", "not a step name"),
        ("a -[x> b", "not a step name"),
        ("a <- b", "not a step name"),
        ("a -> a", "itself"),
        (" -> ".join(f"n{i}" for i in range(13)), "at most 12"),
        ("a, b, c, d, e -> f, g, h, i", "at most 16"),
    ],
)
def test_bad_text_spec_is_rejected(spec: str, reason: str) -> None:
    with pytest.raises(forge.ForgeError, match=reason):
        forge.render("flow", data=spec)


def test_cli_takes_an_inline_text_spec_for_flow(tmp_path: Path) -> None:
    out = tmp_path / "flow.svg"

    with contextlib.redirect_stdout(io.StringIO()):
        code = forge.main(["--kind", "flow", "--data", "a -> b, c", "--out", str(out)])

    assert code == 0
    check(out.read_text(encoding="utf-8"))


def test_cli_reads_a_txt_spec_file_for_flow(tmp_path: Path) -> None:
    spec = tmp_path / "ci.txt"
    spec.write_text("# ci\nbuild -> test -> ship\n", encoding="utf-8")

    data = forge.load_data(str(spec), text_spec=True)

    assert data == "# ci\nbuild -> test -> ship\n"
    assert "SHIP" in forge.render("flow", data=data)


def test_json_flow_file_still_loads_as_json(tmp_path: Path) -> None:
    path = tmp_path / "flow.json"
    path.write_text('{"nodes": ["a", "b"]}', encoding="utf-8")

    assert forge.load_data(str(path), text_spec=True) == {"nodes": ["a", "b"]}


def test_text_spec_is_only_read_for_flow(capsys: pytest.CaptureFixture[str]) -> None:
    code = forge.main(["--kind", "tiles", "--data", "a -> b"])

    assert code == 2
    assert "neither inline JSON nor a file" in capsys.readouterr().err
