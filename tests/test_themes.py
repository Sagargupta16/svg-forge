"""themes.py: WCAG contrast math, presets, derived themes, palette files and the guarantee."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import themes

PALETTES = (
    Path(__file__).resolve().parent.parent / "skills" / "animated-svg" / "assets" / "palettes"
)
REQUIRED = [
    "github-dark",
    "github-light",
    "nord",
    "dracula",
    "catppuccin-mocha",
    "catppuccin-latte",
    "tokyo-night",
    "gruvbox-dark",
    "solarized-dark",
    "solarized-light",
    "one-dark",
    "high-contrast-dark",
    "high-contrast-light",
    "transparent-dark",
    "transparent-light",
]
BRANDS = [
    "#ffff66",  # very light
    "#1a1a1a",  # very dark
    "#ff0000",
    "#b91c1c",
    "#00ff00",
    "#15803d",
    "#0000ff",
    "#7c3aed",
    "#f59e0b",
    "#06b6d4",
    "#ffffff",
    "#808080",
]
# forge 0.1.0 THEMES, copied so a forge refactor cannot hide a token change
FORGE_DARK = {
    "bg": "#0b1012",
    "wash": "#0e1a24",
    "card": "#0f171c",
    "ink": "#f3f4f6",
    "text": "rgba(255,255,255,0.74)",
    "dim": "rgba(255,255,255,0.52)",
    "border": "rgba(255,255,255,0.09)",
    "panel": "rgba(255,255,255,0.04)",
    "panel_stroke": "rgba(255,255,255,0.16)",
    "grid": "rgba(255,255,255,0.035)",
    "ok": "#22c55e",
    "warn": "#f59e0b",
    "muted": "#9ca3af",
    "shine": 0.16,
}
FORGE_LIGHT = {
    "bg": "#ffffff",
    "wash": "#eef4fb",
    "card": "#f6f8fa",
    "ink": "#0b1012",
    "text": "rgba(11,16,18,0.76)",
    "dim": "rgba(11,16,18,0.58)",
    "border": "rgba(11,16,18,0.13)",
    "panel": "rgba(11,16,18,0.035)",
    "panel_stroke": "rgba(11,16,18,0.2)",
    "grid": "rgba(11,16,18,0.05)",
    "ok": "#15803d",
    "warn": "#b45309",
    "muted": "#4b5563",
    "shine": 0.55,
}


def surfaces(theme: dict[str, Any], both: bool) -> list[str]:
    """Opaque colors a token is drawn on: each page, and the card composited over it."""
    pages = [theme["bg"]]
    if both and theme["transparent"]:
        pages.append("#ffffff" if theme["mode"] == "dark" else "#0d1117")
    out = []
    for page in pages:
        card = themes.parse_color(theme["card"])
        out += [page, themes.format_color(themes._over(card, themes.parse_color(page)))]
    return out


def failures(theme: dict[str, Any]) -> list[str]:
    rules = [
        ("ink", 4.5, False),
        ("text", 4.5, False),
        ("dim", 3.0, True),
        ("ok", 3.0, True),
        ("warn", 3.0, True),
        ("muted", 3.0, True),
    ]
    colors = {token: theme[token] for token, _, _ in rules}
    colors["accent ink"] = themes.accent_ink(theme["accent"], theme)
    out = []
    for token, minimum, both in [*rules, ("accent ink", 3.0, True)]:
        for surface in surfaces(theme, both):
            ratio = themes.contrast(colors[token], surface)
            if ratio < minimum:
                out.append(f"{theme['name']} {token} {colors[token]} on {surface}: {ratio:.2f}")
    return out


def write(tmp_path: Path, data: object, name: str = "brand.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------- contrast math


def test_grey_777_on_white_is_just_under_aa() -> None:
    assert themes.contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


def test_black_on_white_is_21() -> None:
    assert themes.contrast("#000000", "#ffffff") == pytest.approx(21.0)


def test_same_color_is_1() -> None:
    assert themes.contrast("#3b82f6", "#3b82f6") == pytest.approx(1.0)


def test_contrast_is_symmetric_for_opaque_colors() -> None:
    assert themes.contrast("#0969da", "#f6f8fa") == pytest.approx(
        themes.contrast("#f6f8fa", "#0969da")
    )


def test_luminance_endpoints() -> None:
    assert (themes.luminance("#000"), themes.luminance("#fff")) == (0.0, 1.0)


def test_translucent_fg_is_composited_over_bg() -> None:
    assert themes.contrast("rgba(0,0,0,0.5)", "#ffffff") == pytest.approx(
        themes.contrast("#808080", "#ffffff"), abs=0.03
    )


def test_eight_digit_hex_carries_alpha() -> None:
    assert themes.parse_color("#00000080")[3] == pytest.approx(0.502)


def test_translucent_bg_needs_a_base() -> None:
    with pytest.raises(themes.ThemeError, match="base"):
        themes.contrast("#ffffff", "rgba(0,0,0,0.5)")


def test_translucent_bg_over_base_is_composited() -> None:
    assert themes.contrast("#ffffff", "rgba(0,0,0,0.5)", base="#ffffff") == pytest.approx(
        themes.contrast("#ffffff", "#808080"), abs=0.03
    )


@pytest.mark.parametrize(
    "value", ["blue", "#12", "#12345g", "rgb(300,0,0)", "rgba(0,0,0,2)", "", None, 255]
)
def test_bad_colors_raise(value: object) -> None:
    with pytest.raises(themes.ThemeError, match="must be a color"):
        themes.parse_color(value)


def test_ensure_contrast_keeps_a_passing_color() -> None:
    assert themes.ensure_contrast("#0969DA", "#ffffff", 4.5) == "#0969da"


def test_ensure_contrast_moves_a_failing_color_just_far_enough() -> None:
    fixed = themes.ensure_contrast("#777777", "#ffffff", 4.5)

    assert 4.5 <= themes.contrast(fixed, "#ffffff") < 4.6


def test_ensure_contrast_lightens_on_dark() -> None:
    fixed = themes.ensure_contrast("#333366", "#0d1117", 4.5)

    assert themes.luminance(fixed) > themes.luminance("#333366")


def test_ensure_contrast_flattens_a_failing_translucent_color() -> None:
    fixed = themes.ensure_contrast("rgba(255,255,255,0.2)", "#0b1012", 4.5)

    assert fixed.startswith("#")
    assert themes.contrast(fixed, "#0b1012") >= 4.5


def test_ensure_contrast_raises_when_unreachable() -> None:
    with pytest.raises(themes.ThemeError, match="cannot reach"):
        themes.ensure_contrast("#ff0000", "#777777", 7)


def test_ensure_contrast_rejects_impossible_minimum() -> None:
    with pytest.raises(themes.ThemeError, match="between 1 and 21"):
        themes.ensure_contrast("#000", "#fff", 22)


# ---------------------------------------------------------------- presets


def test_list_themes_has_every_required_preset() -> None:
    assert themes.list_themes() == REQUIRED


@pytest.mark.parametrize("name", REQUIRED)
def test_preset_meets_the_contrast_guarantee(name: str) -> None:
    assert failures(themes.get_theme(name)) == []


@pytest.mark.parametrize("name", REQUIRED)
def test_preset_passes_as_written(name: str) -> None:
    assert themes.get_theme(name)["notes"] == []


@pytest.mark.parametrize("name", REQUIRED)
def test_theme_has_exactly_the_token_names(name: str) -> None:
    keys = set(themes.get_theme(name))

    assert keys == {*themes.TOKENS, *themes.EXTRAS, "notes"}


def test_github_dark_matches_forge_dark_tokens() -> None:
    theme = themes.get_theme("github-dark")

    assert {k: theme[k] for k in FORGE_DARK} == FORGE_DARK
    assert (theme["mode"], theme["accent"], theme["transparent"]) == ("dark", "#60a5fa", False)


def test_github_light_matches_forge_light_tokens() -> None:
    theme = themes.get_theme("github-light")

    assert {k: theme[k] for k in FORGE_LIGHT} == FORGE_LIGHT
    assert (theme["mode"], theme["accent"], theme["transparent"]) == ("light", "#60a5fa", False)


@pytest.mark.parametrize(("alias", "name"), [("dark", "github-dark"), ("LIGHT", "github-light")])
def test_forge_theme_names_alias_the_github_pair(alias: str, name: str) -> None:
    assert themes.get_theme(alias) == themes.get_theme(name)


@pytest.mark.parametrize(
    ("accent", "theme", "expected"),
    [("#60a5fa", "github-dark", "#60a5fa"), ("#60a5fa", "github-light", "#0761d0")],
)
def test_accent_ink_matches_forge_clamp_when_it_passes(
    accent: str, theme: str, expected: str
) -> None:
    assert themes.accent_ink(accent, themes.get_theme(theme)) == expected


def test_accent_ink_fixes_an_accent_the_clamp_leaves_too_dark() -> None:
    theme = themes.get_theme("github-dark")
    ink = themes.accent_ink("#0000ff", theme)

    assert min(themes.contrast(ink, s) for s in surfaces(theme, True)) >= 3


@pytest.mark.parametrize("name", ["transparent-dark", "transparent-light"])
def test_transparent_preset_paints_no_background(name: str) -> None:
    assert themes.get_theme(name)["transparent"] is True


@pytest.mark.parametrize("name", ["transparent-dark", "transparent-light"])
@pytest.mark.parametrize("token", ["dim", "ok", "warn", "muted"])
def test_transparent_ui_colors_read_on_both_github_pages(name: str, token: str) -> None:
    color = themes.get_theme(name)[token]

    assert min(themes.contrast(color, page) for page in ("#0d1117", "#ffffff")) >= 3


@pytest.mark.parametrize("name", ["transparent-dark", "transparent-light"])
def test_transparent_accent_reads_on_both_github_pages(name: str) -> None:
    theme = themes.get_theme(name)
    ink = themes.accent_ink(theme["accent"], theme)

    assert min(themes.contrast(ink, page) for page in ("#0d1117", "#ffffff")) >= 3


@pytest.mark.parametrize(
    ("name", "mode", "expected"),
    [
        ("catppuccin-mocha", "light", "catppuccin-latte"),
        ("solarized-light", "dark", "solarized-dark"),
        ("github-dark", "dark", "github-dark"),
        ("transparent-dark", "light", "transparent-light"),
    ],
)
def test_mode_selects_the_preset_counterpart(name: str, mode: str, expected: str) -> None:
    assert themes.get_theme(name, mode=mode)["name"] == expected


def test_mode_without_a_counterpart_raises() -> None:
    with pytest.raises(themes.ThemeError, match="nord has no light variant"):
        themes.get_theme("nord", mode="light")


def test_accent_argument_replaces_the_default_accent() -> None:
    theme = themes.get_theme("nord", accent="#F0F")

    assert theme["accent"] == "#ff00ff"


def test_translucent_accent_is_rejected() -> None:
    with pytest.raises(themes.ThemeError, match="accent must be an opaque color"):
        themes.get_theme("nord", accent="rgba(255,0,0,0.5)")


def test_unknown_spec_lists_the_presets() -> None:
    with pytest.raises(themes.ThemeError, match="github-dark, github-light, nord"):
        themes.get_theme("solarised")


def test_get_theme_returns_a_fresh_dict() -> None:
    themes.get_theme("nord")["bg"] = "#000000"

    assert themes.get_theme("nord")["bg"] == "#2e3440"


# ---------------------------------------------------------------- derived themes


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize("brand", BRANDS)
def test_derived_theme_meets_the_contrast_guarantee(brand: str, mode: str) -> None:
    assert failures(themes.get_theme(f"auto:{brand}", mode=mode)) == []


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize("brand", BRANDS)
def test_derived_theme_is_deterministic(brand: str, mode: str) -> None:
    assert themes.get_theme(brand, mode=mode) == themes.get_theme(f"auto:{brand}", mode=mode)


@pytest.mark.parametrize("brand", BRANDS)
def test_derived_theme_keeps_the_brand_as_accent(brand: str) -> None:
    theme = themes.get_theme(f"auto:{brand}", mode="light")

    assert (theme["accent"], theme["mode"]) == (brand, "light")


def test_derived_theme_defaults_to_dark() -> None:
    assert themes.get_theme("auto:#ff5a1f")["mode"] == "dark"


@pytest.mark.parametrize("spec", ["auto:ff5a1f", "#FF5A1F", "AUTO:#ff5a1f", " auto:#ff5a1f "])
def test_brand_spec_forms_agree(spec: str) -> None:
    assert themes.get_theme(spec) == themes.get_theme("auto:#ff5a1f")


def test_derived_light_theme_reports_its_accent_adjustment() -> None:
    notes = themes.get_theme("auto:#ffff66", mode="light")["notes"]

    assert len(notes) == 1
    assert notes[0].startswith("accent #ffff66 as ink -> #")


def test_grey_brand_gives_neutral_greys() -> None:
    theme = themes.get_theme("auto:#808080")
    r, g, b, _ = themes.parse_color(theme["bg"])

    assert r == g == b


# ---------------------------------------------------------------- palette files


@pytest.mark.parametrize("path", sorted(PALETTES.glob("*.json")), ids=lambda p: p.name)
def test_shipped_palette_passes_as_written(path: Path) -> None:
    theme = themes.get_theme(str(path))

    assert theme["notes"] == []
    assert failures(theme) == []


def test_shipped_palettes_cover_dark_and_light() -> None:
    modes = {themes.get_theme(str(p))["mode"] for p in PALETTES.glob("*.json")}

    assert modes == {"dark", "light"}


def test_palette_overrides_its_base(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"extends": "nord", "accent": "#bf616a"}))

    assert (theme["bg"], theme["accent"], theme["mode"]) == ("#2e3440", "#bf616a", "dark")


def test_palette_name_defaults_to_the_file_name(tmp_path: Path) -> None:
    assert themes.get_theme(write(tmp_path, {}, "my-brand.json"))["name"] == "my-brand"


def test_palette_without_extends_starts_from_github_dark(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"name": "x"}))

    assert theme["bg"] == FORGE_DARK["bg"]


def test_light_palette_without_extends_starts_from_github_light(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"mode": "light"}))

    assert theme["bg"] == FORGE_LIGHT["bg"]


def test_palette_can_extend_a_brand_color(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"extends": "auto:#16a34a", "mode": "light"}))

    assert (theme["mode"], theme["accent"]) == ("light", "#16a34a")


def test_palette_failing_value_is_adjusted_and_noted(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"dim": "rgba(255,255,255,0.2)"}))

    assert theme["notes"][0].startswith("dim rgba(255,255,255,0.2) -> #")
    assert failures(theme) == []


def test_palette_colors_are_normalized(tmp_path: Path) -> None:
    theme = themes.get_theme(write(tmp_path, {"ok": "rgb(34, 197, 94)", "card": "#0F171CFF"}))

    assert (theme["ok"], theme["card"]) == ("#22c55e", "#0f171c")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"background": "#000"}, "unknown key"),
        ({"bg": "navy"}, "brand.json: bg must be a color"),
        ({"ink": "rgba(255,255,255,0.9)"}, "brand.json: ink must be an opaque color"),
        ({"extends": "monokai"}, "extends must be a preset"),
        ({"extends": "other.json"}, "extends must be a preset"),
        ({"mode": "dim"}, "mode must be"),
        ({"shine": 2}, "shine must be a number from 0 to 1"),
        ({"shine": True}, "shine must be a number from 0 to 1"),
        ({"transparent": "yes"}, "transparent must be true or false"),
        ({"name": "<b>"}, "name must be"),
        (["#000"], "must be a JSON object"),
    ],
)
def test_bad_palette_raises_a_clear_error(tmp_path: Path, data: object, message: str) -> None:
    with pytest.raises(themes.ThemeError, match=message):
        themes.get_theme(write(tmp_path, data))


def test_palette_with_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{bg: #000}", encoding="utf-8")

    with pytest.raises(themes.ThemeError, match="broken.json: not valid JSON"):
        themes.get_theme(str(path))


def test_missing_palette_file_raises(tmp_path: Path) -> None:
    with pytest.raises(themes.ThemeError, match="cannot read palette"):
        themes.get_theme(str(tmp_path / "absent.json"))


def test_palette_mode_mismatch_raises(tmp_path: Path) -> None:
    with pytest.raises(themes.ThemeError, match="light palette; it has no dark variant"):
        themes.get_theme(write(tmp_path, {"extends": "github-light"}), mode="dark")


# ---------------------------------------------------------------- CLI


def test_cli_prints_the_resolved_theme(capsys: pytest.CaptureFixture[str]) -> None:
    code = themes.main(["tokyo-night", "--accent", "#bb9af7"])
    out = json.loads(capsys.readouterr().out)

    assert code == 0
    assert (out["name"], out["accent"], out["accent_ink"]) == ("tokyo-night", "#bb9af7", "#bb9af7")


def test_cli_exits_2_on_a_bad_spec(capsys: pytest.CaptureFixture[str]) -> None:
    code = themes.main(["no-such-theme"])

    assert code == 2
    assert "unknown theme" in capsys.readouterr().err
