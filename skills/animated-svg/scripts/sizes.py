#!/usr/bin/env python3
"""Canvas sizes for forge.py: WxH, a width that keeps the kind's aspect, or a named preset.

  resolve_size("1280x640")              -> (1280, 640, None)
  resolve_size("880", (840, 240))       -> (880, 251, None)     width only keeps the aspect
  resolve_size("og")                    -> (1280, 640, "og")
  resolve_size("readme", (840, 240))    -> (880, 251, "readme") width-only preset

Each side must be MIN_SIDE to MAX_SIDE px (16 to 4096); anything else raises SizeError.

Layout keeps text and spacing readable from 64 px icons to 2560 px banners. For a canvas of
width x height drawn by a kind designed at base (bw, bh):
  scale        min(width / bw, height / bh), so the design fits both sides; 1.0 at base size
  font(px)     px * scale, at least min(px, FONT_FLOOR) and at most px * MAX_SCALE, and never
               above half the shorter canvas side (that cap wins on favicon-sized canvases)
  space(px)    px * scale, at least px * SPACE_FLOOR and at most px * MAX_SCALE, and never
               above a quarter of the shorter side, so padding cannot eat the canvas
  pad, gutter  space(base_pad), space(base_gutter)
Results round to 2 decimals so output stays byte-stable; at the base size every helper
returns its input unchanged (as long as the design itself respects the side caps).

Usage:
  python sizes.py --list
  python sizes.py og
  python sizes.py 880 --kind-default 840x240
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass

MIN_SIDE = 16
MAX_SIDE = 4096
FONT_FLOOR = 8.0  # px; forge's smallest labels are 8 px mono
SPACE_FLOOR = 0.25  # padding and gutters shrink to at most a quarter of their design size
MAX_SCALE = 4.0  # text and spacing grow to at most 4x their design size


class SizeError(ValueError):
    """Bad size spec; the message says what to pass instead."""


@dataclass(frozen=True)
class SizePreset:
    width: int
    height: int | None  # None: width only, the height follows the kind's aspect
    use: str
    source: str  # official doc URL, or why the number is a convention
    safe: tuple[int, int] | None = None  # centered area no platform crop reaches


SIZES: dict[str, SizePreset] = {
    "readme": SizePreset(
        880,
        None,
        "full-width README image",
        "convention: GitHub publishes no README width; images wider than the column scale "
        "down to fit (measured 830 px in repo view, 1012 px in file view: "
        "https://wh0.github.io/2025/05/18/banner-width.html)",
    ),
    "readme-half": SizePreset(
        430, None, "two README images side by side", "convention: (880 - 20 px gap) / 2"
    ),
    "card": SizePreset(400, 200, "small stat or link card", "convention: 2:1 README card"),
    "og": SizePreset(
        1280,
        640,
        "GitHub repository social preview",
        "https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features"
        "/customizing-your-repository/customizing-your-repositorys-social-media-preview",
    ),
    "banner-wide": SizePreset(
        1500,
        500,
        "X (Twitter) profile header",
        "https://help.x.com/en/managing-your-account/how-to-customize-your-profile",
    ),
    "linkedin-banner": SizePreset(
        1584,
        396,
        "LinkedIn profile background photo",
        "https://www.linkedin.com/help/linkedin/answer/a568217",
    ),
    "youtube-banner": SizePreset(
        2560,
        1440,
        "YouTube channel banner; keep text and logos inside the safe area",
        "https://support.google.com/youtube/answer/10456525 (safe area 1235 x 338 at the "
        "2048 x 1152 minimum, scaled here to 2560 wide)",
        safe=(1544, 423),
    ),
    "square": SizePreset(
        1080,
        1080,
        "square social post",
        "https://help.instagram.com/1631821640426723 (Instagram keeps up to 1080 px wide)",
    ),
    "story": SizePreset(
        1080,
        1920,
        "9:16 story or reel cover",
        "https://help.instagram.com/1631821640426723 (1080 px wide; 9:16 is the story frame)",
    ),
    "slide-16x9": SizePreset(1920, 1080, "16:9 slide or video frame", "convention: 1080p"),
    "icon-512": SizePreset(
        512,
        512,
        "web app manifest icon",
        "https://web.dev/articles/add-manifest (Chromium needs 192 and 512 px icons)",
    ),
    "icon-128": SizePreset(
        128,
        128,
        "browser extension store icon",
        "https://developer.chrome.com/docs/extensions/reference/manifest/icons",
    ),
    "icon-64": SizePreset(64, 64, "small app or list icon", "convention"),
    "favicon-32": SizePreset(32, 32, "favicon", "convention: the common desktop tab favicon"),
    "avatar-460": SizePreset(
        460,
        460,
        "profile picture",
        "convention: GitHub recommends about 500 x 500 px "
        "(https://docs.github.com/en/account-and-profile/reference/profile-reference)",
    ),
}
ALIASES = {"social-preview": "og"}

_PAIR = re.compile(r"(\d{1,5})\s*[x*\u00d7]\s*(\d{1,5})")  # x, * or the times sign
_WIDTH = re.compile(r"\d{1,5}")


def list_sizes() -> list[str]:
    """Preset names (aliases excluded)."""
    return list(SIZES)


def _bounded(w: int, h: int) -> tuple[int, int]:
    for name, side in (("width", w), ("height", h)):
        if not MIN_SIDE <= side <= MAX_SIDE:
            raise SizeError(f"{name} {side} is out of range; each side must be 16 to 4096 px")
    return w, h


def _base(kind_default: object) -> tuple[float, float]:
    ok = isinstance(kind_default, tuple) and len(kind_default) == 2
    if ok and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
        for v in kind_default
    ):
        return float(kind_default[0]), float(kind_default[1])
    raise SizeError(f"kind_default must be a (width, height) pair above 0, got {kind_default!r}")


def _width_only(w: int, base: tuple[float, float]) -> tuple[int, int]:
    h = max(1, round(w * base[1] / base[0]))
    if not MIN_SIDE <= w <= MAX_SIDE:
        raise SizeError(f"width {w} is out of range; each side must be 16 to 4096 px")
    if not MIN_SIDE <= h <= MAX_SIDE:
        raise SizeError(
            f"width {w} at the kind's {base[0]:g}x{base[1]:g} aspect gives height {h}, "
            "outside 16 to 4096 px; pass WxH instead"
        )
    return w, h


def resolve_size(
    spec: object, kind_default: tuple[float, float] = (840, 240)
) -> tuple[int, int, str | None]:
    """(width, height, preset name or None) for a size spec.

    spec is None or "" (the kind's default), "WxH" ("1280x640", also X, * or the times sign),
    a width ("880" or 880, the kind's aspect gives the height) or a preset from list_sizes().
    """
    base = _base(kind_default)
    if spec is None or (isinstance(spec, str) and not spec.strip()):
        return round(base[0]), round(base[1]), None
    if isinstance(spec, float) and spec.is_integer():
        spec = int(spec)
    if isinstance(spec, int) and not isinstance(spec, bool):
        return (*_width_only(spec, base), None)
    if not isinstance(spec, str):
        raise SizeError(f"size must be text like 1280x640, 880 or og, got {spec!r}")
    key = spec.strip().lower().replace("_", "-").replace(" ", "")
    name = ALIASES.get(key, key)
    if name in SIZES:
        preset = SIZES[name]
        if preset.height is None:
            return (*_width_only(preset.width, base), name)
        return (*_bounded(preset.width, preset.height), name)
    m = _PAIR.fullmatch(key)
    if m:
        return (*_bounded(int(m.group(1)), int(m.group(2))), None)
    if _WIDTH.fullmatch(key):
        return (*_width_only(int(key), base), None)
    raise SizeError(
        f"unknown size {spec!r}; pass WxH like 1280x640, a width like 880, or a preset: "
        + ", ".join([*SIZES, *ALIASES])
    )


def safe_box(name: str, width: float, height: float) -> tuple[float, float, float, float]:
    """(x, y, w, h) of the preset's centered safe area scaled to width x height.

    The whole canvas when the preset has no safe area.
    """
    preset = SIZES[ALIASES.get(name, name)]
    if preset.safe is None or preset.height is None:
        return 0.0, 0.0, float(width), float(height)
    sw = round(preset.safe[0] * width / preset.width, 2)
    sh = round(preset.safe[1] * height / preset.height, 2)
    return round((width - sw) / 2, 2), round((height - sh) / 2, 2), sw, sh


def scale_factor(width: float, base_width: float) -> float:
    """width / base_width, rounded to 4 places; both must be finite and above 0."""
    for name, value in (("width", width), ("base_width", base_width)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SizeError(f"{name} must be a number, got {value!r}")
        if not math.isfinite(value) or value <= 0:
            raise SizeError(f"{name} must be above 0, got {value!r}")
    return round(width / base_width, 4)


@dataclass(frozen=True)
class Layout:
    """Font and spacing sizes for a canvas, scaled from the kind's design size and clamped."""

    width: float
    height: float
    base: tuple[float, float] = (840, 240)
    base_pad: float = 20.0
    base_gutter: float = 12.0

    def __post_init__(self) -> None:
        _base(self.base)
        _base((self.width, self.height))

    @property
    def scale(self) -> float:
        return round(min(self.width / self.base[0], self.height / self.base[1]), 4)

    @property
    def short(self) -> float:
        return min(self.width, self.height)

    def font(self, px: float) -> float:
        size = min(max(px * self.scale, min(px, FONT_FLOOR)), px * MAX_SCALE)
        return round(min(size, self.short / 2), 2)

    def space(self, px: float) -> float:
        size = min(max(px * self.scale, px * SPACE_FLOOR), px * MAX_SCALE)
        return round(min(size, self.short / 4), 2)

    @property
    def pad(self) -> float:
        return self.space(self.base_pad)

    @property
    def gutter(self) -> float:
        return self.space(self.base_gutter)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sizes.py", description="Resolve a canvas size spec.")
    ap.add_argument("spec", nargs="?", help="WxH, a width, or a preset name")
    ap.add_argument("--kind-default", default="840x240", help="the kind's size, WxH")
    ap.add_argument("--list", action="store_true", help="print the presets")
    args = ap.parse_args(argv)
    if args.list:
        for name, p in SIZES.items():
            size = f"{p.width}x{p.height}" if p.height else f"{p.width} wide"
            print(f"{name:<16} {size:<10} {p.use}")
        return 0
    if not args.spec:
        ap.error("give a size spec or --list")
    try:
        base = resolve_size(args.kind_default, (840, 240))[:2]
        w, h, name = resolve_size(args.spec, base)
    except SizeError as exc:
        print(f"sizes.py: error: {exc}", file=sys.stderr)
        return 2
    print(f"{w}x{h}" + (f" ({name})" if name else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
