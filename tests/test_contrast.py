"""validate_svg.py contrast rules SV021-SV023: WCAG math, color resolution, backgrounds, CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import validate_svg

NS = 'xmlns="http://www.w3.org/2000/svg"'
WHITE_CANVAS = '<rect width="200" height="100" fill="#ffffff"/>'
BLACK_CANVAS = '<rect width="200" height="100" fill="#000000"/>'


def svg(body: str) -> str:
    return f'<svg {NS} viewBox="0 0 200 100" role="img" aria-label="Card">{body}</svg>'


def text(attrs: str = "", content: str = "Hi") -> str:
    return f'<text x="10" y="50" {attrs}>{content}</text>'


def check(body: str, **kw: str) -> validate_svg.Report:
    return validate_svg.validate_text(svg(body).encode("utf-8"), contrast="warn", **kw)


def rules(body: str, **kw: str) -> set[tuple[str, str]]:
    return {(f.rule, f.severity) for f in check(body, **kw).findings}


def entries(body: str, **kw: str) -> list[dict[str, object]]:
    return check(body, **kw).stats["contrast"]  # type: ignore[return-value]


def color(value: str) -> validate_svg.Color:
    parsed = validate_svg.parse_color(value)
    assert parsed is not None
    return parsed


# WCAG math


def test_gray_777_on_white_is_just_under_aa() -> None:
    ratio = validate_svg.contrast_ratio(color("#777"), color("#fff"))

    assert ratio == pytest.approx(4.48, abs=0.01)
    assert ratio < 4.5


def test_black_on_white_is_21() -> None:
    assert validate_svg.contrast_ratio(color("black"), color("white")) == pytest.approx(21.0)


def test_alpha_composites_over_the_background() -> None:
    shown = validate_svg.over(color("rgba(0,0,0,0.5)"), color("#ffffff"))

    assert validate_svg.hex_color(shown) == "#808080"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#f00", (1.0, 0.0, 0.0, 1.0)),
        ("#f008", (1.0, 0.0, 0.0, 0x88 / 255)),
        ("#00ff00", (0.0, 1.0, 0.0, 1.0)),
        ("#0000ff80", (0.0, 0.0, 1.0, 0x80 / 255)),
        ("rgb(255, 0, 0)", (1.0, 0.0, 0.0, 1.0)),
        ("rgba(0,0,255,0.25)", (0.0, 0.0, 1.0, 0.25)),
        ("rgb(100% 0% 0% / 50%)", (1.0, 0.0, 0.0, 0.5)),
        ("hsl(0, 100%, 50%)", (1.0, 0.0, 0.0, 1.0)),
        ("hsla(120, 100%, 25%, 0.5)", (0.0, 0.5, 0.0, 0.5)),
        ("Grey", (128 / 255, 128 / 255, 128 / 255, 1.0)),
        ("transparent", (0.0, 0.0, 0.0, 0.0)),
    ],
)
def test_color_syntaxes(value: str, expected: validate_svg.Color) -> None:
    assert color(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["#12", "rgb(1, 2)", "notacolor", "url(#g)", "var(--fg)"])
def test_unreadable_colors_are_none(value: str) -> None:
    assert validate_svg.parse_color(value) is None


def test_path_rings_follow_relative_commands_and_compact_arc_flags() -> None:
    assert validate_svg.path_rings("M10 10 h20 v20 h-20 z") == [
        [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0), (10.0, 30.0)]
    ]
    assert validate_svg.path_rings("M0 0a5 5 0 0110 10") == [[(0.0, 0.0), (10.0, 10.0)]]


# colors on elements


def test_low_contrast_text_on_the_canvas_warns() -> None:
    assert ("SV021", "warn") in rules(WHITE_CANVAS + text('fill="#cccccc"'))


def test_readable_text_has_no_finding() -> None:
    assert rules(WHITE_CANVAS + text('fill="#595959"')) == set()


@pytest.mark.parametrize(
    "attrs", ['fill="#ffffff" fill-opacity="0.5"', 'fill="rgba(255,255,255,0.5)"']
)
def test_text_alpha_is_composited_over_its_background(attrs: str) -> None:
    (entry,) = entries(BLACK_CANVAS + text(attrs))

    assert entry["shown"] == "#808080"
    assert entry["background"] == "#000000"


def test_group_opacity_multiplies_into_the_text() -> None:
    (entry,) = entries(BLACK_CANVAS + f'<g opacity="0.5">{text('fill="#ffffff"')}</g>')

    assert entry["shown"] == "#808080"


def test_fill_is_inherited_from_ancestors() -> None:
    (entry,) = entries(WHITE_CANVAS + f'<g fill="#cccccc"><g>{text()}</g></g>')

    assert entry["color"] == "#cccccc"
    assert entry["pass"] is False


def test_current_color_resolves_the_color_property() -> None:
    (entry,) = entries(WHITE_CANVAS + f'<g color="#cccccc">{text('fill="currentColor"')}</g>')

    assert entry["color"] == "#cccccc"


def test_style_rule_beats_the_presentation_attribute() -> None:
    body = "<style>.t{fill:#cccccc}</style>" + WHITE_CANVAS + text('class="t" fill="#000000"')

    assert ("SV021", "warn") in rules(body)


def test_inline_style_beats_a_style_rule() -> None:
    css = "<style>text.t{fill:#cccccc}</style>"
    body = css + WHITE_CANVAS + text('class="t" style="fill:#000000"')

    assert rules(body) == set()


def test_tspan_is_checked_with_its_own_fill() -> None:
    body = WHITE_CANVAS + text('fill="#000000"', 'A<tspan fill="#cccccc">B</tspan>')

    assert {e["text"]: e["pass"] for e in entries(body)} == {"A": True, "B": False}


def test_unreadable_fill_is_an_info_note() -> None:
    assert rules(WHITE_CANVAS + text('fill="var(--fg)"')) == {("SV021", "info")}


# backgrounds


def test_full_canvas_background_is_the_only_one_tested() -> None:
    (entry,) = entries(WHITE_CANVAS + text('fill="#0d1117"'))

    assert entry["against"] == "canvas <rect> line 1"
    assert entry["pass"] is True


def test_text_without_background_is_tested_on_both_github_themes() -> None:
    found = entries(text('fill="#0d1117"'))

    assert [(e["against"], e["pass"]) for e in found] == [
        ("github-dark", False),
        ("github-light", True),
    ]
    assert ("SV022", "warn") in rules(text('fill="#0d1117"'))


def test_theme_option_tests_one_github_theme() -> None:
    found = entries(text('fill="#0d1117"'), theme="light")

    assert [e["against"] for e in found] == ["github-light"]
    assert rules(text('fill="#0d1117"'), theme="light") == set()


def test_opaque_card_under_text_replaces_the_page() -> None:
    card = '<rect width="100" height="100" fill="#ffffff"/>'

    (entry,) = entries(card + text('fill="#0d1117"'))

    assert entry["against"] == "<rect> line 1"


def test_text_beside_the_card_still_meets_the_page() -> None:
    card = '<rect width="100" height="100" fill="#ffffff"/>'

    found = entries(card + '<text x="150" y="50" fill="#0d1117">Hi</text>')

    assert {e["against"] for e in found} == {"github-dark", "github-light"}


def test_filled_path_counts_as_a_background() -> None:
    shape = '<path d="M0 0 H100 V100 H0 Z" fill="#ffffff"/>'

    (entry,) = entries(shape + text('fill="#0d1117"'))

    assert entry["against"] == "<path> line 1"


def test_transform_moves_text_onto_the_card() -> None:
    card = '<rect x="100" width="100" height="100" fill="#ffffff"/>'
    moved = f'<g transform="translate(100 0)">{text('fill="#0d1117"')}</g>'

    (entry,) = entries(card + moved)

    assert entry["against"] == "<rect> line 1"


def test_translucent_layer_tints_the_background() -> None:
    tint = '<rect width="200" height="100" fill="rgba(0,0,0,0.5)"/>'

    (entry,) = entries(WHITE_CANVAS + tint + text('fill="#000000"'))

    assert entry["background"] == "#808080"
    assert entry["tint"] == "<rect> line 1"


def test_gradient_background_uses_its_worst_stop() -> None:
    grad = (
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#ffffff"/>'
        '<stop offset="1" stop-color="#cccccc"/></linearGradient></defs>'
        '<rect width="200" height="100" fill="url(#g)"/>'
    )

    (entry,) = entries(grad + text('fill="#777777"'))

    assert entry["background"] == "#cccccc"
    assert entry["ratio"] == pytest.approx(2.78, abs=0.01)


def test_text_on_an_image_is_an_info_note() -> None:
    image = '<image href="data:image/png;base64,AAAA" width="200" height="100"/>'

    assert rules(image + text('fill="#cccccc"')) == {("SV021", "info")}


# what counts as visible text


@pytest.mark.parametrize(
    ("size", "weight", "passes"),
    [("23", "normal", False), ("24", "normal", True), ("19", "bold", True), ("18", "700", False)],
)
def test_large_text_needs_only_three_to_one(size: str, weight: str, passes: bool) -> None:
    (entry,) = entries(
        WHITE_CANVAS + text(f'fill="#888888" font-size="{size}" font-weight="{weight}"')
    )

    assert entry["required"] == (3.0 if passes else 4.5)
    assert entry["pass"] is passes


def test_text_that_fades_in_is_tested_at_its_peak_opacity() -> None:
    fade = '<animate attributeName="opacity" values="0;1" dur="1s" fill="freeze"/>'

    (entry,) = entries(WHITE_CANVAS + text('fill="#cccccc" opacity="0"', f"Hi{fade}"))

    assert entry["shown"] == "#cccccc"


def test_css_fade_in_counts_as_an_animation() -> None:
    css = "<style>.f{opacity:0;animation:in 1s forwards}@keyframes in{to{opacity:1}}</style>"

    assert len(entries(css + WHITE_CANVAS + text('class="f" fill="#cccccc"'))) == 1


def test_invisible_text_without_animation_is_skipped() -> None:
    assert entries(WHITE_CANVAS + text('fill="#cccccc" opacity="0"')) == []


def test_unreadable_fade_is_tested_at_full_opacity_with_a_note() -> None:
    fade = '<animate attributeName="opacity" by="1" dur="1s"/>'

    found = rules(WHITE_CANVAS + text('fill="#cccccc" opacity="0"', f"Hi{fade}"))

    assert found == {("SV021", "warn"), ("SV021", "info")}


@pytest.mark.parametrize(
    "body", [f"<defs>{text('fill="#cccccc"')}</defs>", text('fill="#cccccc" display="none"')]
)
def test_unrendered_text_is_skipped(body: str) -> None:
    assert entries(WHITE_CANVAS + body) == []


# graphics


def test_solid_graphic_below_three_to_one_warns() -> None:
    found = rules('<circle cx="50" cy="50" r="10" fill="#60a5fa"/>')

    assert found == {("SV023", "warn")}


def test_translucent_graphic_counts_as_decoration() -> None:
    assert entries('<circle cx="50" cy="50" r="10" fill="rgba(96,165,250,0.3)"/>') == []


def test_shape_under_text_is_a_surface_not_a_graphic() -> None:
    body = '<rect width="100" height="100" fill="#0d1117"/>' + text('fill="#ffffff"')

    assert [e["kind"] for e in entries(body)] == ["text"]


def test_default_black_shapes_get_one_info_note() -> None:
    body = '<rect x="10" y="10" width="5" height="5"/><rect x="30" y="10" width="5" height="5"/>'

    assert rules(body) == {("SV023", "info")}


# rules, API and CLI

FIRES = {
    "SV021": WHITE_CANVAS + text('fill="#cccccc"'),
    "SV022": text('fill="#0d1117"'),
    "SV023": '<circle cx="50" cy="50" r="10" fill="#0d1117"/>',
}


def test_every_contrast_rule_has_a_fixture() -> None:
    assert set(FIRES) == set(validate_svg.CONTRAST_RULES)


@pytest.mark.parametrize("rule", sorted(FIRES))
def test_contrast_rule_fires(rule: str) -> None:
    assert (rule, "warn") in rules(FIRES[rule])


def test_strict_contrast_turns_warnings_into_errors() -> None:
    report = validate_svg.validate_text(svg(FIRES["SV022"]).encode(), contrast="error")

    assert {(f.rule, f.severity) for f in report.findings} == {("SV022", "error")}


def test_api_leaves_contrast_off_by_default() -> None:
    report = validate_svg.validate_text(svg(FIRES["SV022"]).encode())

    assert report.findings == []
    assert "contrast" not in report.stats


def test_cli_strict_contrast_exit_code(tmp_path: Path) -> None:
    path = tmp_path / "dark-text.svg"
    path.write_text(svg(FIRES["SV022"]), encoding="utf-8")

    assert validate_svg.main([str(path)]) == 0
    assert validate_svg.main([str(path), "--strict-contrast"]) == 1


def test_cli_json_reports_ratio_colors_and_background(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "dark-text.svg"
    path.write_text(svg(FIRES["SV022"]), encoding="utf-8")

    assert validate_svg.main([str(path), "--json"]) == 0

    (result,) = json.loads(capsys.readouterr().out)
    dark = result["stats"]["contrast"][0]
    assert set(dark) == {
        "kind",
        "line",
        "element",
        "text",
        "paint",
        "value",
        "color",
        "shown",
        "background",
        "against",
        "tint",
        "ratio",
        "required",
        "font_px",
        "bold",
        "large",
        "pass",
    }
    assert (dark["against"], dark["background"], dark["color"]) == (
        "github-dark",
        "#0d1117",
        "#0d1117",
    )
    assert dark["ratio"] == 1.0
    assert result["findings"][0]["rule"] == "SV022"
