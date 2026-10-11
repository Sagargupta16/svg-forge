"""optimize_svg.py: each safe operation, each never-rule, the refusal path, determinism, and a
round trip over every shipped SVG."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from xml.dom import minidom

import pytest

import optimize_svg
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "skills" / "animated-svg" / "assets" / "templates"
SHIPPED = sorted(TEMPLATES.glob("*.svg")) + sorted((ROOT / "examples").glob("*.svg"))
NS = 'xmlns="http://www.w3.org/2000/svg"'
INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"


def svg(body: str, root: str = "") -> str:
    return f'<svg {NS} viewBox="0 0 100 100" role="img" aria-label="x"{root}>{body}</svg>'


def opt(text: str, precision: int = 2) -> str:
    after, problems = optimize_svg.run(text.encode("utf-8"), precision)
    assert problems == []
    return after.decode("utf-8")


def path_d(d: str, precision: int = 2, extra: str = "") -> str:
    out = opt(svg(f'<path d="{d}"{extra}/>'), precision)
    return minidom.parseString(out).getElementsByTagName("path")[0].getAttribute("d")


def ids(text: str) -> set[str]:
    root = validate_svg.parse(text)
    return {i for n in root.iter() if (i := n.attr("id"))}


CHAIN = svg(
    '<rect id="a" width="10" height="10" opacity="0">'
    '<animate id="fade" attributeName="opacity" values="0;1" dur="1s" begin="0s;b.end"/></rect>'
    '<rect id="b" x="20" width="10" height="10">'
    '<animate attributeName="x" values="20;40" dur="1s" begin="a.end;fade.end"/></rect>'
)


# ---------------------------------------------------------------- safe operations


def test_drops_comments_outside_style() -> None:
    out = opt("<!-- exported -->" + svg('<!-- layer --><g><rect width="1" height="1"/></g>'))

    assert "<!--" not in out


def test_keeps_comments_inside_style() -> None:
    out = opt(svg("<style><!-- keep -->.a{fill:red}</style>"))

    assert "<style><!-- keep -->.a{fill:red}</style>" in out


def test_keeps_legal_comments() -> None:
    out = opt("<!--! Icon CC BY 4.0 -->" + svg('<rect width="1" height="1"/>'))

    assert out.startswith("<!--! Icon CC BY 4.0 --><svg")


def test_drops_metadata() -> None:
    rdf = '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'

    out = opt(svg(f'<metadata id="m1">{rdf}</metadata><rect width="1" height="1"/>'))

    assert "metadata" not in out and "rdf" not in out


def test_drops_editor_elements_attributes_and_declarations() -> None:
    body = '<sodipodi:namedview id="nv" inkscape:zoom="2"/><g inkscape:label="Layer 1"/>'
    root = f' xmlns:inkscape="{INKSCAPE}" xmlns:sodipodi="{SODIPODI}" inkscape:version="1.3"'

    out = opt(svg(body, root))

    assert "inkscape" not in out and "sodipodi" not in out


def test_keeps_an_editor_element_whose_id_is_referenced() -> None:
    body = '<sodipodi:namedview id="nv"/><use href="#nv"/>'

    out = opt(svg(body, f' xmlns:sodipodi="{SODIPODI}"'))

    assert '<sodipodi:namedview id="nv"/>' in out and f'xmlns:sodipodi="{SODIPODI}"' in out


def test_drops_illustrator_data_name() -> None:
    out = opt(svg('<g data-name="Layer 1" data-figma-id="3"><rect width="1" height="1"/></g>'))

    assert "data-" not in out


def test_keeps_data_attributes_that_css_selects() -> None:
    out = opt(svg('<style>[data-name="x"]{fill:red}</style><g data-name="x"/>'))

    assert '<g data-name="x"/>' in out


def test_drops_whitespace_between_tags() -> None:
    out = opt(svg('\n  <g>\n    <rect width="1" height="1"/>\n  </g>\n'))

    assert "\n" not in out.rstrip("\n")


def test_keeps_whitespace_inside_text() -> None:
    text = '<text x="1" y="5"><tspan>a</tspan> <tspan>b</tspan>  c </text>'

    assert text in opt(svg(f"\n{text}\n"))


def test_keeps_style_text_byte_identical() -> None:
    style = "<style>\n  .a { fill: red; }\n  .b>.c { opacity: 0.123456; }\n</style>"

    assert style in opt(svg(style))


def test_drops_defaults_only_when_certain() -> None:
    out = opt(svg('<rect x="0" y="0" width="1" height="1" opacity="1"/><circle cx="0" r="1"/>'))

    assert '<rect width="1" height="1"/><circle r="1"/>' in out


def test_keeps_values_that_inherit_or_position() -> None:
    body = '<g stroke-width="1" fill-opacity="1"><text x="0"><tspan x="0">a</tspan></text></g>'

    assert body in opt(svg(body))


def test_keeps_dash_character_references() -> None:
    out = opt(svg("<text>a &#8212; b</text>"))

    assert "a &#8212; b" in out and validate_svg.validate_text(out.encode()).errors == 0


# ---------------------------------------------------------------- rounding


def test_rounds_path_numbers_and_keeps_every_command() -> None:
    assert path_d("M10.12345 20.6789 L30.5 40.999 Z") == "M10.12 20.68 L30.5 41 Z"


def test_rounds_relative_path_against_the_rounded_pen() -> None:
    d = path_d("M0 0" + "l0.004 0" * 10)

    xs = [Decimal(segment.split()[0]) for segment in d.split("l")[1:]]
    assert len(xs) == 10 and sum(xs) == Decimal("0.04")


def test_keeps_arc_flags_when_rounding_the_next_number() -> None:
    assert path_d("M0 0a10 10 0 10.999.5") == "M0 0a10 10 0 10 1 .5"


def test_leaves_unparseable_path_data_alone() -> None:
    assert path_d("M1.23456 2 X 3") == "M1.23456 2 X 3"


def test_rounds_points_and_shape_geometry() -> None:
    body = '<polygon points="0.12345,1.98765 2.5,3"/><circle cx="1.23456" cy="5" r="2.0001"/>'

    out = opt(svg(body))

    assert '<polygon points="0.12,1.99 2.5,3"/><circle cx="1.23" cy="5" r="2"/>' in out


def test_rounds_translate_but_keeps_scale_and_matrix_factors() -> None:
    m = "matrix(0.707107 0.707107 -0.707107 0.707107 3.14159 2.71828)"

    out = opt(svg(f'<g transform="translate(10.12345 5) scale(0.123456) {m}"/>'))

    assert 'transform="translate(10.12 5) scale(0.123456) ' in out
    assert "matrix(0.707107 0.707107 -0.707107 0.707107 3.14 2.72)" in out


def test_never_rounds_viewbox() -> None:
    text = f'<svg {NS} viewBox="0 0 100.123456 50.5" role="img" aria-label="x"/>'

    assert 'viewBox="0 0 100.123456 50.5"' in opt(text)


@pytest.mark.parametrize(("precision", "expected"), [(0, "M1 3"), (3, "M1.235 2.988")])
def test_precision_sets_the_decimals(precision: int, expected: str) -> None:
    assert path_d("M1.23456 2.98765", precision) == expected


def test_keeps_dash_drawn_geometry_exact() -> None:
    d = "M0 0 L10.123456 0"

    assert path_d(d, extra=' stroke-dasharray="10.12"') == d


def test_rounds_a_dash_drawn_path_that_sets_path_length() -> None:
    extra = ' pathLength="1" stroke-dasharray="1"'

    assert path_d("M0 0 L10.123456 0", extra=extra) == "M0 0 L10.12 0"


def test_rounds_nothing_with_object_bounding_box_content_units() -> None:
    clip = '<clipPath id="c" clipPathUnits="objectBoundingBox"><rect width="0.123456"/></clipPath>'

    assert 'width="0.123456"' in opt(svg(clip + '<rect x="1.23456" clip-path="url(#c)"/>'))


# ---------------------------------------------------------------- never rules


def test_keeps_ids_chained_by_begin() -> None:
    out = opt(CHAIN)

    assert ids(out) == {"a", "b", "fade"}
    assert 'begin="0s;b.end"' in out and 'begin="a.end;fade.end"' in out


def test_keeps_href_and_url_targets() -> None:
    body = (
        '<defs><linearGradient id="g"><stop offset="0"/></linearGradient>'
        '<path id="x" d="M0 0H5"/></defs><use href="#x"/><rect fill="url(#g)" width="1"/>'
    )

    out = opt(svg(body))

    assert ids(out) == {"g", "x"} and 'href="#x"' in out and 'fill="url(#g)"' in out


def test_keeps_opacity_zero_fade_in_start_state() -> None:
    fade = '<animate attributeName="opacity" values="0;1" dur="1s" fill="freeze"/>'

    out = opt(svg(f'<rect width="10" height="10" opacity="0">{fade}</rect>'))

    assert f'<rect width="10" height="10" opacity="0">{fade}</rect>' in out


def test_keeps_animation_elements_byte_identical() -> None:
    anims = (
        '<animate attributeName="x" from="10.123456" to="0" dur="1.25s" keyTimes="0;0.123456;1"'
        ' values="0;5.55555;10" calcMode="spline" keySplines="0.42 0 0.58 1;0.123456 0 0.58 1"/>'
        '<animateTransform attributeName="transform" type="rotate" values="0 50.5555 50;360 50 50"'
        ' dur="2s" repeatCount="indefinite"/>'
        '<animateMotion path="M0.123456 0 L10.987654 0" dur="3s"/>'
        '<set attributeName="opacity" to="1" begin="1s"/>'
    )

    assert anims in opt(svg(f'<rect width="10" height="10">{anims}</rect>'))


def test_keeps_keyframes_byte_identical() -> None:
    css = "@keyframes spin{0%{transform:rotate(0.123456deg)}100%{transform:rotate(360deg)}}"

    assert f"<style>{css}.s{{animation:spin 1s infinite}}</style>" in opt(
        svg(f"<style>{css}.s{{animation:spin 1s infinite}}</style>")
    )


def test_keeps_group_structure() -> None:
    body = '<g transform="translate(1 1)"><g opacity="0.5"><rect width="1" height="1"/></g></g>'

    assert body in opt(svg(body))


# ---------------------------------------------------------------- verification and refusal


def test_verify_accepts_a_faithful_output() -> None:
    raw = CHAIN.encode()

    assert optimize_svg.verify(raw, optimize_svg.optimize(CHAIN).encode()) == []


def test_verify_flags_a_lost_id() -> None:
    after = CHAIN.replace(' id="fade"', "").replace("fade.end", "a.end")

    problems = optimize_svg.verify(CHAIN.encode(), after.encode())

    assert any(p.startswith("ids lost: fade") for p in problems)


def test_verify_flags_a_removed_animation() -> None:
    after = CHAIN.replace(
        '<animate attributeName="x" values="20;40" dur="1s" begin="a.end;fade.end"/>', ""
    )

    problems = optimize_svg.verify(CHAIN.encode(), after.encode())

    assert any(p.startswith("animation inventory changed") for p in problems)


def test_verify_flags_changed_animation_attributes() -> None:
    after = CHAIN.replace('values="20;40"', 'values="20;41"')

    assert optimize_svg.verify(CHAIN.encode(), after.encode()) == ["animate/set attributes changed"]


def test_verify_flags_changed_style_text() -> None:
    before = svg("<style>.a{fill:red}</style>")

    problems = optimize_svg.verify(before.encode(), before.replace("red", "blue").encode())

    assert problems == ["<style> text changed"]


def test_verify_flags_a_new_validator_error() -> None:
    after = CHAIN.replace(' role="img"', "")

    problems = optimize_svg.verify(CHAIN.encode(), after.encode())

    assert any(p.startswith("1 new SV010 error") for p in problems)


def test_verify_flags_unparseable_output() -> None:
    problems = optimize_svg.verify(CHAIN.encode(), b"<svg")

    assert problems[0].startswith("output does not parse")


def test_cli_refuses_and_writes_nothing_when_a_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src, out = tmp_path / "in.svg", tmp_path / "out.svg"
    src.write_text(CHAIN, encoding="utf-8")
    monkeypatch.setattr(optimize_svg, "optimize", lambda text, _p=2: text.replace(' id="b"', ""))

    code = optimize_svg.main([str(src), "--out", str(out)])

    assert code == 1 and not out.exists()
    assert "refused, nothing written: ids lost: b" in capsys.readouterr().err


def test_cli_refuses_input_that_does_not_parse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src, out = tmp_path / "in.svg", tmp_path / "out.svg"
    src.write_text('<!DOCTYPE svg [<!ENTITY a "b">]>' + svg(""), encoding="utf-8")

    code = optimize_svg.main([str(src), "--out", str(out)])

    assert code == 1 and not out.exists()
    assert "input does not parse" in capsys.readouterr().err


# ---------------------------------------------------------------- CLI


def write(tmp_path: Path, name: str = "in.svg", text: str = CHAIN) -> Path:
    path = tmp_path / name
    path.write_text("\n" + text.replace("><", ">\n<"), encoding="utf-8")
    return path


def test_cli_out_writes_the_file_and_reports_savings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src, out = write(tmp_path), tmp_path / "out.svg"

    code = optimize_svg.main([str(src), "--out", str(out)])

    before, after = src.stat().st_size, out.stat().st_size
    assert code == 0 and after < before
    assert f"{before} -> {after} bytes, " in capsys.readouterr().out


def test_cli_check_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = write(tmp_path)
    raw = src.read_bytes()

    code = optimize_svg.main([str(src), "--check"])

    assert code == 0 and src.read_bytes() == raw and list(tmp_path.iterdir()) == [src]
    assert "(check only, nothing written)" in capsys.readouterr().out


def test_cli_in_place_rewrites_the_input(tmp_path: Path) -> None:
    src = write(tmp_path)
    expected, _ = optimize_svg.run(src.read_bytes())

    assert optimize_svg.main([str(src), "--in-place"]) == 0
    assert src.read_bytes() == expected


def test_cli_out_folder_takes_several_files(tmp_path: Path) -> None:
    files = [write(tmp_path, "a.svg"), write(tmp_path, "b.svg")]

    code = optimize_svg.main([*map(str, files), "--out", str(tmp_path / "min")])

    assert code == 0 and sorted(p.name for p in (tmp_path / "min").iterdir()) == ["a.svg", "b.svg"]


def test_cli_needs_a_mode(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        optimize_svg.main([str(write(tmp_path))])

    assert exc.value.code == 2


def test_cli_rejects_negative_precision(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        optimize_svg.main([str(write(tmp_path)), "--check", "--precision", "-1"])

    assert exc.value.code == 2


# ---------------------------------------------------------------- determinism


def test_same_input_gives_same_lf_bytes() -> None:
    raw = ("\r\n" + CHAIN.replace("><", ">\r\n<")).encode()

    first, second = optimize_svg.run(raw)[0], optimize_svg.run(raw)[0]

    assert first == second and b"\r" not in first and first.endswith(b"</svg>\n")


def test_optimizing_twice_changes_nothing() -> None:
    once = opt("<!-- x -->\n" + CHAIN.replace("><", ">\n  <"))

    assert opt(once) == once


def test_cleans_an_inkscape_export() -> None:
    text = (
        f'<svg {NS} xmlns:inkscape="{INKSCAPE}" xmlns:sodipodi="{SODIPODI}" width="64.0000001"'
        ' viewBox="0 0 64 64" role="img" aria-labelledby="t" inkscape:version="1.3">\n'
        '  <title id="t">Pulse</title>\n  <sodipodi:namedview id="namedview7"/>\n'
        '  <metadata id="metadata5"/>\n  <g inkscape:label="Layer 1" id="layer1">\n'
        '    <circle id="dot" cx="32.123456" cy="32.987654" r="4" opacity="0">\n'
        '      <animate attributeName="opacity" values="0;1" dur="1s" begin="0s;dot.click"/>\n'
        "    </circle>\n  </g>\n</svg>\n"
    )

    out = opt(text)

    assert len(out) < 0.7 * len(text)
    assert ids(out) == {"t", "layer1", "dot"} and "inkscape" not in out
    assert '<circle id="dot" cx="32.12" cy="32.99" r="4" opacity="0">' in out


# ---------------------------------------------------------------- shipped files


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_shipped_svg_survives_a_round_trip(path: Path, tmp_path: Path) -> None:
    out = tmp_path / path.name

    assert optimize_svg.main([str(path), "--out", str(out)]) == 0

    before, after = path.read_text(encoding="utf-8"), out.read_text(encoding="utf-8")
    assert validate_svg.validate_file(out).errors == 0
    minidom.parseString(after)
    assert ids(after) == ids(before)
    old, new = validate_svg.parse(before), validate_svg.parse(after)
    assert optimize_svg.inventory(new) == optimize_svg.inventory(old)


def test_shipped_svgs_get_smaller_in_total(tmp_path: Path) -> None:
    before = sum(p.stat().st_size for p in SHIPPED)

    assert optimize_svg.main([*map(str, SHIPPED), "--out", str(tmp_path)]) == 0

    assert sum(p.stat().st_size for p in tmp_path.iterdir()) < before
