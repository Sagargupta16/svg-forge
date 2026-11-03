"""forge.py banner and heading: every variant and section, pairs, phone layouts, bad data."""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path
from xml.dom import minidom

import pytest

import forge
import poster
import validate_svg
from test_integration import overflow

VARIANTS = list(forge.BANNER_SHAPES)
SECTIONS = ["header", "footer"]
FOOTER = {
    "section": "footer",
    "kicker": "Thanks for reading",
    "lines": ["Built in the open.", "Issues and pull requests welcome."],
}
HEADER = {
    "kicker": "Open source",
    "title": "Northwind",
    "subtitle": "Inventory for small shops",
    "lines": ["Works offline", "MIT licensed"],
    "section": "header",
}
TIMINGS = ["long", "medium", "short", "ambient"]
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the GitHub page(s) the file is shown on (both
    for a single file, its own page for one half of a pair); parses; text inside the canvas;
    the static frame shows the finished state."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    return report


def banner_data(section: str) -> dict[str, object]:
    return FOOTER if section == "footer" else HEADER


def font_sizes(svg: str) -> list[float]:
    return [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]


def root_size(svg: str) -> tuple[str, str]:
    root = minidom.parseString(svg).documentElement
    return root.getAttribute("width"), root.getAttribute("height")


def cli(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return forge.main(argv)


# ---------------------------------------------------------------- banner


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("timing", TIMINGS)
def test_banner_variant_and_section_validate(
    variant: str, section: str, theme: str, timing: str
) -> None:
    options = {"variant": variant, "theme": theme, "timing": timing, "data": banner_data(section)}

    svg = forge.render("banner", **options)

    check(svg)
    assert svg == forge.render("banner", **options)
    assert svg.endswith("</svg>\n") and "\r" not in svg


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("loop", [True, False])
def test_banner_loop_and_once(variant: str, loop: bool) -> None:
    svg = forge.render("banner", variant=variant, loop=loop)

    check(svg)
    assert ('repeatCount="indefinite"' in svg) is loop


@pytest.mark.parametrize("section", SECTIONS)
def test_banner_default_heights(section: str) -> None:
    svg = forge.render("banner", data=banner_data(section))

    assert root_size(svg) == ("840", "150" if section == "footer" else "160")


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_banner_pair_half_reads_on_its_page(variant: str, theme: str) -> None:
    check(forge.render("banner", variant=variant, theme=theme, pair=True), theme)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("section", SECTIONS)
def test_banner_phone_layout(variant: str, section: str) -> None:
    svg = forge.render("banner", variant=variant, device="phone", data=banner_data(section))

    check(svg)
    assert root_size(svg)[0] == "320"
    assert min(font_sizes(svg)) >= forge.PHONE_TEXT


def test_banner_phone_wraps_a_long_title_and_subtitle() -> None:
    data = {
        "title": "Northwind inventory platform",
        "subtitle": "Realtime stock for small shops, offline first",
    }

    svg = forge.render("banner", device="phone", data=data)

    check(svg)
    texts = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
    assert len(texts) == 4  # two title rows and two subtitle rows
    assert forge.ELLIPSIS not in "".join(texts)
    assert float(root_size(svg)[1]) > 160  # the canvas grows instead of cutting text


def test_banner_lines_take_turns_on_one_clock() -> None:
    svg = forge.render("banner", data=HEADER)

    # the subtitle leads the two lines: three texts share one position
    tails = re.findall(r'<text class="[\w-]+-s"[^>]*>', svg)
    spots = {(re.search(r' x="([\d.]+)"', t)[1], re.search(r' y="([\d.]+)"', t)[1]) for t in tails}
    assert len(tails) == 3 and len(spots) == 1 and next(iter(spots))[0] == "420"
    assert svg.count('opacity="0"') == 2  # the static frame shows only the first


def test_banner_footer_without_title_rotates_the_lines_in_the_title_place() -> None:
    svg = forge.render("banner", data=FOOTER)

    assert len(re.findall(r'<text class="[\w-]+-b"', svg)) == 2
    assert "THANKS FOR READING" in svg


@pytest.mark.parametrize("size", ["icon-128", "card", "readme", "og", "linkedin-banner"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_banner_lays_out_at_any_size(size: str, variant: str) -> None:
    check(forge.render("banner", variant=variant, size=size))


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("text", HOSTILE)
def test_banner_hostile_text_is_escaped(variant: str, text: str) -> None:
    data = {"kicker": text, "title": text, "subtitle": text, "lines": [text], "section": "footer"}

    svg = forge.render("banner", variant=variant, title=text, data=data)

    check(svg)
    assert "<script" not in svg and "&lt;" in svg


@pytest.mark.parametrize(
    ("data", "variant"),
    [
        ({"title": "x", "section": "side"}, None),
        ({"lines": "not a list"}, None),
        ({"lines": ["a"] * 7}, None),
        ({}, None),
        ({"title": ["x"]}, None),
        (5, None),
        ({"title": "x"}, "zigzag"),
    ],
)
def test_banner_bad_data_is_rejected(data: object, variant: str | None) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("banner", data=data, variant=variant)


def test_banner_unknown_variant_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert forge.main(["--kind", "banner", "--variant", "zigzag"]) == 2
    assert "banner variant" in capsys.readouterr().err


# ---------------------------------------------------------------- heading


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("timing", ["medium", "short", "long", "ambient", "micro"])
@pytest.mark.parametrize("loop", [None, True, False])
def test_heading_validates(theme: str, timing: str, loop: bool | None) -> None:
    svg = forge.render("heading", theme=theme, timing=timing, loop=loop)

    check(svg)
    assert svg == forge.render("heading", theme=theme, timing=timing, loop=loop)


def test_heading_default_size_and_full_canvas_without_border() -> None:
    svg = forge.render("heading")

    assert root_size(svg) == ("840", "64")
    assert '<rect width="840" height="64" fill="#0b1012"/>' in svg
    assert "01 / BUILT IN THE OPEN" in svg and "Featured projects" in svg


def test_heading_takes_a_bare_title_and_pads_a_number() -> None:
    bare = forge.render("heading", data="Release notes")
    numbered = forge.render("heading", data={"number": 3, "title": "Roadmap"})

    assert "Release notes" in bare and " / " not in bare
    assert ">03</text>" in numbered


def test_heading_title_alone_replaces_the_sample() -> None:
    svg = forge.render("heading", title="Roadmap")

    assert "Roadmap" in svg and "BUILT IN THE OPEN" not in svg


def test_heading_pair_and_phone_set_from_the_cli(tmp_path: Path) -> None:
    out = tmp_path / "section.svg"
    data = '{"number": "02", "title": "Release notes and roadmap", "subtitle": "What shipped"}'

    code = cli(
        [
            "--kind",
            "heading",
            "--theme",
            "both",
            "--device",
            "both",
            "--data",
            data,
            "--out",
            str(out),
        ]
    )

    assert code == 0
    for theme in ("dark", "light"):
        for suffix in ("", "-mobile"):
            svg = (tmp_path / f"section-{theme}{suffix}.svg").read_text(encoding="utf-8")
            check(svg, theme)
            if suffix:
                assert root_size(svg)[0] == "320"
                assert min(font_sizes(svg)) >= forge.PHONE_TEXT
    phone = (tmp_path / "section-dark-mobile.svg").read_text(encoding="utf-8")
    assert len(re.findall(r'<text class="[\w-]+-b"', phone)) == 2  # the title wraps


@pytest.mark.parametrize("size", ["icon-128", "card", "readme", "og", "linkedin-banner"])
def test_heading_lays_out_at_any_size(size: str) -> None:
    check(forge.render("heading", size=size))


@pytest.mark.parametrize("text", HOSTILE)
def test_heading_hostile_text_is_escaped(text: str) -> None:
    svg = forge.render("heading", title=text, data={"number": text, "subtitle": text})

    check(svg)
    assert "<script" not in svg and "&lt;" in svg


@pytest.mark.parametrize("data", [{}, {"title": ""}, 5, ["a"], {"title": "x", "number": [1]}])
def test_heading_bad_data_is_rejected(data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render("heading", data=data)


def test_heading_bad_data_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert forge.main(["--kind", "heading", "--data", "{}"]) == 2
    assert "heading needs a title" in capsys.readouterr().err


# ---------------------------------------------------------------- shared


@pytest.mark.parametrize("kind", ["banner", "heading"])
def test_one_clock_and_a_light_animation_budget(kind: str) -> None:
    for variant in VARIANTS if kind == "banner" else [None]:
        svg = forge.render(kind, variant=variant, data=HEADER if kind == "banner" else None)
        report = check(svg)
        durations = sorted({float(d) for d in re.findall(r'dur="([\d.]+)s"', svg)})
        longest = durations[-1]
        assert all(round(longest / d, 3) == round(longest / d) for d in durations), durations
        assert report.stats["animated_elements"] <= 12


@pytest.mark.parametrize("spec", ["transparent-dark", "transparent-light"])
@pytest.mark.parametrize("kind", ["banner", "heading"])
def test_transparent_theme_reads_on_its_page(kind: str, spec: str) -> None:
    for variant in VARIANTS if kind == "banner" else [None]:
        svg = forge.render(kind, theme=spec, variant=variant)
        check(svg, forge.load_theme(spec)[0].mode)
