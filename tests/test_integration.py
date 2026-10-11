"""forge.py with themes.py and sizes.py: --theme, --mode, --accent and --size for every kind."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.dom import minidom

import pytest
import sizes
import themes

import forge
import poster
import validate_svg

PRESET_SIZES = ["icon-128", "card", "readme", "og", "linkedin-banner"]
FACES = {
    "m": ("mono", forge.MONO_LS),
    "s": ("sans", 0.0),
    "r": ("sans", 0.0),
    "b": ("bold", 0.0),
    "t": ("mono", 0.0),
}


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the given GitHub page(s); parses."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def root_of(svg: str) -> minidom.Element:
    return minidom.parseString(svg).documentElement


def shift(node: minidom.Element) -> tuple[float, float, bool]:
    """Static translate() of the node's ancestors, and whether any of them clips."""
    dx = dy = 0.0
    clipped = False
    while node is not None and node.nodeType == node.ELEMENT_NODE:
        clipped = clipped or node.hasAttribute("clip-path") or node.tagName == "defs"
        m = re.fullmatch(r"translate\(([-\d.]+)[ ,]+([-\d.]+)\)", node.getAttribute("transform"))
        if m:
            dx, dy = dx + float(m.group(1)), dy + float(m.group(2))
        node = node.parentNode
    return dx, dy, clipped


def overflow(svg: str) -> list[str]:
    """Text whose estimated box leaves the viewBox (clipped strips excepted)."""
    root = root_of(svg)
    vx, vy, vw, vh = (float(v) for v in root.getAttribute("viewBox").split())
    out = []
    for t in root.getElementsByTagName("text"):
        dx, dy, clipped = shift(t)
        if clipped:
            continue
        face, spacing = FACES[t.getAttribute("class").rsplit("-", 1)[-1]]
        size = float(t.getAttribute("font-size") or 13)
        text = "".join(n.data for n in t.childNodes if n.nodeType == n.TEXT_NODE)
        width = forge.text_width(text, size, face, spacing)
        anchor = {"start": 0.0, "middle": 0.5, "end": 1.0}[t.getAttribute("text-anchor") or "start"]
        left = float(t.getAttribute("x")) + dx - width * anchor
        y = float(t.getAttribute("y")) + dy
        if (
            left < vx - 0.5
            or left + width > vx + vw + 0.5
            or y - 0.75 * size < vy - 0.5
            or y + 0.25 * size > vy + vh + 0.5
        ):
            out.append(f"{text!r} spans x {left:.1f}..{left + width:.1f}, y {y:.1f}")
    return out


def expected_size(kind: str, preset: str, theme: str) -> tuple[str, str]:
    default = root_of(forge.render(kind, theme=theme))
    bw, bh = float(default.getAttribute("width")), float(default.getAttribute("height"))
    spec = sizes.SIZES[preset]
    if spec.height is not None:
        return str(spec.width), str(spec.height)
    # width-only: the kind's aspect, at least the 16 px minimum side
    return str(spec.width), str(max(round(spec.width * bh / bw), sizes.MIN_SIDE))


# ---------------------------------------------------------------- --size for every kind


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("preset", PRESET_SIZES)
@pytest.mark.parametrize("kind", list(forge.KINDS))
def test_every_kind_fits_any_size_preset(kind: str, preset: str, theme: str) -> None:
    svg = forge.render(kind, theme=theme, size=preset)

    check(svg)
    root = root_of(svg)
    assert (root.getAttribute("width"), root.getAttribute("height")) == expected_size(
        kind, preset, theme
    )
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert svg == forge.render(kind, theme=theme, size=preset)


@pytest.mark.parametrize("kind", [k for k, v in forge.KINDS.items() if v.sizing == "scaled"])
def test_scaled_kind_keeps_its_aspect_inside_the_canvas(kind: str) -> None:
    root = root_of(forge.render(kind, size="og"))

    box = [float(v) for v in root.getAttribute("viewBox").split()]
    assert root.getAttribute("preserveAspectRatio") == "xMidYMid meet"
    assert box[2] / box[3] == pytest.approx(1280 / 640, rel=1e-3)  # never stretched


@pytest.mark.parametrize("kind", ["timeline", "logos", "calendar", "ring"])
def test_native_kind_lays_out_at_the_canvas(kind: str) -> None:
    root = root_of(forge.render(kind, size="1000x500"))

    assert root.getAttribute("viewBox") == "0 0 1000 500"
    assert not root.hasAttribute("preserveAspectRatio")


def test_letterbox_takes_the_theme_bg_on_framed_kinds_only() -> None:
    bars = forge.render("bars", size="og")  # rows keep their height: margin above and below
    badge = forge.render("badge", size="icon-128")

    box = root_of(bars).getAttribute("viewBox").split()
    assert float(box[1]) < 0
    assert re.search(rf'<rect x="-1" y="{float(box[1]) - 1:g}"[^>]*fill="#0b1012"/>', bars)
    assert 'fill="#0b1012"' not in badge  # the margin around the pill stays transparent


def test_size_equal_to_the_default_is_a_plain_scale() -> None:
    svg = forge.render("bars", size="600")

    root = root_of(svg)
    assert root.getAttribute("width") == "600"
    assert root.getAttribute("viewBox").startswith("0 0 600 ")


def test_thin_kind_takes_a_width_only_size() -> None:
    root = root_of(forge.render("divider", size="readme"))

    assert root.getAttribute("width") == "880"
    assert int(root.getAttribute("height")) >= sizes.MIN_SIDE


@pytest.mark.parametrize("spec", ["huge", "10x10", "5000"])
def test_bad_size_is_a_forge_error(spec: str) -> None:
    with pytest.raises(forge.ForgeError, match="--size"):
        forge.render("tiles", size=spec)


def test_size_and_width_together_are_refused() -> None:
    with pytest.raises(forge.ForgeError, match="--size"):
        forge.render("tiles", size="og", width=400)


# ---------------------------------------------------------------- --theme and --mode


@pytest.mark.parametrize("spec", [*themes.list_themes(), "auto:#ff6b6b", "#0ea5e9"])
@pytest.mark.parametrize("kind", ["hero", "flow", "calendar", "badge", "divider"])
def test_every_theme_reads_on_its_page(kind: str, spec: str) -> None:
    theme = forge.load_theme(spec)[0]
    page = theme.mode if theme.transparent else "both"

    check(forge.render(kind, theme=spec), page)


def test_mode_picks_the_light_variant_of_a_family() -> None:
    latte = forge.load_theme("catppuccin-mocha", None, "light")[0]

    assert latte.name == "catppuccin-latte" and not forge.is_dark(latte)
    assert forge.load_theme("solarized", None, "light")[0].name == "solarized-light"
    assert forge.load_theme("github")[0] == forge.THEMES["dark"]


def test_theme_accent_applies_unless_accent_is_given() -> None:
    nord = forge.render("chart", theme="nord")
    pink = forge.render("chart", theme="nord", accent="#f472b6")

    assert "#88c0d0" in nord  # the preset's own accent
    assert "#f472b6" in pink and "#88c0d0" not in pink


def test_transparent_theme_paints_no_background() -> None:
    svg = forge.render("tiles", theme="transparent-dark")

    assert '<rect x="0.5" y="0.5"' in svg
    frame = re.search(r'<rect x="0.5" y="0.5"[^>]*>', svg).group(0)
    assert 'fill="none"' in frame and "stroke=" in frame
    assert "linearGradient" not in svg


def test_palette_file_theme(tmp_path: Path) -> None:
    path = tmp_path / "brand.json"
    path.write_text(json.dumps({"extends": "nord", "accent": "#ebcb8b"}), encoding="utf-8")

    svg = forge.render("ring", theme=str(path))

    check(svg)
    assert "#ebcb8b" in svg


def test_unknown_theme_is_a_forge_error() -> None:
    with pytest.raises(forge.ForgeError, match="unknown theme"):
        forge.render("badge", theme="neon")


def test_bare_kind_in_a_pair_keeps_the_theme_ink() -> None:
    single = forge.render("divider")
    half = forge.render("divider", pair=True)

    assert "#60a5fa" in half and "#60a5fa" not in single
    check(single)
    check(half, "dark")


# ---------------------------------------------------------------- CLI


def test_cli_mode_both_writes_the_family_pair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cal.svg"

    code = forge.main(
        ["--kind", "calendar", "--theme", "catppuccin", "--mode", "both", "--out", str(out)]
    )

    assert code == 0
    dark, light = tmp_path / "cal-dark.svg", tmp_path / "cal-light.svg"
    check(dark.read_text(encoding="utf-8"), "dark")
    check(light.read_text(encoding="utf-8"), "light")
    assert "#1e1e2e" in dark.read_text(encoding="utf-8")  # mocha base
    assert "#eff1f5" in light.read_text(encoding="utf-8")  # latte base
    assert "<picture>" in capsys.readouterr().out


def test_cli_auto_brand_theme_in_both_modes(tmp_path: Path) -> None:
    out = tmp_path / "hero.svg"

    assert (
        forge.main(
            ["--kind", "hero", "--theme", "auto:#ff6b6b", "--mode", "both", "--out", str(out)]
        )
        == 0
    )

    assert (tmp_path / "hero-dark.svg").is_file() and (tmp_path / "hero-light.svg").is_file()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--theme", "nord", "--mode", "light"], "no light variant"),
        (["--theme", "nord", "--mode", "both", "--out", "x.svg"], "no light variant"),
        (["--theme", "dark", "--mode", "light"], "disagree"),
        (["--theme", "both", "--mode", "dark"], "drop --mode"),
        (["--mode", "both"], "needs --out"),
        (["--theme", "neon"], "unknown theme"),
        (["--size", "tiny"], "unknown size"),
        (["--size", "og", "--width", "300"], "--size sets the canvas"),
    ],
)
def test_cli_impossible_combos_exit_2(
    argv: list[str], message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [a if a != "x.svg" else str(tmp_path / a) for a in argv]

    assert forge.main(["--kind", "badge", *argv]) == 2
    assert message in capsys.readouterr().err


def test_cli_prints_adjustment_notes_to_stderr(capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    assert forge.main(["--kind", "loader"]) == 0

    captured = capsysbinary.readouterr()
    assert b"note: accent #60a5fa ->" in captured.err
    assert captured.out.startswith(b"<svg")


def test_cli_size_preset(tmp_path: Path) -> None:
    out = tmp_path / "og.svg"

    assert forge.main(["--kind", "flow", "--size", "og", "--out", str(out)]) == 0

    root = root_of(out.read_text(encoding="utf-8"))
    assert (root.getAttribute("width"), root.getAttribute("height")) == ("1280", "640")


def test_help_names_each_kinds_size_mode() -> None:
    text = forge.build_parser().format_help()

    for kind, spec in forge.KINDS.items():
        assert re.search(rf"^  {kind}\s.*--size {spec.sizing}\)$", text, re.M), kind


# ---------------------------------------------------------------- themes helpers


def test_ensure_contrast_all_meets_each_minimum() -> None:
    color = themes.ensure_contrast_all("#60a5fa", [("#0d1117", 3.0), ("#ffffff", 3.0)])

    assert themes.contrast(color, "#0d1117") >= 3 and themes.contrast(color, "#ffffff") >= 3


def test_ensure_contrast_all_raises_when_no_lightness_fits() -> None:
    with pytest.raises(themes.ThemeError):
        themes.ensure_contrast_all("#888888", [("#0d1117", 4.5), ("#ffffff", 4.5)])


def test_fractional_rgb_parses() -> None:
    assert themes.parse_color("rgb(216.6, 0, 1.5)") == (216.6, 0.0, 1.5, 1.0)
