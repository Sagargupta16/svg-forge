"""--device phone for tiles, hero, marquee, chart, bars and typing: a native 320 px layout
with text at 10.5 px or more that keeps the desktop look, contrast and motion."""

from __future__ import annotations

import re
from pathlib import Path
from xml.dom import minidom

import pytest
from test_integration import overflow

import forge
import poster
import validate_svg

KINDS = ["tiles", "hero", "marquee", "chart", "bars", "typing"]
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]


def hostile_data(kind: str, s: str) -> object:
    return {
        "tiles": [{"value": s, "label": s}, {"value": "2", "label": s}],
        "hero": {
            "title": s,
            "kicker": s,
            "taglines": [s, s + " " + s],
            "status": s,
            "meta": s,
            "nodes": [s, "b", "c"],
        },
        "marquee": [s, s],
        "chart": {"title": s, "values": [1, 3, 2], "labels": [s, s], "peak": s[:12], "unit": "%"},
        "bars": {"title": s, "items": [{"label": s, "value": 5}, {"label": s + s, "value": 50}]},
        "typing": {"title": s, "lines": [{"cmd": s + " " + s, "out": [s, s + s]}]},
    }[kind]


CASES = [(k, None) for k in KINDS] + [(k, s) for k in KINDS for s in HOSTILE]


def options(kind: str, text: str | None) -> dict[str, object]:
    return {} if text is None else {"title": text, "data": hostile_data(kind, text)}


def check(svg: str, theme: str = "both") -> None:
    """No findings at all, contrast as errors on the GitHub page(s) given; parses."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)


def root_of(svg: str) -> minidom.Element:
    return minidom.parseString(svg).documentElement


def font_sizes(svg: str) -> list[float]:
    """Every font size in the file: font-size attributes and CSS px values."""
    attrs = re.findall(r'font-size="([\d.]+)"', svg)
    css = re.findall(r"font-size:\s*([\d.]+)px", svg)
    return [float(v) for v in attrs + css]


def texts(svg: str) -> list[minidom.Element]:
    return list(root_of(svg).getElementsByTagName("text"))


def content(t: minidom.Element) -> str:
    return "".join(n.data for n in t.childNodes if n.nodeType == n.TEXT_NODE)


@pytest.mark.parametrize(("kind", "text"), CASES)
def test_phone_card_is_320_wide_with_phone_text(kind: str, text: str | None) -> None:
    svg = forge.render(kind, device="phone", **options(kind, text))

    root = root_of(svg)
    assert root.getAttribute("width") == "320"
    assert root.getAttribute("viewBox").split()[:3] == ["0", "0", "320"]
    sizes = font_sizes(svg)
    assert sizes and min(sizes) >= forge.PHONE_TEXT
    check(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert svg == forge.render(kind, device="phone", **options(kind, text))
    assert svg != forge.render(kind, **options(kind, text))
    if text is not None:
        assert "<script" not in svg
        assert "&lt;" in svg


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize(("kind", "text"), CASES)
def test_phone_pair_halves_pass_on_their_page(kind: str, text: str | None, theme: str) -> None:
    svg, _ = forge.build(kind, theme=theme, pair=True, device="phone", **options(kind, text))

    check(svg, theme)
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert min(font_sizes(svg)) >= forge.PHONE_TEXT


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("loop", [True, False])
def test_phone_card_keeps_its_motion(kind: str, loop: bool) -> None:
    svg = forge.render(kind, device="phone", loop=loop)

    check(svg)
    assert poster.problems(svg) == []
    assert "<animate" in svg
    assert ('repeatCount="indefinite"' in svg) is loop
    assert "prefers-reduced-motion" not in svg


def test_phone_tiles_take_two_columns_and_keep_values_whole() -> None:
    sample = forge.render("tiles", device="phone")
    wide = forge.render(
        "tiles",
        device="phone",
        data=[{"value": "$12,345,678.90", "label": "revenue"}, {"value": "7", "label": "x"}],
    )

    xs = {t.getAttribute("x") for t in texts(sample) if t.getAttribute("class").endswith("-b")}
    assert len(xs) == 2  # four tiles in two columns
    values = [t for t in texts(wide) if t.getAttribute("class").endswith("-b")]
    assert [content(t) for t in values] == ["$12,345,678.90", "7"]  # one column, nothing cut
    assert min(float(t.getAttribute("font-size")) for t in values) >= 18


def test_phone_tiles_and_bars_cap_long_lists_with_a_more_line() -> None:
    tiles = forge.render(
        "tiles", device="phone", data=[{"value": str(i), "label": f"m{i}"} for i in range(11)]
    )
    bars = forge.render(
        "bars", device="phone", data=[{"label": f"lang {i}", "value": i} for i in range(12)]
    )

    shown = [content(t) for t in texts(tiles)]
    assert "+3 MORE" in shown and "M7" in shown and "M8" not in shown
    shown = [content(t) for t in texts(bars)]
    assert "+4 MORE" in shown and "LANG 7" in shown and "LANG 8" not in shown
    check(tiles)
    check(bars)
    assert "m10" in root_of(tiles).getElementsByTagName("desc")[0].firstChild.data


def test_phone_hero_stacks_without_the_constellation() -> None:
    svg = forge.render("hero", device="phone")

    assert "<circle" in svg  # the status dot
    assert "CORE" not in svg  # node labels belong to the desktop constellation
    status = next(t for t in texts(svg) if content(t) == "BUILDING IN PUBLIC")
    meta = next(t for t in texts(svg) if content(t) == "MIT LICENSED")
    # its own row: below the pill, from the left margin rather than beside the pill
    assert float(meta.getAttribute("y")) > float(status.getAttribute("y"))
    assert float(meta.getAttribute("x")) < float(status.getAttribute("x"))


def test_phone_hero_wraps_a_long_title_instead_of_cutting_it() -> None:
    svg = forge.render("hero", device="phone", data={"title": "A much longer project title"})

    lines = [t for t in texts(svg) if t.getAttribute("class").endswith("-b")]
    assert " ".join(content(t) for t in lines) == "A much longer project title"
    assert len(lines) == 2


def test_phone_chart_labels_two_ticks_and_keeps_the_peak_inside() -> None:
    svg = forge.render("chart", device="phone", data={"values": [1, 2, 3, 50], "unit": "ms"})

    shown = [content(t) for t in texts(svg)]
    assert "1ms" in shown and "50ms" in shown and "25.5ms" not in shown
    assert overflow(svg) == []


def test_phone_typing_wraps_lines_and_grows_taller() -> None:
    cmd = "python forge.py --kind flow --timing long --data pipeline.json --out flow.svg"
    data = {"lines": [{"cmd": cmd, "out": ["wrote flow.svg with every node in place"]}]}
    svg = forge.render("typing", device="phone", data=data)
    short = forge.render("typing", device="phone", data={"lines": [{"cmd": "ls"}]})

    typed = [content(t) for t in texts(svg) if t.hasAttribute("clip-path")]
    assert " ".join(typed) == cmd
    assert forge.ELLIPSIS not in svg
    assert float(root_of(svg).getAttribute("height")) > float(root_of(short).getAttribute("height"))


def test_cli_device_both_theme_both_writes_four_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.svg"

    code = forge.main(["--kind", "bars", "--device", "both", "--theme", "both", "--out", str(out)])

    printed = capsys.readouterr().out
    assert code == 0
    files = {name: tmp_path / f"{name}.svg" for name in ("x-dark", "x-light")}
    files |= {f"{name}-mobile": tmp_path / f"{name}-mobile.svg" for name in ("x-dark", "x-light")}
    assert all(path.is_file() for path in files.values()) and not out.exists()
    assert printed.count("<source ") == 4
    assert f"(prefers-color-scheme: dark) and {forge.DESKTOP_MEDIA}" in printed
    assert 'media="(prefers-color-scheme: light)" srcset' in printed
    assert re.search(r'<img alt="[^"]*" src="[^"]*x-dark-mobile\.svg" width="100%">', printed)
    for name, path in files.items():
        svg = path.read_text(encoding="utf-8")
        check(svg, "light" if "light" in name else "dark")
        assert (root_of(svg).getAttribute("width") == "320") is name.endswith("mobile")
