"""sizes.py: size specs, platform presets, bounds, scale_factor and Layout clamps."""

from __future__ import annotations

import math

import pytest
import sizes

EXPECTED = {
    "readme": (880, None),
    "readme-half": (430, None),
    "card": (400, 200),
    "og": (1280, 640),
    "banner-wide": (1500, 500),
    "linkedin-banner": (1584, 396),
    "youtube-banner": (2560, 1440),
    "square": (1080, 1080),
    "story": (1080, 1920),
    "slide-16x9": (1920, 1080),
    "icon-512": (512, 512),
    "icon-128": (128, 128),
    "icon-64": (64, 64),
    "favicon-32": (32, 32),
    "avatar-460": (460, 460),
}


def test_every_requested_preset_exists() -> None:
    assert sizes.list_sizes() == list(EXPECTED)


@pytest.mark.parametrize("name", [n for n, (_, h) in EXPECTED.items() if h])
def test_fixed_preset_resolves_to_its_dimensions(name: str) -> None:
    assert sizes.resolve_size(name) == (*EXPECTED[name], name)


@pytest.mark.parametrize("name", [n for n, (_, h) in EXPECTED.items() if h is None])
def test_width_preset_keeps_the_kind_aspect(name: str) -> None:
    w, h, got = sizes.resolve_size(name, (600, 300))

    assert (w, h, got) == (EXPECTED[name][0], EXPECTED[name][0] // 2, name)


def test_social_preview_aliases_og() -> None:
    assert sizes.resolve_size("social-preview") == (1280, 640, "og")


@pytest.mark.parametrize("spec", ["OG", "Slide_16x9", " card "])
def test_preset_names_ignore_case_underscores_and_spaces(spec: str) -> None:
    assert sizes.resolve_size(spec)[2] is not None


@pytest.mark.parametrize("name", list(EXPECTED))
def test_preset_cites_a_source_or_says_convention(name: str) -> None:
    source = sizes.SIZES[name].source

    assert source.startswith(("https://", "convention"))


@pytest.mark.parametrize(
    "spec", ["1280x640", "1280X640", " 1280 x 640 ", "1280*640", "1280" + chr(0xD7) + "640"]
)
def test_width_by_height_parses(spec: str) -> None:
    assert sizes.resolve_size(spec) == (1280, 640, None)


def test_width_alone_keeps_the_kind_aspect() -> None:
    assert sizes.resolve_size("880", (840, 240)) == (880, 251, None)


@pytest.mark.parametrize("spec", [880, 880.0])
def test_numeric_width_is_accepted(spec: float) -> None:
    assert sizes.resolve_size(spec, (840, 240)) == (880, 251, None)


@pytest.mark.parametrize("spec", [None, "", "  "])
def test_empty_spec_gives_the_kind_default(spec: object) -> None:
    assert sizes.resolve_size(spec, (600, 180)) == (600, 180, None)


@pytest.mark.parametrize("spec", ["16x16", "4096x4096"])
def test_bounds_are_inclusive(spec: str) -> None:
    w, h, _ = sizes.resolve_size(spec)

    assert (w, h) in ((16, 16), (4096, 4096))


@pytest.mark.parametrize(
    "spec",
    ["0x0", "15x100", "4097x100", "100x5000", "10", "5000", "abc", "12.5x3", "-100", "x640"],
)
def test_bad_size_raises(spec: str) -> None:
    with pytest.raises(sizes.SizeError):
        sizes.resolve_size(spec)


@pytest.mark.parametrize("spec", [True, [880], 880.5])
def test_bad_size_type_raises(spec: object) -> None:
    with pytest.raises(sizes.SizeError):
        sizes.resolve_size(spec)


def test_out_of_range_error_names_the_bounds() -> None:
    with pytest.raises(sizes.SizeError, match="16 to 4096 px"):
        sizes.resolve_size("5000x100")


def test_unknown_size_error_lists_the_presets() -> None:
    with pytest.raises(sizes.SizeError, match="readme, readme-half, card, og"):
        sizes.resolve_size("poster")


def test_width_whose_aspect_height_is_out_of_range_suggests_wxh() -> None:
    with pytest.raises(sizes.SizeError, match="pass WxH instead"):
        sizes.resolve_size("100", (840, 12))


@pytest.mark.parametrize("default", [(0, 240), (840,), "840x240", (840, math.nan), (True, 2)])
def test_bad_kind_default_raises(default: object) -> None:
    with pytest.raises(sizes.SizeError, match="kind_default"):
        sizes.resolve_size("og", default)


def test_youtube_safe_area_is_centered() -> None:
    assert sizes.safe_box("youtube-banner", 2560, 1440) == (508.0, 508.5, 1544.0, 423.0)


def test_safe_area_scales_with_the_canvas() -> None:
    assert sizes.safe_box("youtube-banner", 1280, 720) == (254.0, 254.25, 772.0, 211.5)


def test_preset_without_safe_area_uses_the_whole_canvas() -> None:
    assert sizes.safe_box("og", 1280, 640) == (0.0, 0.0, 1280.0, 640.0)


# ---------------------------------------------------------------- scale and layout


def test_scale_factor_is_the_width_ratio() -> None:
    assert sizes.scale_factor(1760, 880) == 2.0


@pytest.mark.parametrize(("width", "base"), [(0, 880), (880, -1), (math.inf, 880), (True, 880)])
def test_scale_factor_rejects_bad_numbers(width: float, base: float) -> None:
    with pytest.raises(sizes.SizeError):
        sizes.scale_factor(width, base)


def test_layout_is_identity_at_the_base_size() -> None:
    layout = sizes.Layout(840, 240)

    assert (layout.scale, layout.font(13), layout.pad, layout.gutter) == (1.0, 13.0, 20.0, 12.0)


def test_layout_scale_fits_both_sides() -> None:
    assert sizes.Layout(1584, 396, base=(840, 240)).scale == 1.65


def test_layout_font_grows_between_the_clamps() -> None:
    assert sizes.Layout(2560, 1440).font(10) == 30.48


def test_layout_font_stops_at_the_floor_on_an_icon() -> None:
    assert sizes.Layout(64, 64).font(10) == sizes.FONT_FLOOR


def test_layout_font_below_the_floor_keeps_its_design_size() -> None:
    assert sizes.Layout(64, 64).font(6) == 6.0


def test_layout_font_never_passes_half_the_short_side() -> None:
    assert sizes.Layout(10, 10).font(10) == 5.0


def test_layout_font_stops_at_max_scale() -> None:
    assert sizes.Layout(4096, 4096, base=(64, 64)).font(10) == 10 * sizes.MAX_SCALE


def test_layout_space_stops_at_its_floor() -> None:
    assert sizes.Layout(64, 64).pad == 20 * sizes.SPACE_FLOOR


def test_layout_space_never_passes_a_quarter_of_the_short_side() -> None:
    assert sizes.Layout(16, 16).pad == 4.0


def test_layout_space_stops_at_max_scale() -> None:
    assert sizes.Layout(4096, 4096, base=(64, 64)).gutter == 12 * sizes.MAX_SCALE


@pytest.mark.parametrize("size", [(0, 240), (840, -5)])
def test_layout_rejects_a_bad_canvas(size: tuple[float, float]) -> None:
    with pytest.raises(sizes.SizeError):
        sizes.Layout(*size)


# ---------------------------------------------------------------- CLI


def test_cli_prints_the_size(capsys: pytest.CaptureFixture[str]) -> None:
    code = sizes.main(["og"])

    assert (code, capsys.readouterr().out) == (0, "1280x640 (og)\n")


def test_cli_exits_2_on_a_bad_size(capsys: pytest.CaptureFixture[str]) -> None:
    code = sizes.main(["9999x9999"])

    assert code == 2
    assert "16 to 4096" in capsys.readouterr().err
