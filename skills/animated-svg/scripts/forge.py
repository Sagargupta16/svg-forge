#!/usr/bin/env python3
"""Generate self-contained animated SVGs for READMEs, docs and the web (stdlib only).

Kinds: tiles, hero, marquee, chart, bars, flow, loader, typing, divider, badge.

Every file is standalone: SMIL and CSS animation only, no script, no foreignObject, no
external fonts, images or links, system font stacks, role="img" with <title> and <desc>,
and ids plus CSS class names prefixed so several files can be inlined in one page. The same
input gives the same bytes (UTF-8, LF, trailing newline).

Timing presets:
  micro    120-300 ms one-shot feedback
  short    0.4-1.2 s one-shot entrance, 60-120 ms stagger, whole entrance under ~1.5 s
  medium   3-6 s seamless loop (mechanism scenes, pulses, packets on a path)
  long     8-20 s storyboard loop of 3-6 beats on one shared clock
  ambient  20-60 s drift or marquee, set by --speed in px/s (default 40)

Examples:
  python forge.py --kind flow --timing long --data pipeline.json --out flow.svg
  python forge.py --kind tiles --data '[{"value": "42", "label": "repos"}]' --out tiles.svg
  python forge.py --kind hero --theme both --accent "#a78bfa" --out hero.svg
  python forge.py --kind loader --variant dots --once --out dots.svg
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import html
import itertools
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SVG_NS = "http://www.w3.org/2000/svg"
DEFAULT_ACCENT = "#60a5fa"
EASE_OUT = "0.22 1 0.36 1"  # entrances: quick start, soft landing
EASE_IN_OUT = "0.45 0 0.25 1"  # line draws, bar growth and sliders: even pace
ELLIPSIS = "…"


class ForgeError(Exception):
    """Bad options or data; the CLI prints the message and exits 2."""


# ---------------------------------------------------------------- timing presets


@dataclass(frozen=True)
class Preset:
    """A timing preset: the range one cycle may take, and how one-shot entrances are paced."""

    name: str
    lo: float  # shortest cycle or entrance, seconds
    hi: float  # longest
    base: float  # what a kind gets when it has no content-driven target
    loop: bool  # loops unless --once
    item: float = 0.0  # one-shot: one item's entrance
    stagger: float = 0.0  # one-shot: delay between items
    total: float = 0.0  # one-shot: cap on the whole entrance

    def fit(self, seconds: float) -> float:
        return round(min(max(seconds, self.lo), self.hi), 3)


PRESETS: dict[str, Preset] = {
    "micro": Preset("micro", 0.12, 0.3, 0.24, False, item=0.18, stagger=0.02, total=0.3),
    "short": Preset("short", 0.4, 1.2, 0.6, False, item=0.45, stagger=0.09, total=1.5),
    "medium": Preset("medium", 3.0, 6.0, 4.8, True),
    "long": Preset("long", 8.0, 20.0, 12.0, True),
    "ambient": Preset("ambient", 20.0, 60.0, 30.0, True),
}
DEFAULT_SPEED = 40.0  # px/s for marquee scroll and ambient drift


@dataclass(frozen=True)
class Clock:
    """One shared timeline. Every animation starts at 0 and places its beats with keyTimes."""

    dur: float
    loop: bool

    @property
    def exit(self) -> float:
        """Fraction of a looping cycle spent fading the finished state out (see veil)."""
        return min(0.08, 0.45 / self.dur)

    def sub(self, target: float) -> Clock:
        """A faster clock that divides this one evenly, so its beats never drift."""
        return Clock(round(self.dur / max(1, round(self.dur / target)), 4), self.loop)

    def timing(self) -> dict[str, str]:
        out = {"dur": f"{num(self.dur, 3)}s"}
        out.update({"repeatCount": "indefinite"} if self.loop else {"fill": "freeze"})
        return out


# ---------------------------------------------------------------- theme tokens


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str  # card background, close to GitHub's page color for the theme
    wash: str  # top-left tint of the card gradient
    card: str  # raised panels and tiles
    ink: str  # headline text
    text: str  # body text
    dim: str  # labels
    border: str  # card outline
    panel: str  # node and track fill
    panel_stroke: str  # node and track outline
    grid: str  # background texture
    ok: str
    warn: str
    muted: str
    shine: float  # peak opacity of the white shine sweep


THEMES: dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        bg="#0b1012",
        wash="#0e1a24",
        card="#0f171c",
        ink="#f3f4f6",
        text="rgba(255,255,255,0.74)",
        dim="rgba(255,255,255,0.52)",
        border="rgba(255,255,255,0.09)",
        panel="rgba(255,255,255,0.04)",
        panel_stroke="rgba(255,255,255,0.16)",
        grid="rgba(255,255,255,0.035)",
        ok="#22c55e",
        warn="#f59e0b",
        muted="#9ca3af",
        shine=0.16,
    ),
    "light": Theme(
        name="light",
        bg="#ffffff",
        wash="#eef4fb",
        card="#f6f8fa",
        ink="#0b1012",
        text="rgba(11,16,18,0.76)",
        dim="rgba(11,16,18,0.58)",
        border="rgba(11,16,18,0.13)",
        panel="rgba(11,16,18,0.035)",
        panel_stroke="rgba(11,16,18,0.2)",
        grid="rgba(11,16,18,0.05)",
        ok="#15803d",
        warn="#b45309",
        muted="#4b5563",
        shine=0.55,
    ),
}
# Mid grey at low alpha reads on both GitHub themes; used by the transparent kinds.
NEUTRAL = "rgba(127,127,127,0.3)"

MONO = "'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"
SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
FONT_PRESETS = {
    "sans": SANS,
    "mono": MONO,
    "serif": "Georgia,'Times New Roman',Times,serif",
    "system": "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",
}
FONT_STACK = re.compile(r"[A-Za-z0-9 ,'\"._-]{1,200}")
HEX = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


@dataclass(frozen=True)
class Palette:
    ink: str  # accent for text and strokes, clamped to a lightness that reads on the theme
    deep: str  # darker shade for fills and rails


def parse_color(value: object, what: str = "--accent") -> str:
    """Return #rrggbb (lowercase) for #rgb or #rrggbb input, else raise ForgeError."""
    m = HEX.fullmatch(str(value).strip())
    if not m:
        raise ForgeError(f"{what} must be a hex color like #60a5fa or #6af, got {value!r}")
    h = m.group(1).lower()
    return "#" + (h if len(h) == 6 else "".join(ch * 2 for ch in h))


def _hls(hexcolor: str) -> tuple[float, float, float]:
    r, g, b = (int(hexcolor[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def _hex(h: float, light: float, sat: float) -> str:
    rgb = colorsys.hls_to_rgb(h, min(max(light, 0.0), 1.0), min(max(sat, 0.0), 1.0))
    return "#" + "".join(f"{round(ch * 255):02x}" for ch in rgb)


def ink_for(hexcolor: str, theme: Theme) -> str:
    """The color as ink: at least 60% lightness on dark, at most 42% on light."""
    h, light, sat = _hls(hexcolor)
    target = max(light, 0.6) if theme.name == "dark" else min(light, 0.42)
    return hexcolor if target == light else _hex(h, target, sat)


def palette(accent: str, theme: Theme) -> Palette:
    h, light, sat = _hls(accent)
    return Palette(ink=ink_for(accent, theme), deep=_hex(h, light - 0.15, sat * 0.9))


def alpha(hexcolor: str, a: float) -> str:
    r, g, b = (int(hexcolor[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{num(a, 3)})"


# ---------------------------------------------------------------- text measurement

# Average advance per character as a fraction of the font size for the default stacks
# (Segoe UI / Inter / Helvetica for sans, JetBrains Mono / Consolas / Menlo for mono),
# rounded up so estimates run a little wide and text never spills out of its box.
# Px per character before letter-spacing, at common sizes:
#   mono  8.5 px -> 5.3   9 px -> 5.6   11 px -> 6.8   13 px -> 8.1
#   sans  12 px -> 6.7   18 px -> 10.1
#   bold  26 px -> 15.6  (sans 800, digits and mixed case)
#   caps  10 px -> 7.0   (sans uppercase)
# The mono class adds MONO_LS px of letter-spacing per character on top.
EM = {"mono": 0.62, "sans": 0.56, "bold": 0.6, "caps": 0.7}
MONO_LS = 1.2


def text_width(text: str, size: float, face: str = "sans", spacing: float = 0.0) -> float:
    return len(text) * (size * EM[face] + spacing)


def fit(text: str, max_w: float, size: float, face: str = "sans", spacing: float = 0.0) -> str:
    """Return text, cut with an ellipsis when its estimated width passes max_w."""
    if text_width(text, size, face, spacing) <= max_w:
        return text
    per = size * EM[face] + spacing
    keep = max(int(max_w / per) - 1, 1)
    return text[:keep].rstrip() + ELLIPSIS


def shrink(
    text: str, max_w: float, size: float, face: str, floor: float, spacing: float = 0.0
) -> tuple[str, float]:
    """Step the font size down to floor until text fits, then truncate what still does not."""
    while size > floor and text_width(text, size, face, spacing) > max_w:
        size -= 1
    return fit(text, max_w, size, face, spacing), size


# Control characters XML 1.0 forbids are dropped; dashes from U+2012 to U+2015 become "-".
_CLEAN: dict[int, str | None] = {cp: None for cp in (*range(9), 11, 12, *range(14, 32))}
_CLEAN.update({0xFFFE: None, 0xFFFF: None, 9: " ", 10: " ", 13: " "})
_CLEAN.update(dict.fromkeys(range(0x2012, 0x2016), "-"))


def clean(text: str) -> str:
    out = "".join(ch for ch in text.translate(_CLEAN) if not 0xD800 <= ord(ch) <= 0xDFFF)
    return re.sub(r" {2,}", " ", out)


# ---------------------------------------------------------------- svg builder


def num(value: float, places: int = 2) -> str:
    """Fixed-precision number without trailing zeros, so output bytes are stable."""
    text = f"{value:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def esc(text: object) -> str:
    """Escape text content; every interpolated string goes through here or el()."""
    return html.escape(clean(str(text)), quote=True)


def el(name: str, *children: str, **attrs: object) -> str:
    """One element. Keyword names map class_ -> class and font_size -> font-size."""
    head = [name]
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = num(value)
        head.append(f'{key.rstrip("_").replace("_", "-")}="{html.escape(str(value), quote=True)}"')
    tag = " ".join(head)
    return f"<{tag}>{''.join(children)}</{name}>" if children else f"<{tag}/>"


def fmt(value: object) -> str:
    if isinstance(value, tuple):
        return " ".join(fmt(v) for v in value)
    if isinstance(value, (int, float)):
        return num(value, 3)
    return str(value)


def keyed(frames: list[tuple[float, object]], clock: Clock) -> tuple[str, str]:
    """keyTimes and values for (cycle fraction, value) frames.

    On a looping clock, a timeline that ends away from where it started is sent home in
    the last third of the exit window, while veil() keeps the layer hidden. A final frame
    placed at 1.0 opts out: the value then jumps back as the next cycle begins.
    """
    pts: list[tuple[float, str]] = []
    for t, v in frames:
        point = (round(min(max(float(t), 0.0), 1.0), 4), fmt(v))
        if pts and point[0] < pts[-1][0]:
            point = (pts[-1][0], point[1])
        if not pts or point != pts[-1]:
            pts.append(point)
    if pts[0][0] > 0:
        pts.insert(0, (0.0, pts[0][1]))
    first, (end, last) = pts[0][1], pts[-1]
    if clock.loop and last != first and end < 1:
        home = round(max(end, 1 - clock.exit / 3), 4)
        if home > end:
            pts.append((home, last))
        pts.append((1.0, first))
    elif end < 1:
        pts.append((1.0, last))
    return ";".join(num(t, 4) for t, _ in pts), ";".join(v for _, v in pts)


def _mode(times: str, ease: bool | str, discrete: bool) -> dict[str, str]:
    if discrete:
        return {"calcMode": "discrete"}
    if ease:
        curve = ease if isinstance(ease, str) else EASE_OUT
        return {"calcMode": "spline", "keySplines": ";".join([curve] * times.count(";"))}
    return {}


def animate(
    attr: str,
    frames: list[tuple[float, object]],
    clock: Clock,
    *,
    ease: bool | str = False,
    discrete: bool = False,
) -> str:
    times, values = keyed(frames, clock)
    return el(
        "animate",
        attributeName=attr,
        values=values,
        keyTimes=times,
        **_mode(times, ease, discrete),
        **clock.timing(),
    )


def move(
    kind: str,
    frames: list[tuple[float, object]],
    clock: Clock,
    *,
    ease: bool | str = False,
    additive: str | None = None,
) -> str:
    """animateTransform of the given type (translate, scale, rotate) over the clock."""
    times, values = keyed(frames, clock)
    return el(
        "animateTransform",
        attributeName="transform",
        type=kind,
        values=values,
        keyTimes=times,
        additive=additive,
        **_mode(times, ease, False),
        **clock.timing(),
    )


def ride(path: str, a: float, b: float, clock: Clock) -> str:
    """animateMotion carrying its parent along path between cycle fractions a and b."""
    return el(
        "animateMotion",
        path=path,
        keyPoints="0;0;1;1",
        keyTimes=f"0;{num(a, 4)};{num(b, 4)};1",
        calcMode="linear",
        **clock.timing(),
    )


def window(a: float, b: float, ramp: float) -> list[tuple[float, object]]:
    """Opacity frames: hidden, visible from a to b with ramp-long fades, hidden again."""
    return [(0, 0), (a, 0), (a + ramp, 1), (b - ramp, 1), (b, 0)]


def rise(clock: Clock, begin: float, dur: float, dy: float = 10.0) -> str:
    """Fade in while sliding up dy px, from begin for dur seconds."""
    a, b = begin / clock.dur, (begin + dur) / clock.dur
    return animate("opacity", [(0, 0), (a, 0), (b, 1)], clock, ease=True) + move(
        "translate", [(0, (0, dy)), (a, (0, dy)), (b, (0, 0))], clock, ease=True
    )


def veil(clock: Clock) -> str:
    """Fade a built-up layer out at the end of each loop so its reset is never seen."""
    if not clock.loop:
        return ""
    e = clock.exit
    return el(
        "animate",
        attributeName="opacity",
        values="1;1;0;0",
        keyTimes=f"0;{num(1 - e, 4)};{num(1 - e / 3, 4)};1",
        **clock.timing(),
    )


# ---------------------------------------------------------------- render context


@dataclass
class Art:
    """What a kind returns: canvas size, accessible text and markup."""

    width: float
    height: float
    title: str
    desc: str
    body: list[str] = field(default_factory=list)
    defs: list[str] = field(default_factory=list)
    css: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Ctx:
    kind: str
    theme: Theme
    pal: Palette
    preset: Preset
    loop: bool
    speed: float
    width: float | None
    height: float | None
    title: str | None
    desc: str | None
    data: Any
    variant: str | None
    prefix: str
    sans: str
    reduced: str

    def id(self, name: str) -> str:
        return f"{self.prefix}{name}"

    def url(self, name: str) -> str:
        return f"url(#{self.prefix}{name})"

    def cls(self, name: str) -> str:
        return f"{self.prefix}{name}"

    @property
    def one_shot(self) -> bool:
        return not self.preset.loop

    def cycle(self, target: float, distance: float | None = None) -> Clock:
        """Loop clock: target seconds fitted to the preset, or distance / speed for ambient."""
        p = self.preset
        if p.name == "ambient":
            return Clock(p.fit(distance / self.speed if distance else p.base), self.loop)
        return Clock((p if p.loop else PRESETS["medium"]).fit(target), self.loop)

    def entrance(self, n: int, item: float | None = None) -> tuple[Clock, list[float], float]:
        """Clock, begin times and duration for n staggered one-shot entrances."""
        p = self.preset if self.one_shot else PRESETS["short"]
        dur = min(p.item if item is None else item, p.total)
        start = 0.1 if p.name == "short" else 0.0
        stagger = p.stagger
        if n > 1:
            stagger = min(stagger, max(0.0, (p.total - start - dur) / (n - 1)))
        total = round(start + dur + stagger * (n - 1), 3)
        clock = (
            Clock(PRESETS["medium"].fit(total + 2.4), True) if self.loop else Clock(total, False)
        )
        return clock, [round(start + i * stagger, 3) for i in range(n)], dur

    def tone(self, name: object) -> str:
        if name in (None, "", "accent"):
            return self.pal.ink
        if name in ("ok", "warn", "muted"):
            return getattr(self.theme, str(name))
        return ink_for(parse_color(name, "tone"), self.theme)


def spec_of(c: Ctx, list_key: str) -> dict[str, Any]:
    """The kind's data as a dict; a bare JSON list becomes {list_key: list}."""
    raw = SAMPLES[c.kind] if c.data is None else c.data
    if isinstance(raw, list):
        return {list_key: raw}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return {list_key: [raw]}
    raise ForgeError(f"--data for {c.kind} must be a JSON object or list")


def need_list(value: object, what: str, limit: int, least: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < least:
        raise ForgeError(f"{what} must be a JSON list with at least {least} item(s)")
    if len(value) > limit:
        raise ForgeError(f"{what} takes at most {limit} items, got {len(value)}")
    return value


def text_of(value: object, what: str, limit: int = 160) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ForgeError(f"{what} must be text, got {value!r}")
    return clean(str(value)).strip()[:limit]


def number_of(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ForgeError(f"{what} must be a finite number, got {value!r}")
    return float(value)


def frame(c: Ctx, art: Art, *, rx: float = 14, solid: bool = False) -> None:
    """Card background: theme gradient (or solid bg) with a hairline border."""
    fill = c.theme.bg
    if not solid:
        art.defs.append(
            el(
                "linearGradient",
                el("stop", offset=0, stop_color=c.theme.wash),
                el("stop", offset=0.6, stop_color=c.theme.bg),
                id=c.id("bg"),
                x1=0,
                y1=0,
                x2=0.6,
                y2=1,
            )
        )
        fill = c.url("bg")
    art.body.append(
        el(
            "rect",
            x=0.5,
            y=0.5,
            width=art.width - 1,
            height=art.height - 1,
            rx=rx,
            fill=fill,
            stroke=c.theme.border,
        )
    )


def heading(c: Ctx, art: Art, text: str, x: float = 20, y: float = 28) -> None:
    label = fit(text.upper(), art.width - 2 * x, 10, "mono", MONO_LS)
    art.body.append(
        el("text", esc(label), class_=c.cls("m"), x=x, y=y, fill=c.pal.ink, font_size=10)
    )


def mono(c: Ctx, text: str, x: float, y: float, fill: str, size: float, **extra: object) -> str:
    return el("text", esc(text), class_=c.cls("m"), x=x, y=y, fill=fill, font_size=size, **extra)


# ---------------------------------------------------------------- kinds


def kind_tiles(c: Ctx) -> Art:
    """Stat tiles in a grid: staggered entrance one-shot, or a spotlight cycling the tiles."""
    spec = spec_of(c, "items")
    items = []
    for i, raw in enumerate(need_list(spec.get("items"), "tiles items", 16)):
        if not isinstance(raw, dict):
            raise ForgeError(f"tiles item {i} must be an object with value and label")
        items.append(
            {
                "value": text_of(raw.get("value", ""), f"tiles item {i} value", 24),
                "label": text_of(raw.get("label", ""), f"tiles item {i} label", 60),
                "tone": raw.get("tone"),
            }
        )
    n = len(items)
    cols = int(number_of(spec.get("cols", min(n, 4)), "tiles cols"))
    if not 1 <= cols <= 8:
        raise ForgeError("tiles cols must be between 1 and 8")
    rows = math.ceil(n / cols)
    title = c.title or (text_of(spec["title"], "tiles title") if spec.get("title") else "")
    w = c.width or 840
    pad, gap = 16, 12
    top = pad + (28 if title else 0)
    th = 80.0 if c.height is None else max(48.0, (c.height - top - pad - (rows - 1) * gap) / rows)
    h = c.height or top + rows * th + (rows - 1) * gap + pad
    tw = (w - 2 * pad - (cols - 1) * gap) / cols
    art = Art(w, h, title or "Stat tiles", "; ".join(f"{t['value']} {t['label']}" for t in items))
    frame(c, art)
    if title:
        heading(c, art, title, x=pad + 4, y=pad + 14)
    if c.one_shot:
        clock, begins, item = c.entrance(n)
    else:
        clock, begins, item = c.cycle(c.preset.base, distance=w), [], 0.0
    layer = []
    for i, t in enumerate(items):
        x = pad + (i % cols) * (tw + gap)
        y = top + (i // cols) * (th + gap)
        color = c.tone(t["tone"])
        value, size = shrink(t["value"], tw - 32, min(26.0, th * 0.34), "bold", 13)
        label = fit(t["label"].upper(), tw - 32, 8.5, "mono", MONO_LS)
        inner = [
            el(
                "rect",
                x=x,
                y=y,
                width=tw,
                height=th,
                rx=12,
                fill=c.theme.card,
                stroke=c.theme.border,
            ),
            el("rect", x=x, y=y + th * 0.22, width=3, height=th * 0.34, rx=1.5, fill=color),
            el(
                "text",
                esc(value),
                class_=c.cls("b"),
                x=x + 18,
                y=y + th * 0.53,
                fill=c.theme.ink,
                font_size=size,
            ),
            mono(c, label, x + 18, y + th * 0.8, c.theme.dim, 8.5),
        ]
        if c.one_shot:
            layer.append(el("g", rise(clock, begins[i], item), *inner))
            continue
        layer.extend(inner)
        a, b = i / n, (i + 1) / n
        ramp = min((b - a) / 3, 0.35 / clock.dur)
        layer.append(
            el(
                "rect",
                animate("opacity", window(a, b, ramp), clock),
                x=x + 0.5,
                y=y + 0.5,
                width=tw - 1,
                height=th - 1,
                rx=11.5,
                fill=alpha(color if color.startswith("#") else c.pal.ink, 0.06),
                stroke=color,
                stroke_width=1.2,
                opacity=0,
            )
        )
    art.body.append(el("g", veil(clock) if c.one_shot else "", *layer))
    return art


def rotating(c: Ctx, lines: list[str], clock: Clock, **attrs: object) -> list[str]:
    """Lines taking turns on one clock; on a one-shot clock the last line stays.

    Static renderers see one line: the first when looping, the last when played once.
    """
    n = len(lines)
    if n == 1:
        return [el("text", esc(lines[0]), **attrs)]
    out = []
    ramp = min(0.04, 1 / (4 * n))
    poster = 0 if clock.loop else n - 1
    for i, text in enumerate(lines):
        a, b = i / n, (i + 1) / n
        frames: list[tuple[float, object]] = [(a, 0), (a + ramp, 1)]
        if clock.loop or i < n - 1:
            frames += [(b - ramp, 1), (b, 0)]
        hidden = None if i == poster else 0
        out.append(
            el("text", esc(text), animate("opacity", frames, clock), **attrs, opacity=hidden)
        )
    return out


def kind_hero(c: Ctx) -> Art:
    """Title, rotating taglines, a status pill and a node constellation with packets."""
    spec = spec_of(c, "taglines")
    title = c.title or text_of(spec.get("title", "Hello"), "hero title", 60)
    kicker = text_of(spec.get("kicker", ""), "hero kicker", 40)
    taglines = [text_of(t, "hero tagline", 90) for t in spec.get("taglines", [])][:6]
    status = text_of(spec.get("status", ""), "hero status", 40)
    meta = text_of(spec.get("meta", ""), "hero meta", 40)
    nodes = [text_of(t, "hero node", 8) for t in spec.get("nodes", [])][:8]
    w = c.width or 840
    h = c.height or 250
    show_nodes = len(nodes) >= 2 and w >= 560
    left = w * 0.6 if show_nodes else w - 80
    desc = ". ".join(x for x in (kicker, title, *taglines, status, meta) if x)
    art = Art(w, h, title, desc)
    p = c.theme
    art.defs += [
        el(
            "pattern",
            el("path", d="M24 0H0V24", fill="none", stroke=p.grid, stroke_width=1),
            id=c.id("grid"),
            width=24,
            height=24,
            patternUnits="userSpaceOnUse",
        ),
        el(
            "linearGradient",
            el("stop", offset=0, stop_color=c.pal.ink, stop_opacity=0),
            el("stop", offset=0.5, stop_color=c.pal.ink, stop_opacity=0.1),
            el("stop", offset=1, stop_color=c.pal.ink, stop_opacity=0),
            id=c.id("scan"),
            x1=0,
            x2=1,
        ),
        el("clipPath", el("rect", x=1, y=1, width=w - 2, height=h - 2, rx=18), id=c.id("card")),
    ]
    frame(c, art, rx=18)
    one = c.one_shot
    clock = c.cycle(max(len(taglines), 1) * 3.0, distance=w * 1.5)
    backdrop = [el("rect", width=w, height=h, fill=c.url("grid"))]
    if not one:
        scan = clock.sub(7.0)
        backdrop.append(
            el(
                "rect",
                move("translate", [(0, (0, 0)), (1, (w + 400, 0))], scan),
                x=-200,
                y=0,
                width=200,
                height=h,
                fill=c.url("scan"),
            )
        )
    art.body.append(el("g", *backdrop, clip_path=c.url("card")))

    s = h / 250
    x0 = 44
    size_title = min(58.0, h * 0.23)
    name, size_title = shrink(title, left - x0 - 12, size_title, "bold", 22)
    parts: list[list[str]] = []
    if kicker:
        parts.append(
            [mono(c, fit(kicker.upper(), left - x0, 11, "mono", 2), x0, 62 * s, c.pal.ink, 11)]
        )
    parts.append(
        [
            el(
                "text",
                esc(name),
                class_=c.cls("b"),
                x=x0 - 4,
                y=118 * s,
                fill=p.ink,
                font_size=size_title,
                letter_spacing=-1,
            )
        ]
    )
    tag_attrs = {"class_": c.cls("s"), "x": x0, "y": 152 * s, "fill": p.text, "font_size": 18}
    fitted = [fit(t, left - x0 - 8, 18, "sans") for t in taglines]
    if fitted:
        if one:
            parts.append([el("text", esc(fitted[0]), **tag_attrs)])
        else:
            parts.append(rotating(c, fitted, clock, **tag_attrs))
    if status:
        pill_w = text_width(status.upper(), 10, "mono", 1.0) + 46
        pulse = c.cycle(1.8).sub(1.8) if not one else None
        dot = el("circle", cx=x0 + 18, cy=190 * s, r=4, fill=p.ok)
        if pulse:
            dot = el(
                "circle",
                animate("opacity", [(0, 1), (0.5, 0.35), (1, 1)], clock.sub(1.8)),
                cx=x0 + 18,
                cy=190 * s,
                r=4,
                fill=p.ok,
            )
        pill = [
            el(
                "rect",
                x=x0,
                y=176 * s,
                width=pill_w,
                height=28,
                rx=14,
                fill=alpha(p.ok, 0.08),
                stroke=alpha(p.ok, 0.35),
            ),
            dot,
            mono(c, status.upper(), x0 + 30, 176 * s + 18, p.ok, 10, letter_spacing=1),
        ]
        if meta:
            meta_x = x0 + pill_w + 16
            room = left - meta_x
            pill.append(
                mono(c, fit(meta.upper(), room, 10, "mono", 1.0), meta_x, 176 * s + 18, p.dim, 10)
            )
        parts.append(pill)
    if show_nodes:
        parts.append(constellation(c, nodes, left, w, h, clock, one))

    if one:
        ent, begins, item = c.entrance(len(parts))
        group = [el("g", rise(ent, begins[i], item), *part) for i, part in enumerate(parts)]
        art.body.append(el("g", veil(ent), *group))
    else:
        art.body += [x for part in parts for x in part]
    return art


def constellation(
    c: Ctx, nodes: list[str], left: float, w: float, h: float, clock: Clock, one: bool
) -> list[str]:
    """Hub (first node) ringed by the rest, with packets riding out along the spokes."""
    p = c.theme
    cx, cy = left + (w - left) / 2, h / 2
    rx, ry = min((w - left) / 2 - 30, 150), h / 2 - 46
    ring = nodes[1:]
    m = len(ring)
    pos = [
        (
            cx + rx * math.cos(-math.pi / 2 + 2 * math.pi * k / m + 0.35),
            cy + ry * math.sin(-math.pi / 2 + 2 * math.pi * k / m + 0.35),
        )
        for k in range(m)
    ]
    out = []
    links = [((cx, cy), q) for q in pos]
    if m >= 3:
        links += [(pos[k], pos[(k + 1) % m]) for k in range(m)]
    for (x1, y1), (x2, y2) in links:
        out.append(el("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=p.panel_stroke, stroke_width=1))
    if not one:
        lane = clock.sub(2.4)
        for k, (x2, y2) in enumerate(pos):
            a = 0.5 * k / m
            path = f"M{num(cx)} {num(cy)} L{num(x2)} {num(y2)}"
            out.append(
                el(
                    "circle",
                    animate("opacity", window(a, a + 0.5, 0.06), lane),
                    ride(path, a, a + 0.5, lane),
                    r=2.6,
                    fill=c.pal.ink,
                    opacity=0,
                )
            )
    breathe = clock.sub(3.0)
    for k, (label, (x, y)) in enumerate(zip(nodes, [(cx, cy), *pos], strict=True)):
        hub = k == 0
        r = 22 if hub else 17
        anim = ""
        if not one:
            a = (k % 4) / 8
            anim = animate("r", [(0, r), (a, r), (a + 0.5, r + 1.5), (1, r)], breathe)
        out.append(
            el(
                "circle",
                anim,
                cx=x,
                cy=y,
                r=r,
                fill=alpha(c.pal.deep, 0.18) if hub else p.card,
                stroke=alpha(c.pal.ink, 0.85) if hub else p.panel_stroke,
                stroke_width=1.3,
            )
        )
        text = fit(label.upper(), 2 * r - 6, 8.5, "mono", 0.6)
        out.append(
            mono(
                c,
                text,
                x,
                y + 3,
                c.pal.ink if hub else p.text,
                8.5,
                text_anchor="middle",
                letter_spacing=0.6,
            )
        )
    return out


def kind_marquee(c: Ctx) -> Art:
    """Rows of text chips scrolling seamlessly at a constant speed (rows alternate direction)."""
    spec = spec_of(c, "items")
    rows_raw = spec.get("rows") or [spec.get("items")]
    rows = [
        [text_of(t, "marquee item", 40) for t in need_list(r, "marquee row", 60)]
        for r in need_list(rows_raw, "marquee rows", 3)
    ]
    w = c.width or 840
    chip_h, row_gap, pad, gap, size = 28, 12, 14, 10, 11
    h = c.height or pad * 2 + len(rows) * chip_h + (len(rows) - 1) * row_gap
    flat = [t for r in rows for t in r]
    art = Art(w, h, c.title or "Marquee", "Scrolling list: " + ", ".join(flat))
    p = c.theme
    frame(c, art, solid=True)
    art.defs += [
        el("clipPath", el("rect", x=1, y=1, width=w - 2, height=h - 2, rx=13), id=c.id("win")),
        el(
            "linearGradient",
            el("stop", offset=0, stop_color=p.bg),
            el("stop", offset=0.07, stop_color=p.bg, stop_opacity=0),
            el("stop", offset=0.93, stop_color=p.bg, stop_opacity=0),
            el("stop", offset=1, stop_color=p.bg),
            id=c.id("fade"),
            x1=0,
            x2=1,
        ),
    ]
    layer = []
    for r, items in enumerate(rows):
        color = c.pal.ink if r % 2 == 0 else p.muted
        chips = []
        for t in items:
            label = fit(t, 216, size, "mono", MONO_LS)
            chips.append((label, text_width(label, size, "mono", MONO_LS) + 26))
        span = sum(cw + gap for _, cw in chips)
        reps = max(1, math.ceil(w / span))
        chips, span = chips * reps, span * reps
        y = pad + r * (chip_h + row_gap)
        copies = 1 if c.one_shot else 2
        seq = []
        x = 0.0
        for label, cw in chips * copies:
            seq.append((x, label, cw))
            x += cw + gap
        if c.one_shot:
            seq = [s for s in seq if s[0] < w]
        drawn = [
            el(
                "g",
                el(
                    "rect",
                    x=cx + 0.5,
                    y=y + 0.5,
                    width=cw - 1,
                    height=chip_h - 1,
                    rx=(chip_h - 1) / 2,
                    fill=alpha(color, 0.08),
                    stroke=alpha(color, 0.35),
                ),
                mono(c, label, cx + cw / 2, y + chip_h / 2 + 4, color, size, text_anchor="middle"),
            )
            for cx, label, cw in seq
        ]
        if c.one_shot:
            clock, begins, item = c.entrance(len(drawn))
            drawn = [el("g", rise(clock, begins[i], item, dy=6), d) for i, d in enumerate(drawn)]
            layer.append(el("g", veil(clock), *drawn, transform=f"translate({pad} 0)"))
            continue
        seconds = span / c.speed
        clock = Clock(
            round(seconds if c.preset.name == "ambient" else c.preset.fit(seconds), 3), c.loop
        )
        start, end = (0, -span) if r % 2 == 0 else (-span, 0)
        layer.append(el("g", move("translate", [(0, (start, 0)), (1, (end, 0))], clock), *drawn))
    art.body.append(el("g", *layer, clip_path=c.url("win")))
    art.body.append(el("rect", x=0.5, y=0.5, width=w - 1, height=h - 1, rx=14, fill=c.url("fade")))
    return art


def fmt_value(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}k".replace(".0k", "k")
    return num(v, 0 if abs(v) >= 100 else 1)


def kind_chart(c: Ctx) -> Art:
    """Line chart that draws itself in, the area under it, and a marked peak."""
    spec = spec_of(c, "values")
    values = [
        number_of(v, "chart value") for v in need_list(spec.get("values"), "chart values", 400, 2)
    ]
    labels = [text_of(t, "chart label", 16) for t in spec.get("labels", [])]
    title = c.title or (text_of(spec["title"], "chart title") if spec.get("title") else "")
    peak_word = text_of(spec.get("peak", "PEAK"), "chart peak", 12)
    unit = text_of(spec.get("unit", ""), "chart unit", 6)
    w = c.width or 600
    h = c.height or 240
    x0, x1 = 24, w - 58
    y0, y1 = (58 if title else 30), h - (34 if labels else 22)
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    n = len(values)
    pts = [
        (x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (v - lo) / span)
        for i, v in enumerate(values)
    ]
    line = "M" + " L".join(f"{num(x)} {num(y)}" for x, y in pts)
    length = sum(math.dist(a, b) for a, b in itertools.pairwise(pts)) * 1.02 + 2
    area = f"{line} L{num(x1)} {num(y1)} L{num(x0)} {num(y1)} Z"
    peak = values.index(hi)
    px, py = pts[peak]
    lx, ly = pts[-1]
    first, last = fmt_value(values[0]) + unit, fmt_value(values[-1]) + unit
    desc = f"Line chart of {n} points from {first} to {last}, peak {fmt_value(hi)}{unit}."
    art = Art(w, h, title or "Line chart", desc)
    p = c.theme
    frame(c, art)
    if title:
        heading(c, art, title, x=24, y=32)
    art.defs.append(
        el(
            "linearGradient",
            el("stop", offset=0, stop_color=c.pal.ink, stop_opacity=0.26),
            el("stop", offset=1, stop_color=c.pal.ink, stop_opacity=0),
            id=c.id("area"),
            x1=0,
            y1=0,
            x2=0,
            y2=1,
        )
    )
    for frac in (0, 0.5, 1):
        y = y1 - (y1 - y0) * frac
        art.body.append(el("line", x1=x0, y1=y, x2=x1, y2=y, stroke=p.grid if frac else p.border))
        art.body.append(mono(c, fmt_value(lo + span * frac) + unit, x1 + 8, y + 3, p.dim, 8))
    if labels:
        art.body.append(mono(c, labels[0], x0, h - 14, p.dim, 8))
        art.body.append(mono(c, labels[-1], x1, h - 14, p.dim, 8, text_anchor="end"))
    if c.one_shot:
        start = 0.1 if c.preset.name == "short" else 0.0
        draw = 1.1 if c.preset.name == "short" else 0.24
        total = start + draw + 0.3
        clock = Clock(PRESETS["medium"].fit(total + 2.4), True) if c.loop else Clock(total, False)
    else:
        clock = c.cycle(c.preset.base, distance=length)
        start, draw = 0.04 * clock.dur, 0.46 * clock.dur
    d = clock.dur
    a, b = start / d, (start + draw) / d
    label = f"{peak_word} {fmt_value(hi)}{unit}"
    tx, anchor = (
        (px - 8, "end")
        if px - 8 - text_width(label, 9, "mono", MONO_LS) >= 12
        else (px + 8, "start")
    )
    show = [(0, 0), (b, 0), (min(b + 0.25 / d, 1), 1)]
    ring_cls = None
    if clock.loop:
        ring = clock.sub(2.2)
        ring_cls = c.cls("ring")
        art.css.append(
            f".{ring_cls}{{animation:{ring_cls} {num(ring.dur, 3)}s ease-out infinite;"
            "transform-origin:center;transform-box:fill-box}"
            f"@keyframes {ring_cls}{{0%{{opacity:.9;transform:scale(1)}}"
            "100%{opacity:0;transform:scale(2.6)}}"
        )
    built = [
        el(
            "path",
            animate("opacity", [(0, 0), (b - 0.05, 0), (b + 0.1, 1)], clock),
            d=area,
            fill=c.url("area"),
        ),
        el(
            "path",
            animate(
                "stroke-dashoffset",
                [(0, num(length)), (a, num(length)), (b, 0)],
                clock,
                ease=EASE_IN_OUT,
            ),
            d=line,
            fill="none",
            stroke=c.pal.ink,
            stroke_width=2,
            stroke_linejoin="round",
            stroke_linecap="round",
            stroke_dasharray=num(length),
            stroke_dashoffset=0,
        ),
        el(
            "g",
            animate("opacity", show, clock),
            el(
                "circle",
                class_=ring_cls,
                cx=px,
                cy=py,
                r=5,
                fill="none",
                stroke=c.pal.ink,
                stroke_width=1.5,
            ),
            el("circle", cx=lx, cy=ly, r=3.5, fill=c.pal.ink),
            mono(c, label, tx, py - 10, c.pal.ink, 9, text_anchor=anchor),
        ),
    ]
    art.body.append(el("g", veil(clock), *built))
    return art


def kind_bars(c: Ctx) -> Art:
    """Labelled progress bars that grow from zero, staggered."""
    spec = spec_of(c, "items")
    unit = text_of(spec.get("unit", "%"), "bars unit", 6)
    items = []
    for i, raw in enumerate(need_list(spec.get("items"), "bars items", 12)):
        if not isinstance(raw, dict):
            raise ForgeError(f"bars item {i} must be an object with label and value")
        value = number_of(raw.get("value", 0), f"bars item {i} value")
        top = number_of(raw.get("max", 100), f"bars item {i} max")
        if top <= 0:
            raise ForgeError(f"bars item {i} max must be above 0")
        shown = (
            f"{fmt_value(value)}/{fmt_value(top)}" if "max" in raw else f"{fmt_value(value)}{unit}"
        )
        items.append(
            {
                "label": text_of(raw.get("label", ""), f"bars item {i} label", 40),
                "frac": min(max(value / top, 0.0), 1.0),
                "shown": shown,
                "tone": raw.get("tone"),
            }
        )
    title = c.title or (text_of(spec["title"], "bars title") if spec.get("title") else "")
    n = len(items)
    w = c.width or 600
    top_y = 50 if title else 22
    row = 36
    h = c.height or top_y + n * row + 4
    pad = 24
    tw = w - 2 * pad
    art = Art(
        w, h, title or "Progress bars", "; ".join(f"{t['label']} {t['shown']}" for t in items)
    )
    p = c.theme
    frame(c, art)
    if title:
        heading(c, art, title, x=pad, y=30)
    if c.one_shot:
        clock, begins, item = c.entrance(n, item=0.9 if c.preset.name == "short" else None)
    else:
        clock = c.cycle(c.preset.base, distance=tw)
        step = min(0.06, 0.3 / max(n - 1, 1))
        begins = [(0.04 + i * step) * clock.dur for i in range(n)]
        item = 0.3 * clock.dur
    fills = []
    for i, t in enumerate(items):
        y = top_y + i * row + 12
        color = c.tone(t["tone"])
        art.body.append(
            mono(c, fit(t["label"].upper(), tw * 0.7, 9, "mono", MONO_LS), pad, y, p.dim, 9)
        )
        art.body.append(mono(c, t["shown"], pad + tw, y, p.text, 9, text_anchor="end"))
        art.body.append(
            el("rect", x=pad, y=y + 7, width=tw, height=6, rx=3, fill=p.panel_stroke, opacity=0.5)
        )
        if t["frac"] <= 0:
            continue
        a, b = begins[i] / clock.dur, (begins[i] + item) / clock.dur
        grow = move("scale", [(0, (0, 1)), (a, (0, 1)), (b, (1, 1))], clock, ease=EASE_IN_OUT)
        fills.append(
            el(
                "g",
                el(
                    "rect",
                    grow,
                    width=tw * t["frac"],
                    height=6,
                    rx=3,
                    fill=color,
                ),
                transform=f"translate({num(pad)} {num(y + 7)})",
            )
        )
    art.body.append(el("g", veil(clock), *fills))
    return art


@dataclass
class Node:
    id: str
    label: str
    tone: object
    rank: int = 0
    x: float = 0.0
    y: float = 0.0
    fx: float | None = None
    fy: float | None = None


def cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> list[tuple[float, float]]:
    pts = []
    for i in range(49):
        t = i / 48
        u = 1 - t
        pts.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return pts


def flow_graph(spec: dict[str, Any]) -> tuple[list[Node], list[tuple[str, str, str]]]:
    nodes: list[Node] = []
    seen: set[str] = set()
    for i, raw in enumerate(need_list(spec.get("nodes"), "flow nodes", 12, 2)):
        if isinstance(raw, dict):
            nid = text_of(raw.get("id", raw.get("label", "")), f"flow node {i} id", 40)
            label = text_of(raw.get("label", nid), f"flow node {i} label", 40)
            fx = number_of(raw["x"], "flow node x") if "x" in raw else None
            fy = number_of(raw["y"], "flow node y") if "y" in raw else None
            node = Node(nid, label, raw.get("tone"), fx=fx, fy=fy)
        else:
            nid = text_of(raw, f"flow node {i}", 40)
            node = Node(nid, nid, None)
        if not nid or nid in seen:
            raise ForgeError(f"flow node ids must be unique and non-empty, got {nid!r}")
        seen.add(nid)
        nodes.append(node)
    edges = []
    for i, raw in enumerate(need_list(spec.get("edges", []), "flow edges", 16, 0)):
        if isinstance(raw, dict):
            raw = [raw.get("from"), raw.get("to"), raw.get("label", "")]
        if not isinstance(raw, list) or len(raw) not in (2, 3):
            raise ForgeError(f"flow edge {i} must be [from, to] or [from, to, label]")
        a, b = text_of(raw[0], "edge from"), text_of(raw[1], "edge to")
        label = text_of(raw[2], "edge label", 24) if len(raw) == 3 else ""
        if a not in seen or b not in seen or a == b:
            raise ForgeError(
                f"flow edge {i} must join two different known nodes, got {a!r} -> {b!r}"
            )
        edges.append((a, b, label))
    return nodes, edges


def kind_flow(c: Ctx) -> Art:
    """Nodes joined by paths with packets riding them: pipeline or architecture diagram.

    List nodes in flow order. Edges to a later node are forward and set the columns (longest
    path); an edge to an earlier node is a return arc drawn under the diagram. On a loop clock
    the diagram plays as a storyboard: one beat per column, packets travel into each column,
    its nodes light up, return arcs run last, then everything fades and the loop restarts.
    """
    spec = spec_of(c, "nodes")
    nodes, edges = flow_graph(spec)
    index = {n.id: i for i, n in enumerate(nodes)}
    by_id = {n.id: n for n in nodes}
    forward = [e for e in edges if index[e[0]] < index[e[1]]]
    back = [e for e in edges if index[e[0]] > index[e[1]]]
    for node in nodes:
        for a, b, _ in forward:
            if b == node.id:
                node.rank = max(node.rank, by_id[a].rank + 1)
    ranks = max(n.rank for n in nodes) + 1
    title = c.title or (text_of(spec["title"], "flow title") if spec.get("title") else "")
    w = c.width or 840
    h = c.height or 260
    pad, nh = 24, 30
    top = 52 if title else 24
    bottom = h - (54 if back else 22)
    lanes = (w - 2 * pad) / ranks
    longest = max(text_width(n.label.upper(), 9, "mono", MONO_LS) for n in nodes)
    nw = min(max(longest + 30, 88), 176, lanes - 22)
    for r in range(ranks):
        col = [n for n in nodes if n.rank == r]
        for k, node in enumerate(col):
            node.x = pad + lanes * (r + 0.5)
            node.y = top + (bottom - top) * (k + 0.5) / len(col)
    for node in nodes:
        if node.fx is not None:
            node.x = pad + nw / 2 + min(max(node.fx, 0.0), 1.0) * (w - 2 * pad - nw)
        if node.fy is not None:
            node.y = top + nh / 2 + min(max(node.fy, 0.0), 1.0) * (bottom - top - nh)
    desc = "Flow: " + "; ".join(f"{a} to {b}" + (f" ({lab})" if lab else "") for a, b, lab in edges)
    art = Art(
        w,
        h,
        title or "Flow diagram",
        desc if edges else "Flow: " + ", ".join(n.label for n in nodes),
    )
    p = c.theme
    frame(c, art)
    if title:
        heading(c, art, title, x=pad, y=32)
    art.defs.append(
        el(
            "marker",
            el(
                "path",
                d="M1 1L7 4L1 7",
                fill="none",
                stroke=p.panel_stroke,
                stroke_width=1.3,
                stroke_linecap="round",
                stroke_linejoin="round",
            ),
            id=c.id("arrow"),
            viewBox="0 0 8 8",
            refX=7,
            refY=4,
            markerWidth=8,
            markerHeight=8,
            markerUnits="userSpaceOnUse",
            orient="auto",
        )
    )
    routes = []  # (edge, d, length, mid, is_back)
    arc_y = h - 16
    for a, b, label in edges:
        u, v = by_id[a], by_id[b]
        if (a, b, label) in back:
            q0, q3 = (u.x, u.y + nh / 2), (v.x, v.y + nh / 2 + 3)
            q1, q2 = (u.x, arc_y), (v.x, arc_y)
        else:
            q0, q3 = (u.x + nw / 2, u.y), (v.x - nw / 2 - 2, v.y)
            mx = (q0[0] + q3[0]) / 2
            q1, q2 = (mx, q0[1]), (mx, q3[1])
        if abs(q0[1] - q3[1]) < 0.5 and (a, b, label) not in back:
            d = f"M{num(q0[0])} {num(q0[1])} H{num(q3[0])}"
            pts = [q0, q3]
        else:
            d = "M{} {} C{} {} {} {} {} {}".format(*(num(v) for v in (*q0, *q1, *q2, *q3)))
            pts = cubic(q0, q1, q2, q3)
        length = sum(math.dist(s, t) for s, t in itertools.pairwise(pts)) * 1.02 + 2
        if len(pts) == 2:
            mid = ((q0[0] + q3[0]) / 2, q0[1])
        else:
            mid = pts[len(pts) // 2]
        routes.append(((a, b, label), d, length, mid, (a, b, label) in back))

    one = c.one_shot
    beats = ranks + (1 if back else 0) + 1
    if one:
        clock, begins, item = c.entrance(ranks + (1 if back else 0))
    else:
        beat_s = {"medium": 1.0, "long": 2.4}.get(c.preset.name, 2.4)
        clock = c.cycle(beats * beat_s, distance=sum(r[2] for r in routes) or w)
        begins, item = [], 0.0
    bl = 1 / beats
    d_s = clock.dur

    def lit_at(node: Node) -> float:
        if one:
            return (begins[node.rank] + item) / d_s
        return (0.3 if node.rank == 0 else node.rank + 0.85) * bl

    def travel(edge: tuple[str, str, str], is_back: bool) -> tuple[float, float]:
        u, v = by_id[edge[0]], by_id[edge[1]]
        if one:
            if is_back:
                return begins[-1] / d_s, (begins[-1] + item) / d_s
            return (begins[u.rank] + item * 0.5) / d_s, (begins[v.rank] + item * 0.5) / d_s
        if is_back:
            return (ranks + 0.05) * bl, (ranks + 0.85) * bl
        return (u.rank + 1.05) * bl, (v.rank + 0.85) * bl

    base_edges, traces, packets, edge_labels = [], [], [], []
    ramp = min(0.1 * bl, 0.25 / d_s)
    for edge, d, length, mid, is_back in routes:
        a, b = travel(edge, is_back)
        stroke = {"fill": "none", "stroke_width": 1.3}
        if is_back:
            stroke["stroke_dasharray"] = "4 4"
        if one:
            base_edges.append(
                el(
                    "g",
                    animate("opacity", [(0, 0), (a, 0), (a + ramp, 1)], clock),
                    el(
                        "path",
                        animate(
                            "stroke-dashoffset", [(0, num(length)), (a, num(length)), (b, 0)], clock
                        ),
                        d=d,
                        stroke=p.panel_stroke,
                        marker_end=c.url("arrow"),
                        **{**stroke, "stroke_dasharray": num(length)},
                        stroke_dashoffset=0,
                    ),
                )
            )
        else:
            base_edges.append(
                el("path", d=d, stroke=p.panel_stroke, marker_end=c.url("arrow"), **stroke)
            )
            color = c.tone(by_id[edge[1]].tone) if not is_back else p.warn
            traces.append(
                el(
                    "path",
                    animate(
                        "stroke-dashoffset", [(0, num(length)), (a, num(length)), (b, 0)], clock
                    ),
                    d=d,
                    fill="none",
                    stroke=color,
                    stroke_width=1.6,
                    stroke_linecap="round",
                    stroke_dasharray=num(length),
                    stroke_dashoffset=0,
                    opacity=0.9,
                )
            )
            packets.append(
                el(
                    "circle",
                    animate("opacity", window(a, b, ramp), clock),
                    ride(d, a, b, clock),
                    r=3.6,
                    fill=color,
                    opacity=0,
                )
            )
        if edge[2]:
            edge_labels.append(
                mono(c, edge[2].upper(), mid[0], mid[1] - 7, p.dim, 8, text_anchor="middle")
            )

    node_base, overlays, node_labels = [], [], []
    for node in nodes:
        x, y = node.x - nw / 2, node.y - nh / 2
        color = c.tone(node.tone)
        strong = node.tone not in (None, "", "muted")
        rect = el(
            "rect",
            x=x,
            y=y,
            width=nw,
            height=nh,
            rx=6,
            fill=alpha(color, 0.12) if strong else p.card,
            stroke=alpha(color, 0.8) if strong else p.panel_stroke,
            stroke_width=1.2,
        )
        label = fit(node.label.upper(), nw - 16, 9, "mono", MONO_LS)
        text = mono(
            c, label, node.x, node.y + 3.5, color if strong else p.text, 9, text_anchor="middle"
        )
        if one:
            r0 = begins[node.rank]
            node_base.append(el("g", rise(clock, r0, item, dy=6), rect, text))
            continue
        node_base.append(rect)
        node_labels.append(text)
        t = lit_at(node)
        overlays.append(
            el(
                "rect",
                animate("opacity", [(0, 0), (t, 0), (t + ramp, 1)], clock),
                x=x,
                y=y,
                width=nw,
                height=nh,
                rx=6,
                fill=alpha(color, 0.16),
                stroke=color,
                stroke_width=1.4,
            )
        )
    if one:
        art.body.append(el("g", veil(clock), *base_edges, *edge_labels, *node_base))
    else:
        art.body += base_edges + edge_labels + node_base
        art.body.append(el("g", veil(clock), *traces, *overlays))
        art.body += node_labels + packets
    return art


LOADER_TURN = {"micro": 0.6, "short": 0.9, "medium": 1.2, "long": 2.0, "ambient": 4.0}


def kind_loader(c: Ctx) -> Art:
    """Loading indicator: spinner, dots or an indeterminate bar. Loops unless --once."""
    spec = spec_of(c, "variant") if c.data is not None else {}
    variant = c.variant or spec.get("variant", "spinner")
    if isinstance(variant, list):
        variant = variant[0] if variant else "spinner"
    if variant not in ("spinner", "dots", "bar"):
        raise ForgeError(f"loader variant must be spinner, dots or bar, got {variant!r}")
    turn = LOADER_TURN[c.preset.name]
    ink = c.pal.ink
    if variant == "spinner":
        w = c.width or 48
        h = c.height or w
        r = min(w, h) / 2 - 6
        circ = 2 * math.pi * r
        if c.preset.name == "ambient":
            turn = max(1.0, circ / c.speed)
        spin, breathe = Clock(turn, c.loop), Clock(round(turn * 2, 3), c.loop)
        art = Art(w, h, c.title or "Loading", "Animated spinner loader")
        cx, cy = w / 2, h / 2
        short, long_ = circ * 0.18, circ * 0.62
        art.body += [
            el("circle", cx=cx, cy=cy, r=r, fill="none", stroke=NEUTRAL, stroke_width=4),
            el(
                "g",
                move("rotate", [(0, (0, cx, cy)), (1, (360, cx, cy))], spin),
                el(
                    "circle",
                    animate(
                        "stroke-dasharray",
                        [
                            (0, f"{num(short)} {num(circ)}"),
                            (0.5, f"{num(long_)} {num(circ)}"),
                            (1, f"{num(short)} {num(circ)}"),
                        ],
                        breathe,
                    ),
                    cx=cx,
                    cy=cy,
                    r=r,
                    fill="none",
                    stroke=ink,
                    stroke_width=4,
                    stroke_linecap="round",
                    stroke_dasharray=f"{num(short)} {num(circ)}",
                ),
            ),
        ]
        return art
    if variant == "dots":
        w = c.width or 72
        h = c.height or 24
        clock = Clock(turn, c.loop)
        art = Art(w, h, c.title or "Loading", "Animated three-dot loader")
        r = min(h / 2 - 3, w / 12)
        for i in range(3):
            a = i * 0.18
            art.body.append(
                el(
                    "circle",
                    animate(
                        "opacity",
                        [(0, 0.3), (a, 0.3), (a + 0.2, 1), (a + 0.42, 0.3), (1, 0.3)],
                        clock,
                    ),
                    animate(
                        "r",
                        [
                            (0, r * 0.7),
                            (a, r * 0.7),
                            (a + 0.2, r),
                            (a + 0.42, r * 0.7),
                            (1, r * 0.7),
                        ],
                        clock,
                    ),
                    cx=w / 2 + (i - 1) * w / 4,
                    cy=h / 2,
                    r=r * 0.7,
                    fill=ink,
                    opacity=0.3,
                )
            )
        return art
    w = c.width or 240
    h = c.height or 8
    seg = w * 0.32
    clock = Clock(round(turn * 1.4, 3), c.loop)
    art = Art(w, h, c.title or "Loading", "Animated indeterminate progress bar")
    art.defs.append(el("clipPath", el("rect", width=w, height=h, rx=h / 2), id=c.id("track")))
    art.body += [
        el("rect", width=w, height=h, rx=h / 2, fill=NEUTRAL),
        el(
            "g",
            el(
                "rect",
                move(
                    "translate",
                    [(0, (-(w + seg) / 2, 0)), (1, ((w + seg) / 2, 0))],
                    clock,
                    ease=EASE_IN_OUT,
                ),
                x=(w - seg) / 2,
                width=seg,
                height=h,
                rx=h / 2,
                fill=ink,
            ),
            clip_path=c.url("track"),
        ),
    ]
    return art


def kind_typing(c: Ctx) -> Art:
    """Terminal window that types each command, then shows its output lines."""
    spec = spec_of(c, "lines")
    prompt = text_of(spec.get("prompt", "$"), "typing prompt", 8)
    cmds: list[tuple[str, list[str], object]] = []
    for i, raw in enumerate(need_list(spec.get("lines"), "typing lines", 8)):
        if isinstance(raw, dict):
            outs = raw.get("out", [])
            outs = [outs] if isinstance(outs, str) else need_list(outs, "typing out", 6, 0)
            cmd = text_of(raw.get("cmd", ""), f"typing line {i} cmd", 120)
            cmds.append((cmd, [text_of(o, "typing out", 120) for o in outs], raw.get("tone")))
        else:
            cmds.append((text_of(raw, f"typing line {i}", 120), [], None))
    window_title = c.title or text_of(spec.get("title", "terminal"), "typing title", 40)
    w = c.width or 640
    fs = 13.0
    cw = fs * EM["mono"]
    pad, line_h = 20, 21
    cmd_x = pad + (len(prompt) + 1) * cw
    rows = []  # (y, cmd, outs, tone)
    y = 62.0
    for cmd, outs, tone in cmds:
        rows.append(
            (
                y,
                fit(cmd, w - cmd_x - pad, fs, "mono"),
                [fit(o, w - 2 * pad - 16, fs, "mono") for o in outs],
                tone,
            )
        )
        y += line_h * (1 + len(outs)) + 8
    h = c.height or y + 4
    art = Art(w, h, window_title, "Terminal: " + "; ".join(f"{prompt} {cmd}" for cmd, _, _ in cmds))
    p = c.theme
    tcls = c.cls("t")
    art.css.append(f".{tcls}{{font-family:{MONO};font-size:{num(fs)}px;white-space:pre}}")
    art.defs.append(
        el("clipPath", el("rect", x=0.5, y=0.5, width=w - 1, height=h - 1, rx=12), id=c.id("win"))
    )
    art.body += [
        el("rect", x=0.5, y=0.5, width=w - 1, height=h - 1, rx=12, fill=p.bg, stroke=p.border),
        el(
            "g",
            el("rect", width=w, height=34, fill=p.card),
            el("line", x1=0, y1=34, x2=w, y2=34, stroke=p.border),
            clip_path=c.url("win"),
        ),
    ]
    for i, color in enumerate((NEUTRAL, NEUTRAL, p.ok)):
        art.body.append(el("circle", cx=20 + i * 18, cy=17, r=5.5, fill=color))
    art.body.append(
        mono(
            c,
            fit(window_title, w - 160, 10, "mono", MONO_LS),
            w / 2,
            21,
            p.dim,
            10,
            text_anchor="middle",
        )
    )

    # the natural pace in seconds, scaled to the preset afterwards
    cps = c.speed / cw if c.preset.name == "ambient" else 38.0
    t = 0.3
    plan = []  # (prompt_at, type_start, type_end, out_times)
    for _, cmd, outs, _ in rows:
        start = t + 0.12
        end = start + len(cmd) / cps
        out_times = [end + 0.15 + j * 0.1 for j in range(len(outs))]
        plan.append((t, start, end, out_times))
        t = (out_times[-1] if out_times else end) + 0.35
    total = t
    if c.one_shot:
        scale = min(1.0, (c.preset.total - 0.05) / total)
        length = total * scale + 0.05
        clock = (
            Clock(PRESETS["medium"].fit(length + 2.4), True)
            if c.loop
            else Clock(round(length, 3), False)
        )
    else:
        hold = {"medium": 1.6, "long": 2.4}.get(c.preset.name, 4.0)
        clock = c.cycle(total + hold, distance=sum(len(r[1]) for r in rows) * cw)
        scale = min(1.0, (clock.dur - hold) / total)
    d = clock.dur

    def f(sec: float) -> float:
        return sec * scale / d

    shown = []
    cur_x: list[tuple[float, object]] = [(0, cmd_x)]
    cur_y: list[tuple[float, object]] = [(0, rows[0][0] - 12)]
    for i, ((y, cmd, outs, tone), (at, start, end, out_times)) in enumerate(
        zip(rows, plan, strict=True)
    ):
        shown.append(
            el(
                "text",
                esc(prompt),
                animate("opacity", [(0, 0), (f(at), 1)], clock, discrete=True),
                class_=tcls,
                x=pad,
                y=y,
                fill=p.ok,
            )
        )
        widths: list[tuple[float, object]] = [(0, 0), (f(start), 0)]
        per = (end - start) / max(len(cmd), 1)
        for k in range(1, len(cmd) + 1):
            widths.append((f(start + k * per), k * cw))
            cur_x.append((f(start + k * per), cmd_x + k * cw))
        widths[-1] = (widths[-1][0], w - cmd_x)
        cur_y.append((f(at), y - 12))
        cur_x.insert(len(cur_x) - len(cmd), (f(at), cmd_x))
        art.defs.append(
            el(
                "clipPath",
                el(
                    "rect",
                    animate("width", widths, clock, discrete=True),
                    x=cmd_x,
                    y=y - 15,
                    width=w - cmd_x,
                    height=20,
                ),
                id=c.id(f"c{i}"),
            )
        )
        shown.append(
            el("text", esc(cmd), class_=tcls, x=cmd_x, y=y, fill=p.ink, clip_path=c.url(f"c{i}"))
        )
        color = c.tone(tone) if tone else p.text
        for j, (out, ot) in enumerate(zip(outs, out_times, strict=True)):
            shown.append(
                el(
                    "text",
                    esc(out),
                    animate("opacity", [(0, 0), (f(ot), 1)], clock, discrete=True),
                    class_=tcls,
                    x=pad + 16,
                    y=y + line_h * (j + 1),
                    fill=color,
                )
            )
    blink = c.cls("cur")
    count = "infinite" if clock.loop else "4"
    art.css.append(
        f".{blink}{{animation:{blink} 1.05s steps(1) {count}}}"
        f"@keyframes {blink}{{50%{{opacity:0}}}}"
    )
    cur_x.sort(key=lambda fr: fr[0])
    shown.append(
        el(
            "g",
            el(
                "rect",
                animate("x", cur_x, clock, discrete=True),
                animate("y", cur_y, clock, discrete=True),
                x=cur_x[-1][1],
                y=cur_y[-1][1],
                width=cw * 0.9,
                height=15,
                fill=c.pal.ink,
                opacity=0.85,
            ),
            class_=blink,
        )
    )
    art.body.append(el("g", veil(clock), *shown))
    return art


def kind_divider(c: Ctx) -> Art:
    """Hairline divider with a center dot and a light pulse sweeping across it."""
    w = c.width or 840
    h = c.height or 14
    y = h / 2
    art = Art(w, h, c.title or "Divider", "Decorative animated divider")
    ink = c.pal.ink
    art.defs.append(
        el(
            "linearGradient",
            el("stop", offset=0, stop_color=ink, stop_opacity=0),
            el("stop", offset=0.5, stop_color=ink),
            el("stop", offset=1, stop_color=ink, stop_opacity=0),
            id=c.id("pulse"),
            x1=0,
            x2=1,
        )
    )
    if c.one_shot:
        clock, begins, item = c.entrance(2, item=0.8 if c.preset.name == "short" else None)
        half = w / 2
        sides = [
            el(
                "line",
                animate(
                    "stroke-dashoffset",
                    [
                        (0, num(half)),
                        (begins[0] / clock.dur, num(half)),
                        ((begins[0] + item) / clock.dur, 0),
                    ],
                    clock,
                    ease=True,
                ),
                x1=half,
                y1=y,
                x2=x2,
                y2=y,
                stroke=NEUTRAL,
                stroke_width=1,
                stroke_dasharray=num(half),
                stroke_dashoffset=0,
            )
            for x2 in (0, w)
        ]
        b = (begins[1] + item) / clock.dur
        dot = el(
            "circle",
            animate("r", [(0, 0), (begins[1] / clock.dur, 0), (b, 2.5)], clock, ease=True),
            cx=half,
            cy=y,
            r=2.5,
            fill=ink,
        )
        art.body.append(el("g", veil(clock), *sides, dot))
        return art
    seg = min(220.0, w * 0.3)
    clock = c.cycle(3.6 if c.preset.name == "medium" else 10.0, distance=w + seg)
    art.body += [
        el("line", x1=0, y1=y, x2=w, y2=y, stroke=NEUTRAL, stroke_width=1),
        el("circle", cx=w / 2, cy=y, r=2.5, fill=ink),
        el(
            "rect",
            move("translate", [(0, (0, 0)), (1, (w + seg, 0))], clock),
            x=-seg,
            y=y - 1,
            width=seg,
            height=2,
            fill=c.url("pulse"),
        ),
    ]
    return art


def kind_badge(c: Ctx) -> Art:
    """Two-part pill badge (label and value) with a status dot and a shine sweep."""
    spec = spec_of(c, "value") if not isinstance(c.data, str) else {"value": c.data}
    value = spec.get("value", "")
    if isinstance(value, list):
        value = value[0] if value else ""
    value = text_of(value, "badge value", 40)
    label = text_of(spec.get("label", ""), "badge label", 40)
    dot = bool(spec.get("dot", True))
    color = c.tone(spec.get("tone"))
    h = c.height or 28
    size, padx = 11, 12
    lw = text_width(label.upper(), size, "mono", MONO_LS) + 2 * padx if label else 0
    vw = text_width(value.upper(), size, "mono", MONO_LS) + 2 * padx + (12 if dot else 0)
    w = c.width or math.ceil(lw + vw)
    if c.width:
        lw = min(lw, w * 0.5)
        vw = w - lw
    p = c.theme
    art = Art(
        w,
        h,
        c.title or (f"{label}: {value}" if label else value),
        f"Badge: {label} {value}".strip(),
    )
    art.defs += [
        el("clipPath", el("rect", width=w, height=h, rx=h / 2), id=c.id("pill")),
        el(
            "linearGradient",
            el("stop", offset=0, stop_color="#ffffff", stop_opacity=0),
            el("stop", offset=0.5, stop_color="#ffffff", stop_opacity=p.shine),
            el("stop", offset=1, stop_color="#ffffff", stop_opacity=0),
            id=c.id("shine"),
            x1=0,
            x2=1,
        ),
    ]
    one = c.one_shot
    if one:
        clock, begins, item = c.entrance(2)
        sweep = (begins[1] / clock.dur, (begins[1] + item) / clock.dur)
    else:
        clock = c.cycle(4.5 if c.preset.name == "medium" else 10.0, distance=w + 80)
        sweep = (0.0, min(0.35, 1.6 / clock.dur))
    ty = h / 2 + 4
    inner = [
        el("rect", width=lw, height=h, fill=p.card),
        el("rect", x=lw, width=vw, height=h, fill=alpha(color, 0.14)),
        el(
            "rect",
            move(
                "translate",
                [(0, (0, 0)), (sweep[0], (0, 0)), (sweep[1], (w + 80, 0)), (1, (w + 80, 0))],
                clock,
                additive="sum",
            ),
            x=-50,
            y=0,
            width=30,
            height=h,
            fill=c.url("shine"),
            transform="skewX(-20)",
        ),
    ]
    vx = lw + padx + (12 if dot else 0)
    parts = [
        el("g", *inner, clip_path=c.url("pill")),
        el(
            "rect",
            x=0.5,
            y=0.5,
            width=w - 1,
            height=h - 1,
            rx=(h - 1) / 2,
            fill="none",
            stroke=alpha(color, 0.45),
        ),
    ]
    if label:
        parts.append(
            mono(
                c,
                fit(label.upper(), lw - 2 * padx + 2, size, "mono", MONO_LS),
                padx,
                ty,
                p.dim,
                size,
            )
        )
    parts.append(
        mono(
            c,
            fit(value.upper(), vw - (vx - lw) - padx + 2, size, "mono", MONO_LS),
            vx,
            ty,
            color,
            size,
        )
    )
    if dot:
        pulse = "" if one else animate("opacity", [(0, 1), (0.5, 0.35), (1, 1)], clock.sub(1.8))
        parts.append(el("circle", pulse, cx=lw + padx + 3, cy=h / 2, r=3.2, fill=color))
    if one:
        enter = animate(
            "opacity",
            [(0, 0), (begins[0] / clock.dur, 0), ((begins[0] + item) / clock.dur, 1)],
            clock,
            ease=True,
        )
        art.body.append(el("g", veil(clock), el("g", enter, *parts)))
    else:
        art.body += parts
    return art


# ---------------------------------------------------------------- registry and samples


@dataclass(frozen=True)
class KindSpec:
    render: Callable[[Ctx], Art]
    timing: str
    about: str


KINDS: dict[str, KindSpec] = {
    "tiles": KindSpec(kind_tiles, "short", "stat tiles grid"),
    "hero": KindSpec(
        kind_hero, "long", "title, rotating taglines, status pill, node constellation"
    ),
    "marquee": KindSpec(kind_marquee, "ambient", "seamless strip of text chips at constant px/s"),
    "chart": KindSpec(kind_chart, "short", "line chart that draws in, peak marker"),
    "bars": KindSpec(kind_bars, "short", "progress bars that grow"),
    "flow": KindSpec(kind_flow, "medium", "nodes and edges with packets: pipeline or architecture"),
    "loader": KindSpec(kind_loader, "medium", "spinner, dots or bar loader (--variant)"),
    "typing": KindSpec(kind_typing, "long", "terminal typing lines"),
    "divider": KindSpec(kind_divider, "medium", "hairline divider with a pulse"),
    "badge": KindSpec(kind_badge, "medium", "label and value pill with a shine sweep"),
}

SAMPLES: dict[str, Any] = {
    "tiles": {
        "items": [
            {"value": "99.9%", "label": "uptime", "tone": "ok"},
            {"value": "1.2k", "label": "stars"},
            {"value": "48", "label": "releases"},
            {"value": "<1s", "label": "build time"},
        ]
    },
    "hero": {
        "kicker": "Animated SVG",
        "title": "svg-forge",
        "taglines": [
            "Self-contained animated SVGs",
            "SMIL and CSS, no script",
            "Renders in READMEs and on the web",
            "Dark and light from one command",
        ],
        "status": "Building in public",
        "meta": "MIT licensed",
        "nodes": ["core", "cli", "api", "docs", "ci", "web"],
    },
    "marquee": [
        "python",
        "typescript",
        "rust",
        "go",
        "docker",
        "kubernetes",
        "terraform",
        "postgres",
        "redis",
        "react",
        "vite",
        "github actions",
    ],
    "chart": {
        "title": "Weekly active users",
        "values": [120, 132, 128, 150, 171, 165, 190, 214, 208, 236, 251, 247],
        "labels": ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10", "W11", "W12"],
    },
    "bars": {
        "title": "Languages",
        "items": [
            {"label": "Python", "value": 46},
            {"label": "TypeScript", "value": 31},
            {"label": "Shell", "value": 14},
            {"label": "Other", "value": 9, "tone": "muted"},
        ],
    },
    "flow": {
        "title": "CI pipeline",
        "nodes": ["commit", "build", "test", "scan", {"id": "deploy", "tone": "ok"}],
        "edges": [
            ["commit", "build"],
            ["build", "test"],
            ["build", "scan"],
            ["test", "deploy"],
            ["scan", "deploy"],
        ],
    },
    "loader": None,
    "typing": {
        "title": "bash",
        "prompt": "$",
        "lines": [
            {"cmd": "python forge.py --kind flow --out flow.svg", "out": ["wrote flow.svg"]},
            {"cmd": "python validate_svg.py flow.svg", "out": ["flow.svg: ok"], "tone": "ok"},
        ],
    },
    "divider": None,
    "badge": {"label": "build", "value": "passing", "tone": "ok"},
}


# ---------------------------------------------------------------- render


def font_stack(value: str | None) -> str:
    if value is None:
        return SANS
    if value in FONT_PRESETS:
        return FONT_PRESETS[value]
    if not FONT_STACK.fullmatch(value) or "url" in value.lower():
        raise ForgeError("--font-stack takes sans, mono, serif, system or a plain font-family list")
    return value


def assemble(c: Ctx, art: Art) -> str:
    p = c.prefix
    css = [
        f".{p}m{{font-family:{MONO};font-weight:700;letter-spacing:{num(MONO_LS)}px}}",
        f".{p}s{{font-family:{c.sans};font-weight:600}}",
        f".{p}b{{font-family:{c.sans};font-weight:800}}",
        *art.css,
    ]
    if c.reduced == "respect":
        css.append(
            f"@media (prefers-reduced-motion: reduce){{.{p}root *{{animation-delay:0s!important;"
            "animation-duration:1ms!important;animation-iteration-count:1!important;"
            "animation-fill-mode:forwards!important}}"
        )
    w, h = num(art.width), num(art.height)
    head = (
        f'<svg xmlns="{SVG_NS}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-labelledby="{p}title {p}desc" class="{p}root">'
    )
    parts = [
        head,
        f'<title id="{p}title">{esc(art.title)}</title>',
        f'<desc id="{p}desc">{esc(art.desc[:600])}</desc>',
        f"<style>{html.escape(''.join(css), quote=False)}</style>",
    ]
    if art.defs:
        parts.append("<defs>" + "".join(art.defs) + "</defs>")
    parts += [b for b in art.body if b]
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render(
    kind: str,
    *,
    theme: str = "dark",
    accent: str = DEFAULT_ACCENT,
    timing: str | None = None,
    loop: bool | None = None,
    speed: float | None = None,
    width: float | None = None,
    height: float | None = None,
    title: str | None = None,
    desc: str | None = None,
    data: Any = None,
    variant: str | None = None,
    reduced_motion: str = "ignore",
    font: str | None = None,
    id_prefix: str | None = None,
) -> str:
    """Return one SVG document as a string. Raises ForgeError on bad options or data."""
    if kind not in KINDS:
        raise ForgeError(f"unknown kind {kind!r}; choose from {', '.join(KINDS)}")
    if theme not in THEMES:
        raise ForgeError("theme must be dark or light (the CLI expands both)")
    timing = timing or KINDS[kind].timing
    if timing not in PRESETS:
        raise ForgeError(f"timing must be one of {', '.join(PRESETS)}")
    if reduced_motion not in ("ignore", "respect"):
        raise ForgeError("--reduced-motion must be ignore or respect")
    for name, value in (("--width", width), ("--height", height)):
        if value is not None and not 8 <= value <= 4000:
            raise ForgeError(f"{name} must be between 8 and 4000")
    if speed is not None and not 0 < speed <= 2000:
        raise ForgeError("--speed must be above 0 and at most 2000 px/s")
    if id_prefix is not None and not re.fullmatch(r"[A-Za-z][\w-]{0,23}", id_prefix):
        raise ForgeError("--id-prefix must start with a letter and use letters, digits, - or _")
    accent = parse_color(accent)
    preset = PRESETS[timing]
    looping = (preset.loop or kind == "loader") if loop is None else loop
    seed = json.dumps(
        [kind, theme, accent, timing, looping, speed, width, height, title, desc, data, variant],
        sort_keys=True,
        default=str,
    )
    prefix = id_prefix or "sf" + hashlib.sha1(seed.encode()).hexdigest()[:6] + "-"
    th = THEMES[theme]
    ctx = Ctx(
        kind=kind,
        theme=th,
        pal=palette(accent, th),
        preset=preset,
        loop=looping,
        speed=speed or DEFAULT_SPEED,
        width=width,
        height=height,
        title=clean(title).strip() if title else None,
        desc=desc,
        data=data,
        variant=variant,
        prefix=prefix,
        sans=font_stack(font),
        reduced=reduced_motion,
    )
    art = KINDS[kind].render(ctx)
    if desc:
        art.desc = clean(desc)
    return assemble(ctx, art)


def load_data(value: str | None) -> Any:
    """Inline JSON (starts with [ { or ") or a path to a JSON file."""
    if value is None:
        return None
    text = value
    if not value.lstrip().startswith(("[", "{", '"')):
        path = Path(value)
        if not path.is_file():
            raise ForgeError(f"--data is neither inline JSON nor a file: {value}")
        text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ForgeError(f"--data is not valid JSON: {exc}") from exc


def write(path: Path, svg: str) -> bool:
    """Write only when the bytes change; return True when the file was (re)written."""
    data = svg.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def picture(dark: str, light: str, alt: str) -> str:
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{html.escape(dark)}">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="{html.escape(light)}">\n'
        f'  <img alt="{html.escape(alt)}" src="{html.escape(dark)}">\n'
        "</picture>"
    )


def build_parser() -> argparse.ArgumentParser:
    kinds = "\n".join(f"  {k:<8} {v.about} (default timing {v.timing})" for k, v in KINDS.items())
    ap = argparse.ArgumentParser(
        prog="forge.py",
        description="Generate a self-contained animated SVG.",
        epilog="kinds:\n" + kinds,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--kind", required=True, choices=list(KINDS))
    ap.add_argument("--out", help="output .svg; omit to print to stdout (single theme only)")
    ap.add_argument("--width", type=float, help="canvas width in px (kind default otherwise)")
    ap.add_argument("--height", type=float, help="canvas height in px (most kinds size to content)")
    ap.add_argument("--theme", choices=["dark", "light", "both"], default="dark")
    ap.add_argument("--accent", default=DEFAULT_ACCENT, help="hex accent, #rgb or #rrggbb")
    ap.add_argument(
        "--timing", choices=list(PRESETS), help="timing preset (kind default otherwise)"
    )
    loop = ap.add_mutually_exclusive_group()
    loop.add_argument("--loop", dest="loop", action="store_const", const=True, help="loop forever")
    loop.add_argument(
        "--once", dest="loop", action="store_const", const=False, help="play once and hold"
    )
    ap.add_argument(
        "--speed", type=float, help=f"px/s for marquee and ambient (default {DEFAULT_SPEED:g})"
    )
    ap.add_argument("--title", help="visible heading where the kind has one, and the <title>")
    ap.add_argument("--desc", help="override the generated <desc>")
    ap.add_argument("--data", help="inline JSON or a path to a JSON file with the kind's items")
    ap.add_argument("--variant", help="loader: spinner, dots or bar")
    ap.add_argument("--reduced-motion", choices=["ignore", "respect"], default="ignore")
    ap.add_argument("--font-stack", help="sans, mono, serif, system, or a font-family list")
    ap.add_argument("--id-prefix", help="prefix for ids and classes (default: hash of the input)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    if args.theme == "both" and not args.out:
        print("forge.py: error: --theme both needs --out", file=sys.stderr)
        return 2
    try:
        data = load_data(args.data)
        svgs = {
            t: render(
                args.kind,
                theme=t,
                accent=args.accent,
                timing=args.timing,
                loop=args.loop,
                speed=args.speed,
                width=args.width,
                height=args.height,
                title=args.title,
                desc=args.desc,
                data=data,
                variant=args.variant,
                reduced_motion=args.reduced_motion,
                font=args.font_stack,
                id_prefix=args.id_prefix,
            )
            for t in themes
        }
    except ForgeError as exc:
        print(f"forge.py: error: {exc}", file=sys.stderr)
        return 2
    if not args.out:
        sys.stdout.buffer.write(svgs[themes[0]].encode("utf-8"))
        return 0
    out = Path(args.out)
    if args.theme != "both":
        changed = write(out, svgs[themes[0]])
        print(
            f"{'wrote' if changed else 'unchanged'} {out.as_posix()} ({out.stat().st_size} bytes)"
        )
        return 0
    stem = out.with_suffix("") if out.suffix == ".svg" else out
    paths = {t: stem.with_name(f"{stem.name}-{t}.svg") for t in themes}
    for t, path in paths.items():
        changed = write(path, svgs[t])
        print(
            f"{'wrote' if changed else 'unchanged'} {path.as_posix()} ({path.stat().st_size} bytes)"
        )
    alt = re.search(r"<title[^>]*>(.*?)</title>", svgs["dark"])
    print(
        picture(
            paths["dark"].as_posix(),
            paths["light"].as_posix(),
            html.unescape(alt.group(1) if alt else ""),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
