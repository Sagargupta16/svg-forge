"""forge.py: every kind renders valid, deterministic, escaped SVG across themes and timings."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.dom import minidom

import pytest

import forge
import poster
import validate_svg

# Each kind with its default timing plus contrasting ones; the meta-test keeps it complete.
CASES: dict[str, list[str]] = {
    "tiles": ["short", "medium", "micro"],
    "hero": ["long", "short"],
    "marquee": ["ambient", "medium", "short"],
    "chart": ["short", "medium"],
    "bars": ["short", "long"],
    "flow": ["medium", "long", "short", "ambient"],
    "loader": ["medium", "micro", "ambient"],
    "typing": ["long", "short", "ambient"],
    "divider": ["medium", "short", "ambient"],
    "badge": ["medium", "short"],
}
PARAMS = [(k, theme, t) for k, ts in CASES.items() for theme in ("dark", "light") for t in ts]
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]


def check(svg: str) -> validate_svg.Report:
    """Validate, parse with minidom, and return the report (asserting no findings)."""
    report = validate_svg.validate_text(svg.encode("utf-8"))
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def test_every_kind_has_cases() -> None:
    assert set(CASES) == set(forge.KINDS)


@pytest.mark.parametrize(("kind", "theme", "timing"), PARAMS)
def test_kind_renders_valid_deterministic_svg(kind: str, theme: str, timing: str) -> None:
    svg = forge.render(kind, theme=theme, timing=timing)

    check(svg)
    assert svg == forge.render(kind, theme=theme, timing=timing)
    assert svg.endswith("</svg>\n")
    assert "\r" not in svg


@pytest.mark.parametrize("kind", list(forge.KINDS))
@pytest.mark.parametrize("loop", [True, False])
def test_loop_and_once_stay_valid(kind: str, loop: bool) -> None:
    svg = forge.render(kind, loop=loop)

    check(svg)
    assert ('repeatCount="indefinite"' in svg) is loop
    if not loop:
        assert "infinite" not in svg


@pytest.mark.parametrize(("kind", "theme", "timing"), PARAMS)
@pytest.mark.parametrize("loop", [None, True, False])
def test_static_frame_shows_the_finished_state(
    kind: str, theme: str, timing: str, loop: bool | None
) -> None:
    svg = forge.render(kind, theme=theme, timing=timing, loop=loop)

    assert poster.problems(svg) == []


def test_poster_check_catches_hidden_entrance() -> None:
    hidden = forge.render("tiles").replace("<g><animate", '<g opacity="0"><animate', 1)

    assert poster.problems(hidden)


@pytest.mark.parametrize("kind", list(forge.KINDS))
def test_loop_durations_stay_in_preset_range(kind: str) -> None:
    svg = forge.render(kind, timing="medium")

    durations = [float(d) for d in re.findall(r'dur="([\d.]+)s"', svg)]
    if kind != "marquee":  # a marquee pass is fitted to the range by speed, checked below
        assert max(durations) <= forge.PRESETS["medium"].hi


@pytest.mark.parametrize("kind", ["tiles", "bars", "chart", "flow", "badge", "divider"])
def test_short_entrance_finishes_by_one_and_a_half_seconds(kind: str) -> None:
    report = check(forge.render(kind, timing="short"))

    assert report.stats["longest_s"] <= 1.5
    assert report.stats["infinite"] == 0


def hostile_data(kind: str, s: str) -> object:
    return {
        "tiles": [{"value": s, "label": s}],
        "hero": {
            "title": s,
            "kicker": s,
            "taglines": [s, s],
            "status": s,
            "meta": s,
            "nodes": [s, "b", "c"],
        },
        "marquee": [s, s],
        "chart": {"title": s, "values": [1, 3, 2], "labels": [s, s], "peak": s[:12]},
        "bars": {"title": s, "items": [{"label": s, "value": 5}]},
        "flow": {"title": s, "nodes": [s, {"id": "b", "label": s}], "edges": [[s, "b", s]]},
        "loader": None,
        "typing": {"title": s, "lines": [{"cmd": s, "out": [s]}]},
        "divider": None,
        "badge": {"label": s, "value": s},
    }[kind]


@pytest.mark.parametrize("kind", list(forge.KINDS))
@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_text_is_escaped(kind: str, text: str) -> None:
    svg = forge.render(kind, title=text, data=hostile_data(kind, text))

    check(svg)
    assert "<script" not in svg
    assert "&lt;" in svg
    if "&" in text:
        assert "&amp;" in svg


def test_hostile_text_survives_into_title_and_desc() -> None:
    svg = forge.render("tiles", title=HOSTILE[0], data=[{"value": "1", "label": HOSTILE[1]}])

    doc = minidom.parseString(svg)
    assert doc.getElementsByTagName("title")[0].firstChild.data == HOSTILE[0]
    assert HOSTILE[1] in doc.getElementsByTagName("desc")[0].firstChild.data


@pytest.mark.parametrize("value", ["blue", "#12", "#12345g", "rgb(0,0,0)", ""])
def test_bad_accent_is_rejected(value: str) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("badge", accent=value)


def test_short_hex_accent_expands() -> None:
    svg = forge.render("divider", accent="#9CF")

    assert "#99ccff" in svg


def test_accent_ink_is_clamped_per_theme() -> None:
    dark, light = forge.THEMES["dark"], forge.THEMES["light"]

    assert forge.ink_for("#1e3a8a", dark) != "#1e3a8a"
    assert forge.ink_for("#60a5fa", dark) == "#60a5fa"
    assert forge.ink_for("#60a5fa", light) != "#60a5fa"


def test_cli_rejects_bad_accent_with_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    code = forge.main(["--kind", "badge", "--accent", "nope"])

    assert code == 2
    assert "--accent" in capsys.readouterr().err


def test_theme_both_writes_pair_and_prints_picture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "card.svg"

    code = forge.main(["--kind", "hero", "--theme", "both", "--out", str(out)])

    printed = capsys.readouterr().out
    dark, light = tmp_path / "card-dark.svg", tmp_path / "card-light.svg"
    assert code == 0
    assert dark.is_file() and light.is_file() and not out.exists()
    assert dark.read_bytes() != light.read_bytes()
    assert '<source media="(prefers-color-scheme: dark)"' in printed
    assert "card-light.svg" in printed
    for path in (dark, light):
        check(path.read_text(encoding="utf-8"))


def test_theme_both_needs_out() -> None:
    assert forge.main(["--kind", "badge", "--theme", "both"]) == 2


def test_stdout_gets_the_svg_bytes(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    code = forge.main(["--kind", "badge"])

    out = capsysbinary.readouterr().out
    assert code == 0
    assert out == forge.render("badge").encode("utf-8")


def test_write_skips_unchanged_file(tmp_path: Path) -> None:
    out = tmp_path / "x.svg"
    svg = forge.render("loader")

    assert forge.write(out, svg) is True
    assert forge.write(out, svg) is False


def test_reduced_motion_respect_adds_media_block() -> None:
    respect = forge.render("typing", reduced_motion="respect")
    ignore = forge.render("typing")

    assert "prefers-reduced-motion: reduce" in respect
    assert "prefers-reduced-motion" not in ignore
    check(respect)


def test_marquee_duration_follows_speed() -> None:
    def durations(speed: float) -> list[float]:
        svg = forge.render("marquee", timing="ambient", speed=speed)
        return [float(d) for d in re.findall(r'dur="([\d.]+)s"', svg)]

    slow, fast = durations(20), durations(40)

    assert len(slow) == len(fast) == 1
    assert slow[0] == pytest.approx(fast[0] * 2, abs=0.002)


def test_ambient_cycle_is_twenty_to_sixty_seconds() -> None:
    svg = forge.render("flow", timing="ambient", speed=40)

    longest = max(float(d) for d in re.findall(r'dur="([\d.]+)s"', svg))
    assert 20 <= longest <= 60


def test_long_text_is_truncated_with_ellipsis() -> None:
    svg = forge.render("tiles", data=[{"value": "1", "label": "x" * 60}], width=300)

    assert forge.ELLIPSIS in svg
    assert "X" * 60 not in svg  # the visible label is cut
    assert f"1 {'x' * 60}</desc>" in svg  # the description keeps the full text


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [(290, 0, "290"), (100, 2, "100"), (1.50, 2, "1.5"), (-0.001, 2, "0"), (12.3456, 3, "12.346")],
)
def test_num_trims_only_decimal_zeros(value: float, places: int, expected: str) -> None:
    assert forge.num(value, places) == expected


def test_chart_axis_labels_keep_whole_numbers() -> None:
    svg = forge.render("chart", data={"values": [290, 1120]})

    assert ">290</text>" in svg and ">1.1k</text>" in svg


def test_text_width_uses_documented_factors() -> None:
    assert forge.text_width("abcd", 10, "mono") == pytest.approx(4 * 6.2)
    assert forge.text_width("ab", 10, "mono", 1.2) == pytest.approx(2 * 7.4)
    assert forge.fit("short", 500, 10) == "short"


def test_en_and_em_dashes_become_hyphens() -> None:
    svg = forge.render("badge", title=f"a{chr(0x2014)}b{chr(0x2013)}c")

    assert chr(0x2014) not in svg and chr(0x2013) not in svg
    assert "a-b-c" in svg


def test_ids_and_classes_carry_one_prefix() -> None:
    svg = forge.render("flow")

    prefix = re.search(r'<title id="([\w-]+?)title"', svg).group(1)
    ids = re.findall(r'\bid="([^"]+)"', svg)
    assert ids and all(i.startswith(prefix) for i in ids)
    assert all(c.startswith(prefix) for c in re.findall(r'class="([^"]+)"', svg))
    assert prefix != re.search(r'<title id="([\w-]+?)title"', forge.render("tiles")).group(1)


def test_id_prefix_option_is_used_and_validated() -> None:
    assert 'id="hdrtitle"' in forge.render("badge", id_prefix="hdr")
    with pytest.raises(forge.ForgeError):
        forge.render("badge", id_prefix="1bad")


def test_svg_root_is_accessible() -> None:
    doc = minidom.parseString(forge.render("chart")).documentElement

    assert doc.getAttribute("role") == "img"
    assert doc.getAttribute("aria-labelledby").split() == [
        doc.getElementsByTagName("title")[0].getAttribute("id"),
        doc.getElementsByTagName("desc")[0].getAttribute("id"),
    ]


def test_no_external_resources_anywhere() -> None:
    for kind in forge.KINDS:
        svg = forge.render(kind)
        assert "http" not in svg.replace(forge.SVG_NS, "")
        assert "@import" not in svg and "<image" not in svg


def test_data_loads_inline_or_from_file(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    path.write_text(json.dumps(["a", "b"]), encoding="utf-8")

    assert forge.load_data('["a", "b"]') == ["a", "b"]
    assert forge.load_data(str(path)) == ["a", "b"]
    with pytest.raises(forge.ForgeError):
        forge.load_data("[not json")
    with pytest.raises(forge.ForgeError):
        forge.load_data(str(tmp_path / "missing.json"))


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("tiles", []),
        ("chart", {"values": [1]}),
        ("flow", {"nodes": ["a", "a"]}),
        ("flow", {"nodes": ["a", "b"], "edges": [["a", "c"]]}),
        ("bars", {"items": [{"label": "x", "value": 1, "max": 0}]}),
        ("loader", {"variant": "wheel"}),
    ],
)
def test_bad_data_is_rejected(kind: str, data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render(kind, data=data)


def test_font_stack_rejects_css_injection() -> None:
    assert "Georgia" in forge.render("hero", font="serif")
    with pytest.raises(forge.ForgeError):
        forge.render("hero", font="x}@import url(https://e.x/f.css);{")


def test_flow_back_edge_runs_after_the_columns() -> None:
    data = {"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["b", "c"], ["c", "a", "retry"]]}

    svg = forge.render("flow", timing="long", data=data)

    check(svg)
    assert "RETRY" in svg
    assert 'stroke-dasharray="4 4"' in svg


def test_straight_edge_label_sits_at_the_middle() -> None:
    data = {
        "nodes": [{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 1, "y": 0}],
        "edges": [["a", "b", "go"]],
    }

    svg = forge.render("flow", data=data, width=600)

    x = float(re.search(r'x="([\d.]+)"[^>]*>GO</text>', svg).group(1))
    assert 250 < x < 350
