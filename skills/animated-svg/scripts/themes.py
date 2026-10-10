#!/usr/bin/env python3
"""Theme tokens for forge.py: presets, palette files and brand-derived themes (stdlib only).

get_theme() returns a dict with forge's Theme token names (TOKENS) plus mode ("dark" or
"light"), accent (the theme's default accent hex), transparent (paint no background) and
notes (what the contrast guarantee changed). Every theme is checked with WCAG 2.2 contrast
ratios (sRGB relative luminance; a translucent color is composited over what is under it):

  ink, text              at least 4.5:1 on bg and on card (card composited over bg)
  dim, ok, warn, muted   at least 3:1 on bg and on card
  accent as ink          at least 3:1 on bg and on card (accent_ink, also at render time)

Presets pass as written. When a palette file or a derived theme falls short, the color's HLS
lightness moves by the smallest step that passes (a translucent color is flattened over bg
first) and the change is listed in notes. Transparent themes paint no background: bg is the
page they are checked on (GitHub's #0d1117 or #ffffff, by mode), and dim, ok, warn, muted and
the accent are also checked on the other GitHub page so they read on both. ink and text cannot
be: no opaque color reaches 4.5:1 on both pages (the best is about 4.35:1), so they follow mode.

Specs:
  github-dark, nord, ...     a preset (list_themes()); "dark" and "light" alias the GitHub pair
  auto:#ff5a1f, #ff5a1f      a full theme derived from one brand color; mode= picks dark or light
  path/to/palette.json       a palette file:

Palette file (one JSON object, every key optional; unknown keys and bad values raise ThemeError):
  "extends"       preset name or auto:<hex> to start from (default github-dark, or github-light
                  when "mode" is "light")
  "name"          theme name (default: the file name without .json)
  "mode"          "dark" or "light" (default: the base's); sets the accent lightness clamp
  "transparent"   true or false (default: the base's)
  "description"   free text, ignored
  "accent", "ink", "ok", "warn", "muted", "bg", "wash"
                  opaque color: #rgb, #rrggbb or rgb(r,g,b)
  "card", "text", "dim", "border", "panel", "panel_stroke", "grid"
                  any color: also #rrggbbaa or rgba(r,g,b,a)
  "shine"         number from 0 to 1, peak opacity of the white shine sweep

Usage:
  python themes.py --list
  python themes.py nord
  python themes.py auto:#ff5a1f --mode light --accent "#0ea5e9"
  python themes.py assets/palettes/ember.json
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# forge.Theme field names, in order; get_theme() adds EXTRAS and "notes"
TOKENS = (
    "name",
    "bg",
    "wash",
    "card",
    "ink",
    "text",
    "dim",
    "border",
    "panel",
    "panel_stroke",
    "grid",
    "ok",
    "warn",
    "muted",
    "shine",
)
EXTRAS = ("mode", "accent", "transparent")
COLORS = (*(t for t in TOKENS if t not in ("name", "shine")), "accent")
OPAQUE = ("accent", "ink", "ok", "warn", "muted", "bg", "wash")  # forge feeds these to alpha()
PALETTE_KEYS = frozenset((*TOKENS, *EXTRAS, "extends", "description"))

TEXT_MIN = 4.5  # WCAG 2.2 SC 1.4.3, normal text
UI_MIN = 3.0  # WCAG 2.2 SC 1.4.11 graphics, and SC 1.4.3 large text
# token, minimum ratio, also checked on the other GitHub page when the theme is transparent
RULES = (
    ("ink", TEXT_MIN, False),
    ("text", TEXT_MIN, False),
    ("dim", UI_MIN, True),
    ("ok", UI_MIN, True),
    ("warn", UI_MIN, True),
    ("muted", UI_MIN, True),
)

# GitHub page backgrounds, Primer bgColor.default (light neutral.0, dark neutral.1):
# https://github.com/primer/primitives/blob/main/src/tokens/functional/color/bgColor.json5
# https://github.com/primer/primitives/blob/main/src/tokens/base/color/dark/dark.json5
GITHUB_DARK_PAGE = "#0d1117"
GITHUB_LIGHT_PAGE = "#ffffff"
DEFAULT_ACCENT = "#60a5fa"

Color = tuple[float, float, float, float]  # r, g, b in 0..255, alpha in 0..1


class ThemeError(ValueError):
    """Bad theme spec, palette file or color; the message says what to fix."""


# ---------------------------------------------------------------- color math

_HEX = re.compile(r"#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})")
_FUNC = re.compile(
    r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d*\.?\d+)\s*)?\)"
)


def parse_color(value: object, what: str = "color") -> Color:
    """#rgb, #rrggbb, #rrggbbaa, rgb(r,g,b) or rgba(r,g,b,a) as (r, g, b, alpha)."""
    text = value.strip().lower() if isinstance(value, str) else ""
    m = _HEX.fullmatch(text)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        alpha = round(int(h[6:], 16) / 255, 3) if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
    m = _FUNC.fullmatch(text)
    if m:
        r, g, b = (int(x) for x in m.group(1, 2, 3))
        alpha = float(m.group(4)) if m.group(4) else 1.0
        if max(r, g, b) <= 255 and alpha <= 1:
            return (r, g, b, alpha)
    raise ThemeError(
        f"{what} must be a color like #0b1012, #fff or rgba(255,255,255,0.5), got {value!r}"
    )


def format_color(color: Color) -> str:
    """#rrggbb when opaque, else rgba(r,g,b,a) with at most 3 alpha decimals."""
    r, g, b = (round(v) for v in color[:3])
    if color[3] >= 1:
        return f"#{r:02x}{g:02x}{b:02x}"
    a = f"{color[3]:.3f}".rstrip("0").rstrip(".") or "0"
    return f"rgba({r},{g},{b},{a})"


def _opaque(value: object, what: str) -> Color:
    color = parse_color(value, what)
    if color[3] < 1:
        raise ThemeError(f"{what} must be an opaque color, got {value!r}")
    return color


def _over(fg: Color, under: Color) -> Color:
    """Composite fg over an opaque color (source-over in sRGB, as browsers paint)."""
    a = fg[3]
    r, g, b = (fg[i] * a + under[i] * (1 - a) for i in range(3))
    return (r, g, b, 1.0)


def _channel(value: float) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lum(color: Color) -> float:
    return 0.2126 * _channel(color[0]) + 0.7152 * _channel(color[1]) + 0.0722 * _channel(color[2])


def _ratio(fg: Color, under: Color) -> float:
    a, b = _lum(_over(fg, under)), _lum(under)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def luminance(color: str) -> float:
    """WCAG 2.2 relative luminance of an opaque color, 0 (black) to 1 (white)."""
    return _lum(_opaque(color, "color"))


def _under(bg: str, base: str | None) -> Color:
    under = parse_color(bg, "bg")
    if under[3] < 1:
        if base is None:
            raise ThemeError(f"bg {bg!r} is translucent; pass base, the opaque color under it")
        under = _over(under, _opaque(base, "base"))
    return under


def contrast(fg: str, bg: str, base: str | None = None) -> float:
    """WCAG 2.2 contrast ratio (1 to 21) of fg painted on bg.

    A translucent fg is composited over bg; a translucent bg needs base, the color under it.
    """
    return _ratio(parse_color(fg, "fg"), _under(bg, base))


def _from_hls(h: float, light: float, sat: float) -> Color:
    rgb = colorsys.hls_to_rgb(h, min(max(light, 0.0), 1.0), min(max(sat, 0.0), 1.0))
    r, g, b = (round(ch * 255) for ch in rgb)
    return (r, g, b, 1.0)


def _hls(color: Color) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(*(round(v) / 255 for v in color[:3]))


def _fix(fg: Color, surfaces: list[Color], minimum: float, what: str) -> str:
    """fg unchanged when it passes on every surface, else the nearest HLS lightness that does."""
    if all(_ratio(fg, s) >= minimum for s in surfaces):
        return format_color(fg)
    flat = _over(fg, surfaces[0])
    h, light, sat = _hls(flat)
    signs = (1, -1) if _lum(flat) >= _lum(surfaces[0]) else (-1, 1)
    for step in range(1, 1001):
        for sign in signs:
            candidate = _from_hls(h, light + sign * step / 1000, sat)
            if all(_ratio(candidate, s) >= minimum for s in surfaces):
                return format_color(candidate)
    shown = ", ".join(format_color(s) for s in surfaces)
    raise ThemeError(f"{what} cannot reach {minimum:g}:1 on {shown}; pick a darker or lighter bg")


def ensure_contrast(fg: str, bg: str, minimum: float, base: str | None = None) -> str:
    """fg (normalized) when it reaches minimum:1 on bg, else the nearest lightness that does.

    A translucent fg that fails is flattened over bg first, so the result is opaque.
    """
    if not 1 <= minimum <= 21:
        raise ThemeError(f"minimum contrast must be between 1 and 21, got {minimum!r}")
    return _fix(parse_color(fg, "fg"), [_under(bg, base)], minimum, "fg")


def _surfaces(theme: Mapping[str, Any], both: bool) -> list[Color]:
    """bg and card over bg; a transparent theme adds the other GitHub page when both is set."""
    pages = [_opaque(theme["bg"], "bg")]
    if both and theme["transparent"]:
        other = GITHUB_LIGHT_PAGE if theme["mode"] == "dark" else GITHUB_DARK_PAGE
        pages.append(_opaque(other, "page"))
    card = parse_color(theme["card"], "card")
    out: list[Color] = []
    for page in pages:
        out += [page, _over(card, page)]
    return out


def _clamped(accent: Color, mode: str) -> Color:
    """forge 0.1.0 ink_for: at least 60% HLS lightness on dark, at most 42% on light."""
    h, light, sat = _hls(accent)
    target = max(light, 0.6) if mode == "dark" else min(light, 0.42)
    return accent if target == light else _from_hls(h, target, sat)


def accent_ink(accent: str, theme: Mapping[str, Any]) -> str:
    """The accent as text and strokes: forge's lightness clamp, then 3:1 on bg and card.

    On a transparent theme the 3:1 also holds on the other GitHub page.
    """
    color = _clamped(_opaque(accent, "accent"), theme["mode"])
    return _fix(color, _surfaces(theme, both=True), UI_MIN, "accent")


# ---------------------------------------------------------------- presets


def _rgba(hexcolor: str, a: float) -> str:
    return format_color((*parse_color(hexcolor)[:3], a))


def _mix(a: str, b: str, t: float) -> str:
    """t of the way from a to b, as opaque hex."""
    ca, cb = parse_color(a), parse_color(b)
    return format_color((*(ca[i] + (cb[i] - ca[i]) * t for i in range(3)), 1.0))


def _preset(
    name: str,
    mode: str,
    *,
    bg: str,
    card: str,
    ink: str,
    text: str,
    dim: str,
    ok: str,
    warn: str,
    muted: str,
    accent: str,
    wash: str | None = None,
    line: str | None = None,
    shine: float | None = None,
    transparent: bool = False,
) -> dict[str, Any]:
    """A theme whose hairlines are one color at forge's alpha ladder (line, default ink)."""
    dark = mode == "dark"
    line = line or ink
    border, panel, stroke, grid = (0.09, 0.04, 0.16, 0.035) if dark else (0.13, 0.035, 0.2, 0.05)
    return {
        "name": name,
        "bg": bg,
        "wash": wash or _mix(bg, accent, 0.06 if dark else 0.1),
        "card": card,
        "ink": ink,
        "text": text,
        "dim": dim,
        "border": _rgba(line, border),
        "panel": _rgba(line, panel),
        "panel_stroke": _rgba(line, stroke),
        "grid": _rgba(line, grid),
        "ok": ok,
        "warn": warn,
        "muted": muted,
        "shine": (0.16 if dark else 0.55) if shine is None else shine,
        "mode": mode,
        "accent": accent,
        "transparent": transparent,
    }


PRESETS: dict[str, dict[str, Any]] = {
    # forge 0.1.0 "dark" and "light", byte for byte, so existing output does not change
    "github-dark": {
        "name": "github-dark",
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
        "mode": "dark",
        "accent": DEFAULT_ACCENT,
        "transparent": False,
    },
    "github-light": {
        "name": "github-light",
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
        "mode": "light",
        "accent": DEFAULT_ACCENT,
        "transparent": False,
    },
    # https://www.nordtheme.com/docs/colors-and-palettes
    # nord0 bg, nord1 card, nord6 ink, nord4 text, nord14 ok, nord13 warn, nord8 accent;
    # no Nord grey between nord3 and nord4 reads on nord1, so dim and muted are nord4 at alpha
    "nord": _preset(
        "nord",
        "dark",
        bg="#2e3440",
        card="#3b4252",
        ink="#eceff4",
        text="#d8dee9",
        dim="rgba(216,222,233,0.62)",
        ok="#a3be8c",
        warn="#ebcb8b",
        muted=_mix("#2e3440", "#d8dee9", 0.7),  # nord4 at 70% over nord0
        accent="#88c0d0",
    ),
    # https://spec.draculatheme.com/ (Background, Current Line, Foreground, Green, Orange, Purple);
    # Comment #6272a4 is under 3:1 on Current Line, so dim and muted come from Foreground
    "dracula": _preset(
        "dracula",
        "dark",
        bg="#282a36",
        card="#44475a",
        ink="#f8f8f2",
        text="rgba(248,248,242,0.82)",
        dim="rgba(248,248,242,0.62)",
        ok="#50fa7b",
        warn="#ffb86c",
        muted=_mix("#282a36", "#f8f8f2", 0.62),  # Foreground at 62% over Background
        accent="#bd93f9",
    ),
    # https://github.com/catppuccin/palette/blob/main/palette.json (mocha)
    "catppuccin-mocha": _preset(
        "catppuccin-mocha",
        "dark",
        bg="#1e1e2e",  # base
        card="#313244",  # surface0
        ink="#cdd6f4",  # text
        text="#bac2de",  # subtext1
        dim="#7f849c",  # overlay1
        ok="#a6e3a1",  # green
        warn="#fab387",  # peach
        muted="#9399b2",  # overlay2
        accent="#cba6f7",  # mauve
    ),
    # https://github.com/catppuccin/palette/blob/main/palette.json (latte); green is 2.96:1 and
    # peach 2.64:1 on base, so ok and warn are those hues at the nearest lightness for 3:1
    "catppuccin-latte": _preset(
        "catppuccin-latte",
        "light",
        bg="#eff1f5",  # base
        card="#e6e9ef",  # mantle
        ink="#4c4f69",  # text
        text="#5c5f77",  # subtext1
        dim="#7c7f93",  # overlay2
        ok="#3d9829",  # green #40a02b, darkened
        warn="#e75501",  # peach #fe640b, darkened
        muted="#6c6f85",  # subtext0
        accent="#8839ef",  # mauve
    ),
    # https://github.com/folke/tokyonight.nvim/blob/main/lua/tokyonight/colors/storm.lua
    # with the night overrides from colors/night.lua (bg #1a1b26)
    "tokyo-night": _preset(
        "tokyo-night",
        "dark",
        bg="#1a1b26",  # bg (night)
        card="#292e42",  # bg_highlight
        ink="#c0caf5",  # fg
        text="#a9b1d6",  # fg_dark
        dim="#737aa2",  # dark5
        ok="#9ece6a",  # green
        warn="#e0af68",  # yellow
        muted="#737aa2",  # dark5
        accent="#7aa2f7",  # blue
    ),
    # https://github.com/morhetz/gruvbox/blob/master/colors/gruvbox.vim
    "gruvbox-dark": _preset(
        "gruvbox-dark",
        "dark",
        bg="#282828",  # dark0
        card="#3c3836",  # dark1
        ink="#fbf1c7",  # light0
        text="#ebdbb2",  # light1
        dim="#a89984",  # light4
        ok="#b8bb26",  # bright_green
        warn="#fabd2f",  # bright_yellow
        muted="#a89984",  # light4
        accent="#fe8019",  # bright_orange
    ),
    # https://ethanschoonover.com/solarized/ ; base0 body text is 4.1:1 on base02, so text is
    # base1 and the headline ink steps up to base2
    "solarized-dark": _preset(
        "solarized-dark",
        "dark",
        bg="#002b36",  # base03
        card="#073642",  # base02
        ink="#eee8d5",  # base2
        text="#93a1a1",  # base1
        dim="#839496",  # base0
        ok="#859900",  # green
        warn="#b58900",  # yellow
        muted="#839496",  # base0
        accent="#268bd2",  # blue
    ),
    # https://ethanschoonover.com/solarized/ ; base01 is 4.39:1 on base2, so ink and text are
    # base03 and base02; the accents share one luminance (2.62:1 on base2), so ok is green at
    # the nearest lightness for 3:1 and warn is orange, which passes as is
    "solarized-light": _preset(
        "solarized-light",
        "light",
        bg="#fdf6e3",  # base3
        card="#eee8d5",  # base2
        ink="#002b36",  # base03
        text="#073642",  # base02
        dim="#586e75",  # base01
        ok="#7b8e00",  # green #859900, darkened
        warn="#cb4b16",  # orange
        muted="#586e75",  # base01
        accent="#268bd2",  # blue
    ),
    # https://github.com/joshdick/onedark.vim/blob/main/autoload/onedark.vim (Atom One Dark)
    # and https://github.com/atom/atom/blob/master/packages/one-dark-syntax/styles/colors.less
    "one-dark": _preset(
        "one-dark",
        "dark",
        bg="#282c34",  # background
        card="#2c323c",  # cursor_grey
        ink="#abb2bf",  # foreground
        text="#abb2bf",  # foreground (the palette has one text grey that passes 4.5:1)
        dim="#828997",  # mono-2, hsl(220, 9%, 55%)
        ok="#98c379",  # green
        warn="#d19a66",  # dark_yellow
        muted="#828997",  # mono-2
        accent="#61afef",  # blue
    ),
    # GitHub dark high contrast, Primer functional tokens:
    # https://github.com/primer/primitives/blob/main/src/tokens/functional/color/fgColor.json5
    # bg neutral.0, fg neutral.13, muted neutral.10, border neutral.10, accent #74b9ff,
    # success #2bd853, attention yellow.3 of dark.high-contrast.json5
    "high-contrast-dark": _preset(
        "high-contrast-dark",
        "dark",
        bg="#010409",
        wash="#010409",
        card="#151b23",  # neutral.2
        ink="#ffffff",
        text="#f0f6fc",  # neutral.12
        dim="#b7bdc8",
        ok="#2bd853",
        warn="#f0b72f",
        muted="#b7bdc8",
        accent="#74b9ff",
        line="#b7bdc8",
        shine=0.2,
    ),
    # GitHub light high contrast (same sources; black #010409 from light.high-contrast.json5)
    # fg base black, muted neutral.10, accent blue.6, success #04591f, attention yellow.6
    "high-contrast-light": _preset(
        "high-contrast-light",
        "light",
        bg="#ffffff",
        wash="#ffffff",
        card="#f6f8fa",  # neutral.1
        ink="#010409",
        text="#25292e",  # neutral.12
        dim="#454c54",
        ok="#04591f",
        warn="#603700",
        muted="#454c54",
        accent="#023b95",
        line="#454c54",
    ),
    # No background. Checked on the mode's GitHub page; dim, ok, warn, muted and the accent
    # also on the other one. Greys are Primer neutrals that pass on both pages.
    "transparent-dark": _preset(
        "transparent-dark",
        "dark",
        bg=GITHUB_DARK_PAGE,
        wash=GITHUB_DARK_PAGE,
        card="rgba(127,127,127,0.08)",
        ink="#f0f6fc",  # dark neutral.12
        text="#d1d7e0",  # dark neutral.11
        dim="#818b98",  # light neutral.8
        ok="#1a7f37",  # light green.5
        warn="#9a6700",  # light yellow.5
        muted="#818b98",
        accent="#388bfd",  # dark blue.4
        line="#7f7f7f",
        transparent=True,
    ),
    "transparent-light": _preset(
        "transparent-light",
        "light",
        bg=GITHUB_LIGHT_PAGE,
        wash=GITHUB_LIGHT_PAGE,
        card="rgba(127,127,127,0.08)",
        ink="#1f2328",  # light neutral.13
        text="#393f46",  # light neutral.11
        dim="#656c76",  # dark neutral.8
        ok="#1a7f37",  # light green.5
        warn="#9a6700",  # light yellow.5
        muted="#656c76",
        accent="#0969da",  # light fgColor.accent
        line="#7f7f7f",
        transparent=True,
    ),
}
ALIASES = {"dark": "github-dark", "light": "github-light"}
_PAIRS = (
    ("github-dark", "github-light"),
    ("catppuccin-mocha", "catppuccin-latte"),
    ("solarized-dark", "solarized-light"),
    ("high-contrast-dark", "high-contrast-light"),
    ("transparent-dark", "transparent-light"),
)
COUNTERPARTS = {a: b for pair in _PAIRS for a, b in (pair, pair[::-1])}


def list_themes() -> list[str]:
    """Preset names, GitHub pair first."""
    return list(PRESETS)


# ---------------------------------------------------------------- derived themes

_BRAND = re.compile(r"auto:#?([0-9a-f]{3}|[0-9a-f]{6})|#([0-9a-f]{3}|[0-9a-f]{6})")


def _brand(spec: str) -> str | None:
    """The hex in an auto:<hex> or bare #hex spec, as #rrggbb, else None."""
    m = _BRAND.fullmatch(spec.strip().lower())
    return format_color(parse_color("#" + (m.group(1) or m.group(2)))) if m else None


def derive_theme(brand: str, mode: str = "dark") -> dict[str, Any]:
    """A full theme tinted by one brand color, built like forge's GitHub pair.

    The brand's hue tints bg, wash, card and ink; its saturation sets how strongly (a grey
    brand gives neutral greys). The brand itself becomes the accent. Not yet contrast-checked;
    get_theme() does that.
    """
    if mode not in ("dark", "light"):
        raise ThemeError(f"mode must be dark or light, got {mode!r}")
    color = _opaque(brand, "brand color")
    h, _light, sat = _hls(color)
    k = min(1.0, sat * 1.25)
    accent = format_color(color)
    name = f"auto-{mode}-{accent[1:]}"

    def tint(light: float, s: float) -> str:
        return format_color(_from_hls(h, light, s * k))

    if mode == "dark":
        return {
            **PRESETS["github-dark"],
            "name": name,
            "bg": tint(0.057, 0.24),
            "wash": tint(0.098, 0.44),
            "card": tint(0.085, 0.3),
            "ink": tint(0.955, 0.14),
            "accent": accent,
        }
    ink = tint(0.057, 0.24)
    return {
        **PRESETS["github-light"],
        "name": name,
        "wash": tint(0.959, 0.68),
        "card": tint(0.973, 0.26),
        "ink": ink,
        "text": _rgba(ink, 0.76),
        "dim": _rgba(ink, 0.58),
        "border": _rgba(ink, 0.13),
        "panel": _rgba(ink, 0.035),
        "panel_stroke": _rgba(ink, 0.2),
        "grid": _rgba(ink, 0.05),
        "accent": accent,
    }


# ---------------------------------------------------------------- resolve and check


def _load_palette(path: Path, mode: str | None) -> dict[str, Any]:
    where = f"{path.name}: "
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ThemeError(f"cannot read palette {path.as_posix()}: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise ThemeError(f"{where}not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ThemeError(f"{where}a palette must be a JSON object of token names")
    unknown = sorted(set(raw) - PALETTE_KEYS)
    if unknown:
        allowed = ", ".join(sorted(PALETTE_KEYS))
        raise ThemeError(f"{where}unknown key(s) {', '.join(unknown)}; allowed: {allowed}")
    file_mode = raw.get("mode")
    if file_mode not in (None, "dark", "light"):
        raise ThemeError(f'{where}mode must be "dark" or "light", got {file_mode!r}')
    base = raw.get("extends", "github-light" if file_mode == "light" else "github-dark")
    brand = _brand(base) if isinstance(base, str) else None
    preset = _preset_name(base) if isinstance(base, str) else None
    if brand:
        theme = derive_theme(brand, file_mode or "dark")
    elif preset:
        theme = dict(PRESETS[preset])
    else:
        raise ThemeError(
            f"{where}extends must be a preset ({', '.join(list_themes())}) or auto:<hex>, "
            f"got {base!r}"
        )
    theme.update({k: v for k, v in raw.items() if k not in ("extends", "description")})
    if "name" not in raw:
        theme["name"] = re.sub(r"[^\w.:-]+", "-", path.stem)[:48]
    if mode is not None and mode != theme["mode"]:
        raise ThemeError(f"{where}this is a {theme['mode']} palette; it has no {mode} variant")
    return theme


def _preset_name(spec: str) -> str | None:
    name = ALIASES.get(spec.strip().lower(), spec.strip().lower())
    return name if name in PRESETS else None


def _resolve(spec: object, mode: str | None) -> tuple[dict[str, Any], str]:
    """The unchecked theme for spec, and the prefix error messages about it should carry."""
    if not isinstance(spec, str) or not spec.strip():
        raise ThemeError(f"theme spec must be a non-empty string, got {spec!r}")
    key = spec.strip()
    name = _preset_name(key)
    if name:
        if mode is not None and mode != PRESETS[name]["mode"]:
            other = COUNTERPARTS.get(name)
            if other is None:
                raise ThemeError(
                    f"{name} has no {mode} variant; pass a {mode} preset or auto:<hex>"
                )
            name = other
        return dict(PRESETS[name]), ""
    brand = _brand(key)
    if brand:
        return derive_theme(brand, mode or "dark"), ""
    path = Path(key)
    if key.lower().endswith(".json") or path.is_file():
        return _load_palette(path, mode), f"{path.name}: "
    raise ThemeError(
        f"unknown theme {spec!r}; use a preset ({', '.join(list_themes())}), "
        "auto:<hex> or a palette .json file"
    )


def _validate(theme: dict[str, Any], where: str) -> None:
    name = theme["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][\w .:-]{0,47}", name):
        raise ThemeError(f"{where}name must be 1 to 48 letters, digits, space, . _ : or -")
    for key in COLORS:
        color = parse_color(theme[key], f"{where}{key}")
        if key in OPAQUE and color[3] < 1:
            raise ThemeError(f"{where}{key} must be an opaque color, got {theme[key]!r}")
        theme[key] = format_color(color)
    shine = theme["shine"]
    if isinstance(shine, bool) or not isinstance(shine, (int, float)) or not 0 <= shine <= 1:
        raise ThemeError(f"{where}shine must be a number from 0 to 1, got {shine!r}")
    if theme["mode"] not in ("dark", "light"):
        raise ThemeError(f'{where}mode must be "dark" or "light", got {theme["mode"]!r}')
    if not isinstance(theme["transparent"], bool):
        raise ThemeError(f"{where}transparent must be true or false, got {theme['transparent']!r}")


def _guarantee(theme: dict[str, Any]) -> list[str]:
    """Apply the contrast rules in place; return one note per changed color."""
    notes = []
    for token, minimum, both in RULES:
        old = theme[token]
        new = _fix(parse_color(old), _surfaces(theme, both), minimum, f"{theme['name']} {token}")
        if new != old:
            theme[token] = new
            notes.append(f"{token} {old} -> {new} to reach {minimum:g}:1")
    clamped = format_color(_clamped(parse_color(theme["accent"]), theme["mode"]))
    ink = accent_ink(theme["accent"], theme)
    if ink != clamped:
        notes.append(f"accent {theme['accent']} as ink -> {ink} to reach {UI_MIN:g}:1")
    return notes


def get_theme(spec: str, accent: str | None = None, mode: str | None = None) -> dict[str, Any]:
    """Resolve spec to a contrast-checked theme dict (TOKENS + EXTRAS + notes).

    accent replaces the theme's default accent. mode picks dark or light for auto:<hex>
    (default dark); for a preset it selects the counterpart (catppuccin-mocha with
    mode="light" gives catppuccin-latte) and raises when there is none.
    """
    if mode not in (None, "dark", "light"):
        raise ThemeError(f"mode must be dark or light, got {mode!r}")
    theme, where = _resolve(spec, mode)
    if accent is not None:
        theme["accent"] = accent
    _validate(theme, where)
    theme["notes"] = _guarantee(theme)
    return theme


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="themes.py", description="Resolve a theme and print its tokens as JSON."
    )
    ap.add_argument("spec", nargs="?", help="preset name, auto:<hex>, #hex or a palette .json")
    ap.add_argument("--accent", help="accent hex to check with the theme")
    ap.add_argument("--mode", choices=["dark", "light"], help="dark or light variant")
    ap.add_argument("--list", action="store_true", help="print the preset names")
    args = ap.parse_args(argv)
    if args.list:
        print("\n".join(list_themes()))
        return 0
    if not args.spec:
        ap.error("give a theme spec or --list")
    try:
        theme = get_theme(args.spec, accent=args.accent, mode=args.mode)
    except ThemeError as exc:
        print(f"themes.py: error: {exc}", file=sys.stderr)
        return 2
    theme["accent_ink"] = accent_ink(theme["accent"], theme)
    print(json.dumps(theme, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
