"""Loader variants: each renders valid, quiet, deterministic SVG that loops or freezes cleanly."""

from __future__ import annotations

import re
from xml.dom import minidom

import pytest

import forge
import poster
import validate_svg

CLASSIC = ("spinner", "dots", "bar")
NEW = ("pulse", "orbit", "bars", "wave", "ring", "blocks", "clock", "bounce")
VARIANTS = (*CLASSIC, *NEW)
ANIMATION = re.compile(r"<animate(?:Transform)?\b[^>]*>")
MAX_ANIMATED = 8


def validate(svg: str) -> validate_svg.Report:
    """Parse the file and validate it with contrast as errors on both GitHub pages."""
    minidom.parseString(svg)
    return validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme="both")


def test_every_variant_is_tested() -> None:
    assert list(forge.LOADER_VARIANTS) == list(VARIANTS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_validates_on_both_github_pages(variant: str) -> None:
    report = validate(forge.render("loader", variant=variant))

    assert report.findings == [], report.findings


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_is_visible_in_a_static_frame(variant: str) -> None:
    assert poster.problems(forge.render("loader", variant=variant)) == []


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_is_deterministic(variant: str) -> None:
    svg = forge.render("loader", variant=variant)

    assert svg == forge.render("loader", variant=variant)
    assert svg.endswith("</svg>\n")
    assert "\r" not in svg


@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_loops_by_default_and_freezes_with_once(variant: str) -> None:
    looping = forge.render("loader", variant=variant)
    once = forge.render("loader", variant=variant, loop=False)

    tags = ANIMATION.findall(looping)
    assert tags
    assert all('repeatCount="indefinite"' in tag and "freeze" not in tag for tag in tags)
    tags = ANIMATION.findall(once)
    assert tags
    assert all('fill="freeze"' in tag and "repeatCount" not in tag for tag in tags)
    assert "indefinite" not in once
    assert validate(once).findings == []


@pytest.mark.parametrize("timing", list(forge.PRESETS))
@pytest.mark.parametrize("variant", VARIANTS)
def test_variant_stays_calm_under_every_timing(variant: str, timing: str) -> None:
    report = validate(forge.render("loader", variant=variant, timing=timing))

    assert report.findings == [], report.findings
    assert report.stats["animated_elements"] <= MAX_ANIMATED


@pytest.mark.parametrize("variant", NEW)
def test_new_variant_loops_seamlessly(variant: str) -> None:
    doc = minidom.parseString(forge.render("loader", variant=variant))
    animations = [
        *doc.getElementsByTagName("animate"),
        *doc.getElementsByTagName("animateTransform"),
    ]

    assert animations
    for node in animations:
        values = node.getAttribute("values").split(";")
        first, last = values[0].split(), values[-1].split()
        if node.getAttribute("type") == "rotate":  # whole turns about the same center
            assert (float(last[0]) - float(first[0])) % 360 == 0, values
            assert last[1:] == first[1:], values
        else:
            assert values[0] == values[-1], values


def test_unknown_variant_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(forge.ForgeError, match="loader variant must be"):
        forge.render("loader", variant="wheel")

    assert forge.main(["--kind", "loader", "--variant", "wheel"]) == 2
    err = capsys.readouterr().err
    assert all(name in err for name in VARIANTS)
