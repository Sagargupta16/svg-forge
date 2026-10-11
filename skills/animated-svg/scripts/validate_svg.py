#!/usr/bin/env python3
"""Check SVG files for render-target safety, accessibility, weight and animation hygiene.

Usage: validate_svg.py FILE_OR_DIR... [--target standalone|web] [--max-kb N] [--json]
                       [--strict-contrast] [--theme both|dark|light]

Targets: standalone (README image, <img>, docs) is strict; web (SVG inlined in a page you
control) turns external references, foreignObject and a missing xmlns into warnings.

Rules (error unless marked warn):
  SV001  not well-formed XML, unreadable, or contains a DOCTYPE / ENTITY declaration
  SV002  root element is not <svg>
  SV003  root has no valid viewBox
  SV004  root is not in the SVG namespace (missing xmlns)                     web: warn
  SV005  <script> element
  SV006  on* event handler attribute or javascript: URL
  SV007  <foreignObject>                                                      web: warn
  SV008  external reference in href, xlink:href, src or url(): only #id and data: load
         inside an SVG image                                     web: warn except file:
  SV009  @import or a remote @font-face in CSS                                web: warn
  SV010  no accessible name: role="img" with aria-label or aria-labelledby, or
         aria-hidden="true" for decoration
  SV011  aria-labelledby names an id that is missing or not a <title> / <desc>
  SV012  duplicate id
  SV013  file over the size budget (100 KB standalone, 200 KB web, or --max-kb);
         warn above half of it
  SV014  en or em dash anywhere in the file
  SV015  warn: more than 40 animated elements
  SV016  warn: repeating animation shorter than 100 ms
  SV017  warn: keyTimes / values / keyPoints counts differ, or keyTimes do not run 0 to 1
  SV018  warn: keySplines without calcMode="spline", or the wrong number of keySplines
  SV019  warn: pathLength and vector-effect="non-scaling-stroke" on one element
  SV020  warn: data: URI larger than 64 KB
  SV021  warn: text below WCAG 1.4.3 contrast (4.5:1, or 3:1 for large text: 24px, or
         18.66px bold) against the opaque background the SVG paints beneath it
  SV022  warn: text with no opaque background in the SVG that falls below the same
         threshold on GitHub dark (#0d1117) or GitHub light (#ffffff)
  SV023  warn: a solid shape below 3:1 (WCAG 1.4.11) against what is painted beneath it,
         or against a GitHub theme where the SVG paints nothing
  --strict-contrast turns SV021-SV023 into errors. --theme dark or --theme light tests
  only that GitHub theme (the matching half of a <picture> pair). The Python API runs
  them only when asked: validate_text(..., contrast="warn" or "error").

Contrast model: static colors from fill, color and opacity attributes, inline style and
simple <style> rules (type, class, id, descendant and child selectors; @media is
ignored), with inheritance, currentColor, fill-opacity and opacity composited over what is
painted beneath. Text is sampled near the middle of its estimated run; the background is
the topmost opaque shape there, else a full-canvas opaque shape, else both GitHub themes.
Gradients count every stop and keep the worst ratio. Text that starts at opacity 0 and
fades in is tested at its peak animated opacity. For SV023, paints under 50% opacity count
as decoration and filled shapes under text count as its background, not as graphics.
Findings marked info say what could not be checked.

Exit status: 1 when any file has an error, 0 when there are only warnings or none.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.parsers import expat

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
DASHES = (chr(0x2013), chr(0x2014))
SMIL = {"animate", "animateTransform", "animateMotion", "set", "animateColor"}
BUDGET_KB = {"standalone": 100, "web": 200}
MAX_ANIMATED = 40
DATA_URI_KB = 64

RULES = {
    "SV001": "not well-formed XML",
    "SV002": "root is not <svg>",
    "SV003": "missing or invalid viewBox",
    "SV004": "not in the SVG namespace",
    "SV005": "script element",
    "SV006": "event handler or javascript: URL",
    "SV007": "foreignObject",
    "SV008": "external reference",
    "SV009": "CSS @import or remote font",
    "SV010": "no accessible name",
    "SV011": "broken aria-labelledby",
    "SV012": "duplicate id",
    "SV013": "file size budget",
    "SV014": "en or em dash",
    "SV015": "too many animated elements",
    "SV016": "repeating animation under 100 ms",
    "SV017": "keyTimes length or range",
    "SV018": "keySplines without spline mode",
    "SV019": "pathLength with non-scaling-stroke",
    "SV020": "large data: URI",
    "SV021": "text contrast below WCAG",
    "SV022": "text fails on a GitHub theme",
    "SV023": "graphic contrast below 3:1",
}
# Run when contrast is on: the CLI default (warn), or contrast="warn"/"error" in the API.
CONTRAST_RULES = {rule: RULES[rule] for rule in ("SV021", "SV022", "SV023")}

URL_REF = re.compile(r"url\(\s*(['\"]?)([^'\")]*)\1\s*\)", re.I)
CLOCK = re.compile(r"^\s*(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)\s*(h|min|s|ms)?\s*$")
CSS_TIME = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b", re.I)
CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
KEYFRAMES = re.compile(r"@(?:-webkit-)?keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", re.I)


@dataclass
class Finding:
    rule: str
    severity: str  # error | warn | info
    line: int
    message: str


@dataclass
class Report:
    file: str
    target: str
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    @property
    def errors(self) -> int:
        return sum(f.severity == "error" for f in self.findings)

    @property
    def warnings(self) -> int:
        return sum(f.severity == "warn" for f in self.findings)

    def add(self, rule: str, severity: str, line: int, message: str) -> None:
        self.findings.append(Finding(rule, severity, line, message))

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "target": self.target,
            "ok": self.errors == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [asdict(f) for f in self.findings],
            "stats": self.stats,
        }


@dataclass
class Node:
    ns: str
    tag: str
    attrs: dict[str, str]
    line: int
    parent: Node | None = None
    children: list[Node] = field(default_factory=list)
    text: list[str] = field(default_factory=list)

    def iter(self):  # noqa: ANN201 - generator of Node
        yield self
        for child in self.children:
            yield from child.iter()

    def attr(self, local: str, ns: str = "") -> str | None:
        return self.attrs.get(f"{ns}}}{local}" if ns else local)


class DeclarationError(Exception):
    def __init__(self, line: int, what: str) -> None:
        super().__init__(what)
        self.line = line


def split(name: str) -> tuple[str, str]:
    ns, _, local = name.rpartition("}")
    return ns, local


def parse(text: str) -> Node:
    """Parse with expat into a small tree that keeps line numbers. Refuses DTDs."""
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack: list[Node] = []
    roots: list[Node] = []

    def refuse(*_args: object) -> None:
        raise DeclarationError(parser.CurrentLineNumber, "DOCTYPE or ENTITY declaration")

    def start(name: str, attrs: dict[str, str]) -> None:
        ns, local = split(name)
        node = Node(ns, local, dict(attrs), parser.CurrentLineNumber, stack[-1] if stack else None)
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)

    def end(_name: str) -> None:
        stack.pop()

    def chars(data: str) -> None:
        if stack:
            stack[-1].text.append(data)

    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    parser.Parse(text, True)
    return roots[0]


def seconds(value: str | None) -> float | None:
    """SMIL clock value to seconds: 4.8s, 120ms, 1min, 00:01:02.5, or bare seconds."""
    if not value:
        return None
    m = CLOCK.match(value)
    if not m:
        return None
    a, b, c, unit = m.groups()
    if a is not None:  # full or partial clock value
        hours, minutes = (int(a), int(b)) if b is not None else (0, int(a))
        return hours * 3600 + minutes * 60 + float(c)
    scale = {"h": 3600, "min": 60, "s": 1, "ms": 0.001, None: 1}[unit]
    return float(c) * scale


def classify(ref: str) -> str:
    """local (#id or empty), data, file, js, or remote (http, https, //, relative path)."""
    r = ref.strip().lower()
    if not r or r.startswith("#"):
        return "local"
    if r.startswith("data:"):
        return "data"
    if r.startswith("file:"):
        return "file"
    if r.startswith("javascript:"):
        return "js"
    return "remote"


def check_ref(report: Report, line: int, where: str, ref: str, web: bool) -> None:
    kind = classify(ref)
    if kind == "local":
        return
    if kind == "data":
        kb = len(ref) / 1024
        if kb > DATA_URI_KB:
            report.add(
                "SV020", "warn", line, f"{where} data: URI is {kb:.0f} KB (cap {DATA_URI_KB})"
            )
        return
    if kind == "js":
        report.add("SV006", "error", line, f"{where} uses a javascript: URL")
        return
    severity = "warn" if web and kind == "remote" else "error"
    shown = ref if len(ref) <= 80 else ref[:77] + "..."
    report.add("SV008", severity, line, f"{where} points outside the file: {shown}")


def style_texts(root: Node) -> list[tuple[int, str]]:
    out = []
    for node in root.iter():
        if node.tag == "style":
            out.append((node.line, "".join(node.text)))
        if node.attr("style"):
            out.append((node.line, node.attr("style") or ""))
    return out


def css_checks(report: Report, root: Node, web: bool) -> dict[str, object]:
    """CSS findings plus the CSS side of the animation inventory."""
    keyframes = 0
    durations: list[float] = []
    infinite = 0
    animated_classes: set[str] = set()
    severity = "warn" if web else "error"
    for line, css in style_texts(root):
        if re.search(r"@import\b", css, re.I):
            report.add("SV009", severity, line, "CSS @import loads an external stylesheet")
        for face in re.findall(r"@font-face\s*\{[^}]*\}", css, re.I):
            if any(classify(m.group(2)) not in ("local", "data") for m in URL_REF.finditer(face)):
                report.add("SV009", severity, line, "@font-face loads a remote font")
        for m in URL_REF.finditer(css):
            check_ref(report, line, "CSS url()", m.group(2), web)
        keyframes += len(KEYFRAMES.findall(css))
        plain = KEYFRAMES.sub("", css)
        bodies = [(sel, body) for sel, body in CSS_RULE.findall(plain)] or [("", plain)]
        for selector, body in bodies:
            for decl in re.findall(r"animation(?:-duration)?\s*:\s*([^;}]+)", body, re.I):
                times = CSS_TIME.findall(decl)
                if times:
                    value, unit = times[0]
                    durations.append(float(value) * (0.001 if unit.lower() == "ms" else 1))
                if re.search(r"\binfinite\b", decl, re.I):
                    infinite += 1
                animated_classes.update(re.findall(r"\.([\w-]+)", selector))
    css_elements = 0
    for node in root.iter():
        classes = set((node.attr("class") or "").split())
        style = node.attr("style") or ""
        if classes & animated_classes or re.search(r"animation\s*:", style, re.I):
            css_elements += 1
    return {
        "keyframes": keyframes,
        "css_durations": durations,
        "css_infinite": infinite,
        "css_elements": css_elements,
    }


def smil_checks(report: Report, root: Node) -> dict[str, object]:
    count = 0
    parents: set[int] = set()
    durations: list[float] = []
    infinite = 0
    for node in root.iter():
        if node.tag not in SMIL:
            continue
        count += 1
        if node.parent is not None:
            parents.add(id(node.parent))
        dur = seconds(node.attr("dur"))
        if dur is not None:
            durations.append(dur)
        rc, rd = node.attr("repeatCount"), node.attr("repeatDur")
        if rc == "indefinite" or rd == "indefinite":
            infinite += 1
        repeats = rc == "indefinite" or rd is not None or (rc not in (None, "1") and rc != "0")
        if dur is not None and dur < 0.1 and repeats:
            report.add(
                "SV016", "warn", node.line, f"<{node.tag}> repeats every {dur * 1000:.0f} ms"
            )
        key_times = node.attr("keyTimes")
        mode = node.attr("calcMode") or ("paced" if node.tag == "animateMotion" else "linear")
        if key_times:
            times = [t for t in key_times.split(";") if t.strip()]
            for name in ("values", "keyPoints"):
                raw = node.attr(name)
                if raw is not None:
                    n = len([v for v in raw.split(";") if v.strip()])
                    if n != len(times):
                        report.add(
                            "SV017",
                            "warn",
                            node.line,
                            f"<{node.tag}> has {len(times)} keyTimes but {n} {name}",
                        )
            try:
                nums = [float(t) for t in times]
            except ValueError:
                nums = []
                report.add("SV017", "warn", node.line, f"<{node.tag}> keyTimes are not numbers")
            if nums:
                bad_end = mode != "discrete" and abs(nums[-1] - 1) > 1e-6
                if (
                    abs(nums[0]) > 1e-6
                    or bad_end
                    or any(b < a for a, b in itertools.pairwise(nums))
                ):
                    report.add(
                        "SV017",
                        "warn",
                        node.line,
                        f"<{node.tag}> keyTimes must rise from 0 to 1 (got {key_times})",
                    )
        splines = node.attr("keySplines")
        if splines:
            if mode != "spline":
                report.add(
                    "SV018",
                    "warn",
                    node.line,
                    f'<{node.tag}> has keySplines without calcMode="spline"',
                )
            elif key_times:
                segments = len([s for s in splines.split(";") if s.strip()])
                need = len([t for t in key_times.split(";") if t.strip()]) - 1
                if segments != need:
                    report.add(
                        "SV018",
                        "warn",
                        node.line,
                        f"<{node.tag}> needs {need} keySplines for its keyTimes, has {segments}",
                    )
    return {
        "smil": count,
        "smil_parents": parents,
        "smil_durations": durations,
        "smil_infinite": infinite,
    }


def a11y_checks(report: Report, root: Node) -> None:
    if (root.attr("aria-hidden") or "").lower() == "true":
        return
    ids = {n.attr("id"): n for n in root.iter() if n.attr("id")}
    label = (root.attr("aria-label") or "").strip()
    labelledby = (root.attr("aria-labelledby") or "").split()
    named = bool(label)
    for ref in labelledby:
        target = ids.get(ref)
        if target is None or target.tag not in ("title", "desc"):
            report.add(
                "SV011",
                "error",
                root.line,
                f'aria-labelledby id "{ref}" is not a <title> or <desc>',
            )
        elif target.tag == "title" and "".join(target.text).strip():
            named = True
    if root.attr("role") != "img":
        report.add("SV010", "error", root.line, 'root needs role="img" (or aria-hidden="true")')
    if not named:
        report.add(
            "SV010",
            "error",
            root.line,
            "root needs aria-label, or aria-labelledby pointing at a non-empty <title>",
        )


# Contrast (SV021-SV023): a static model of what a reader sees in the first painted state.

Color = tuple[float, float, float, float]  # r, g, b, alpha; each 0 to 1
Matrix = tuple[float, float, float, float, float, float]  # a b c d e f, as in matrix()
Ring = list[tuple[float, float]]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
GITHUB_PAGES: dict[str, Color] = {
    "dark": (0x0D / 255, 0x11 / 255, 0x17 / 255, 1.0),
    "light": (1.0, 1.0, 1.0, 1.0),
}
TEXT_RATIO, LARGE_RATIO, GRAPHIC_RATIO = 4.5, 3.0, 3.0
LARGE_PX, LARGE_BOLD_PX = 24.0, 18.66
DECORATIVE_ALPHA = 0.5
OPAQUE = 0.999
SHAPES = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"}
TEXT_TAGS = {"text", "tspan", "textPath"}
GRADIENTS = {"linearGradient", "radialGradient"}
NOT_RENDERED = set(
    "defs clipPath mask pattern marker symbol linearGradient radialGradient filter title desc "
    "metadata style script foreignObject".split()
)
INHERITED = set(
    "fill fill-opacity stroke stroke-opacity stroke-width color font-size font-weight "
    "letter-spacing text-anchor dominant-baseline visibility".split()
)
NAMED_COLORS = dict(
    pair.split("=")
    for pair in (
        "black=#000000 white=#ffffff gray=#808080 grey=#808080 silver=#c0c0c0 "
        "darkgray=#a9a9a9 darkgrey=#a9a9a9 lightgray=#d3d3d3 lightgrey=#d3d3d3 "
        "dimgray=#696969 dimgrey=#696969 whitesmoke=#f5f5f5 red=#ff0000 maroon=#800000 "
        "crimson=#dc143c tomato=#ff6347 orange=#ffa500 gold=#ffd700 yellow=#ffff00 "
        "olive=#808000 lime=#00ff00 green=#008000 teal=#008080 aqua=#00ffff cyan=#00ffff "
        "blue=#0000ff navy=#000080 purple=#800080 fuchsia=#ff00ff magenta=#ff00ff "
        "pink=#ffc0cb transparent=#00000000"
    ).split()
)
FONT_KEYWORDS = {"xx-small": 9.0, "x-small": 10.0, "small": 13.0, "medium": 16.0}
FONT_KEYWORDS |= {"large": 18.0, "x-large": 24.0, "xx-large": 32.0, "xxx-large": 48.0}
NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
NUM = re.compile(NUMBER)
LENGTH = re.compile(rf"\s*({NUMBER})\s*(px|pt|em|rem|%)?\s*")
TRANSFORM = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
PAINT_URL = re.compile(r"url\(\s*['\"]?#([^'\")\s]+)['\"]?\s*\)\s*(.*)", re.S)
SELECTOR_PART = re.compile(r"(\*|[A-Za-z][\w-]*)?((?:[.#][\w-]+)*)")
PATH_ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7}
PATH_NUMBER = re.compile(rf"[\s,]*({NUMBER})")
PATH_FLAG = re.compile(r"[\s,]*([01])")
PATH_LETTER = re.compile(r"[\s,]*([MmLlHhVvCcSsQqTtAaZz])")


def clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def channel(token: str, scale: float) -> float:
    """One rgb() or hsl() component: a percentage, or a number out of `scale`."""
    if token.endswith("%"):
        return clamp(float(token[:-1]) / 100)
    return clamp(float(token) / scale)


def hue(token: str) -> float:
    m = re.fullmatch(rf"({NUMBER})(deg|rad|grad|turn)?", token)
    if not m:
        raise ValueError(token)
    scale = {"rad": 180 / math.pi, "grad": 0.9, "turn": 360.0}.get(m.group(2) or "", 1.0)
    return float(m.group(1)) * scale % 360


def hsl_part(n: int, h: float, s: float, light: float) -> float:
    k = (n + h / 30) % 12
    return light - s * min(light, 1 - light) * max(-1.0, min(k - 3, 9 - k, 1.0))


def parse_color(value: str) -> Color | None:
    """#rgb, #rgba, #rrggbb, #rrggbbaa, rgb(), rgba(), hsl(), hsla() or a common name."""
    v = value.strip().lower()
    v = NAMED_COLORS.get(v, v)
    if v.startswith("#"):
        h = v[1:]
        if len(h) not in (3, 4, 6, 8) or not re.fullmatch(r"[0-9a-f]+", h):
            return None
        if len(h) < 6:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 6:
            h += "ff"
        r, g, b, a = (int(h[i : i + 2], 16) / 255 for i in range(0, 8, 2))
        return (r, g, b, a)
    m = re.fullmatch(r"(rgba?|hsla?)\(([^()]*)\)", v)
    if not m:
        return None
    parts = [p for p in re.split(r"[\s,/]+", m.group(2)) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        alpha = channel(parts[3], 1.0) if len(parts) == 4 else 1.0
        if m.group(1).startswith("rgb"):
            r, g, b = (channel(p, 255.0) for p in parts[:3])
        else:
            h_deg, s, light = hue(parts[0]), channel(parts[1], 100.0), channel(parts[2], 100.0)
            r, g, b = (hsl_part(n, h_deg, s, light) for n in (0, 8, 4))
    except ValueError:
        return None
    return (r, g, b, alpha)


def fraction(value: str | None) -> float | None:
    """An opacity value: 0.5 or 50%, clamped to 0..1."""
    m = re.fullmatch(rf"\s*({NUMBER})\s*(%)?\s*", value or "")
    if not m:
        return None
    return clamp(float(m.group(1)) / (100 if m.group(2) else 1))


def luminance(c: Color) -> float:
    """WCAG 2.2 relative luminance of the color's sRGB channels."""
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(a: Color, b: Color) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def over(fg: Color, bg: Color) -> Color:
    """fg composited source-over onto an opaque bg."""
    a = fg[3]
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def hex_color(c: Color) -> str:
    out = "#" + "".join(f"{round(v * 255):02x}" for v in c[:3])
    alpha = round(c[3] * 255)
    return out if alpha == 255 else f"{out}{alpha:02x}"


def extremes(colors: list[Color]) -> list[Color]:
    """The darkest and the lightest of a set of backgrounds: the worst cases for any text."""
    unique = sorted({hex_color(c): c for c in colors}.values(), key=luminance)
    return unique if len(unique) <= 2 else [unique[0], unique[-1]]


def worst(fgs: list[Color], bgs: list[Color]) -> tuple[float, Color, Color, Color]:
    """Lowest ratio over every foreground and background pair: (ratio, fg, shown, bg)."""
    pairs = [(contrast_ratio(over(f, b), b), f, over(f, b), b) for b in bgs for f in fgs]
    return min(pairs, key=lambda p: p[0])


def floor2(ratio: float) -> float:
    """Two decimals, rounded down, so a shown 4.50 never hides a failing 4.499."""
    return math.floor(ratio * 100) / 100


def mul(m: Matrix, n: Matrix) -> Matrix:
    a, b, c, d, e, f = m
    return (
        a * n[0] + c * n[1],
        b * n[0] + d * n[1],
        a * n[2] + c * n[3],
        b * n[2] + d * n[3],
        a * n[4] + c * n[5] + e,
        b * n[4] + d * n[5] + f,
    )


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def invert(m: Matrix) -> Matrix | None:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def parse_transform(value: str | None) -> Matrix:
    m = IDENTITY
    for name, args in TRANSFORM.findall(value or ""):
        n = [float(v) for v in NUM.findall(args)]
        if not n or (name == "matrix" and len(n) != 6):
            continue
        if name == "matrix":
            t: Matrix = (n[0], n[1], n[2], n[3], n[4], n[5])
        elif name == "translate":
            t = (1.0, 0.0, 0.0, 1.0, n[0], n[1] if len(n) > 1 else 0.0)
        elif name == "scale":
            t = (n[0], 0.0, 0.0, n[1] if len(n) > 1 else n[0], 0.0, 0.0)
        elif name == "rotate":
            cos, sin = math.cos(math.radians(n[0])), math.sin(math.radians(n[0]))
            t = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(n) == 3:
                t = mul(mul((1.0, 0.0, 0.0, 1.0, n[1], n[2]), t), (1, 0, 0, 1, -n[1], -n[2]))
        else:
            k = math.tan(math.radians(n[0]))
            t = (1.0, 0.0, k, 1.0, 0.0, 0.0) if name == "skewX" else (1.0, k, 0.0, 1.0, 0.0, 0.0)
        m = mul(m, t)
    return m


def path_rings(d: str) -> list[Ring]:
    """Vertices of each subpath, control points included: enough for bounds and hit tests."""
    rings: list[Ring] = []
    ring: Ring = []
    pos, cmd = 0, ""
    x = y = sx = sy = 0.0
    while True:
        m = PATH_LETTER.match(d, pos)
        if m:
            cmd, pos = m.group(1), m.end()
            if cmd in "Zz":
                if ring:
                    rings.append(ring)
                ring, x, y = [], sx, sy
                continue
        elif not cmd or cmd in "Zz" or not PATH_NUMBER.match(d, pos):
            break
        low, rel = cmd.lower(), cmd.islower()
        args: list[float] = []
        for i in range(PATH_ARGS[low]):
            arg = (PATH_FLAG if low == "a" and i in (3, 4) else PATH_NUMBER).match(d, pos)
            if not arg:
                return [*rings, ring] if ring else rings
            pos = arg.end()
            args.append(float(arg.group(1)))
        if not ring and low != "m":
            ring.append((x, y))
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if low == "h":
            x = args[0] + ox
        elif low == "v":
            y = args[0] + oy
        elif low == "a":
            x, y = args[5] + ox, args[6] + oy
        if low in "hva":
            points = [(x, y)]
        else:
            points = [(args[i] + ox, args[i + 1] + oy) for i in range(0, len(args), 2)]
            x, y = points[-1]
        if low == "m":
            if ring:
                rings.append(ring)
            ring, sx, sy = [], x, y
            cmd = "l" if rel else "L"
        ring.extend(points)
    if ring:
        rings.append(ring)
    return rings


def in_rings(rings: list[Ring], x: float, y: float) -> bool:
    """Even-odd hit test over closed rings."""
    inside = False
    for ring in rings:
        if len(ring) < 3:
            continue
        for (x1, y1), (x2, y2) in itertools.pairwise([*ring, ring[0]]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def declarations(body: str) -> dict[str, tuple[str, bool]]:
    out: dict[str, tuple[str, bool]] = {}
    for item in body.split(";"):
        prop, sep, value = item.partition(":")
        if not sep:
            continue
        value = value.strip()
        important = value.lower().endswith("!important")
        if important:
            value = value[: -len("!important")].strip()
        out[prop.strip().lower()] = (value, important)
    return out


def strip_at_rules(css: str) -> tuple[str, dict[str, str]]:
    """CSS without @-blocks (media queries are not modeled), plus @keyframes bodies by name."""
    out: list[str] = []
    frames: dict[str, str] = {}
    pos = 0
    while (at := css.find("@", pos)) != -1:
        out.append(css[pos:at])
        brace, semi = css.find("{", at), css.find(";", at)
        if brace == -1 or (semi != -1 and semi < brace):
            pos = len(css) if semi == -1 else semi + 1
            continue
        depth, end = 0, brace
        while end < len(css):
            depth += {"{": 1, "}": -1}.get(css[end], 0)
            if depth == 0:
                break
            end += 1
        name = re.match(r"@(?:-webkit-)?keyframes\s+([\w-]+)", css[at:brace])
        if name:
            frames[name.group(1)] = css[brace + 1 : end]
        pos = end + 1
    out.append(css[pos:])
    return "".join(out), frames


Compound = tuple[str, tuple[str, ...], frozenset[str]]  # tag or *, ids, classes


def parse_selector(text: str) -> tuple[list[tuple[Compound, str]], tuple[int, int, int]] | None:
    """Type, class, id, descendant and child selectors, rightmost part first; else None."""
    if not text.strip() or re.search(r"[:\[+~|]", text):
        return None
    parts: list[tuple[Compound, str]] = []
    joiner = " "
    a = b = c = 0
    for token in reversed(re.sub(r"\s*>\s*", " > ", text.strip()).split()):
        if token == ">":
            joiner = ">"
            continue
        m = SELECTOR_PART.fullmatch(token)
        if not m:
            return None
        tag = m.group(1) or "*"
        ids = tuple(re.findall(r"#([\w-]+)", m.group(2)))
        classes = frozenset(re.findall(r"\.([\w-]+)", m.group(2)))
        a, b, c = a + len(ids), b + len(classes), c + (tag != "*")
        parts.append(((tag, ids, classes), joiner))
        joiner = " "
    return (parts, (a, b, c)) if parts and joiner == " " else None


def selector_matches(node: Node, parts: list[tuple[Compound, str]], i: int = 0) -> bool:
    (tag, ids, classes), _ = parts[i]
    if tag != "*" and node.tag != tag:
        return False
    if any(node.attr("id") != ident for ident in ids):
        return False
    if not classes <= set((node.attr("class") or "").split()):
        return False
    if i + 1 == len(parts):
        return True
    up = node.parent
    while up is not None:
        if selector_matches(up, parts, i + 1):
            return True
        if parts[i + 1][1] == ">":
            return False
        up = up.parent
    return False


def lineage(node: Node) -> list[Node]:
    out: list[Node] = []
    n: Node | None = node
    while n is not None:
        out.append(n)
        n = n.parent
    return out


def pixels(value: str | None) -> float | None:
    """A positive plain or px length, else None."""
    m = LENGTH.fullmatch(value or "")
    size = float(m.group(1)) if m and m.group(2) in (None, "px") else 0.0
    return size if size > 0 else None


def first(value: str | None) -> str | None:
    """First entry of a coordinate list such as x="10 20 30"."""
    items = (value or "").replace(",", " ").split()
    return items[0] if items else None


@dataclass
class Paint:
    kind: str  # none | color | gradient | unknown
    colors: list[Color]
    label: str
    explicit: bool = True  # False when the shape relies on the default black fill


@dataclass
class Geometry:
    box: tuple[float, float, float, float]  # local bounds x0, y0, x1, y1
    kind: str  # box | ellipse | rings
    rings: list[Ring] = field(default_factory=list)

    @property
    def area(self) -> bool:
        return self.kind != "rings" or any(len(r) >= 3 for r in self.rings)

    @property
    def sample(self) -> tuple[float, float]:
        """A point on the shape: its center, or the middle of its first segment."""
        if self.kind != "rings":
            return (self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2
        ring = next(r for r in self.rings if r)
        (x1, y1), (x2, y2) = ring[0], ring[1] if len(ring) > 1 else ring[0]
        return (x1 + x2) / 2, (y1 + y2) / 2

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.box
        if self.kind == "box":
            return x0 <= x <= x1 and y0 <= y <= y1
        if self.kind == "ellipse":
            rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
            return ((x - x0 - rx) / rx) ** 2 + ((y - y0 - ry) / ry) ** 2 <= 1
        return in_rings(self.rings, x, y)


@dataclass
class Beneath:
    source: str  # "<rect> line 7", "canvas <rect> line 3" or "page"
    base: list[Color] | None  # opaque base colors; None means the GitHub page shows through
    layers: list[list[Color]]  # translucent paints above the base, bottom first
    image: bool = False
    tint: str = ""  # the topmost translucent paint, when there is one


class Scene:
    """Cascaded style, geometry and paint order of one parsed SVG, for the contrast rules."""

    def __init__(self, root: Node) -> None:
        self.order = list(root.iter())
        self.index = {id(n): i for i, n in enumerate(self.order)}
        self.ids = {n.attr("id"): n for n in self.order if n.attr("id")}
        css = "".join("".join(n.text) for n in self.order if n.tag == "style")
        plain, self.keyframes = strip_at_rules(re.sub(r"/\*.*?\*/", "", css, flags=re.S))
        self.rules: list[tuple[list[tuple[Compound, str]], tuple[int, ...], dict]] = []
        for selectors, body in CSS_RULE.findall(plain):
            decls = declarations(body)
            for one in selectors.split(","):
                parsed = parse_selector(one)
                if parsed:
                    self.rules.append((parsed[0], (*parsed[1], len(self.rules)), decls))
        self.anims: dict[int, list[Node]] = {}
        for n in self.order:
            if n.tag in SMIL:
                ref = (n.attr("href") or n.attr("href", XLINK_NS) or "").strip()
                target = self.ids.get(ref[1:]) if ref.startswith("#") else n.parent
                if target is not None:
                    self.anims.setdefault(id(target), []).append(n)
        self.box = self.view_box(root)
        width = pixels(root.attr("width"))
        self.scale = width / self.box[2] if width else 1.0  # rendered px per user unit
        self._style: dict[int, dict[str, str]] = {}
        self._ctm: dict[int, Matrix] = {}
        self._geometry: dict[int, Geometry | None] = {}
        self.surfaces = [
            n for n in self.order if (n.tag in SHAPES or n.tag == "image") and not self.hidden(n)
        ]
        self.canvas = {id(n) for n in self.surfaces if self.covers_canvas(n)}

    @staticmethod
    def view_box(root: Node) -> tuple[float, float, float, float]:
        box = (root.attr("viewBox") or "").replace(",", " ").split()
        try:
            x, y, w, h = (float(v) for v in box)
            if w > 0 and h > 0:
                return x, y, w, h
        except ValueError:
            pass
        return 0.0, 0.0, pixels(root.attr("width")) or 300.0, pixels(root.attr("height")) or 150.0

    # style

    def style(self, node: Node) -> dict[str, str]:
        """Declarations that win for one element: !important, then inline style, then the
        <style> rule with the highest specificity and the latest position."""
        cached = self._style.get(id(node))
        if cached is None:
            sources = [(d, (0, *w)) for parts, w, d in self.rules if selector_matches(node, parts)]
            sources.append((declarations(node.attr("style") or ""), (1, 0, 0, 0, 0)))
            ranked: dict[str, tuple[tuple[int, ...], str]] = {}
            for decls, weight in sources:
                for prop, (value, important) in decls.items():
                    key = (int(important), *weight)
                    if prop not in ranked or key > ranked[prop][0]:
                        ranked[prop] = (key, value)
            cached = {prop: value for prop, (_, value) in ranked.items()}
            self._style[id(node)] = cached
        return cached

    def get(self, node: Node, prop: str) -> str | None:
        """Specified value on the element itself: CSS, then the presentation attribute."""
        value = self.style(node).get(prop)
        if value is None:
            value = node.attr(prop)
        return value.strip() if value is not None else None

    def computed(self, node: Node, prop: str) -> str | None:
        n: Node | None = node
        while n is not None:
            value = self.get(n, prop)
            low = (value or "").lower()
            if value is None or low == "unset":
                if prop not in INHERITED:
                    return None
            elif low == "initial":
                return None
            elif low != "inherit":
                return value
            n = n.parent
        return None

    def current_color(self, node: Node) -> str:
        for n in lineage(node):
            value = self.get(n, "color")
            if value and value.lower() == "initial":
                break
            if value and value.lower() not in ("inherit", "unset", "currentcolor"):
                return value
        return "black"

    def font_size(self, node: Node | None) -> float:
        if node is None:
            return 16.0
        value = (self.get(node, "font-size") or "").lower()
        if value in FONT_KEYWORDS:
            return FONT_KEYWORDS[value]
        if value in ("larger", "smaller"):
            parent = self.font_size(node.parent)
            return parent * 1.2 if value == "larger" else parent / 1.2
        m = LENGTH.fullmatch(value)
        if not m:
            return self.font_size(node.parent)
        size, unit = float(m.group(1)), m.group(2)
        if unit in ("em", "%"):
            return self.font_size(node.parent) * (size if unit == "em" else size / 100)
        return size * {"pt": 4 / 3, "rem": 16.0}.get(unit or "", 1.0)

    def bold(self, node: Node) -> bool:
        weight = (self.computed(node, "font-weight") or "normal").lower()
        return weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 700)

    def length(self, value: str | None, axis: str = "x") -> float | None:
        m = LENGTH.fullmatch(value or "")
        if not m:
            return None
        size, unit = float(m.group(1)), m.group(2)
        if unit == "%":
            w, h = self.box[2], self.box[3]
            ref = w if axis == "x" else h if axis == "y" else math.hypot(w, h) / math.sqrt(2)
            return size * ref / 100
        return size * {"pt": 4 / 3, "em": 16.0, "rem": 16.0}.get(unit or "", 1.0)

    # animation and visibility

    def animation_names(self, node: Node) -> list[str]:
        raw = self.get(node, "animation-name") or self.get(node, "animation") or ""
        return [token for token in re.split(r"[\s,]+", raw) if token in self.keyframes]

    def animated(self, node: Node, prop: str) -> tuple[bool, float | None]:
        """Whether an animation on the element targets prop, and its peak numeric value."""
        found, values = False, []
        for anim in self.anims.get(id(node), []):
            if anim.attr("attributeName") == prop:
                found = True
                for key in ("values", "from", "to"):
                    values += [fraction(v) for v in (anim.attr(key) or "").split(";")]
        pattern = rf"(?<![\w-]){re.escape(prop)}\s*:\s*([^;}}]+)"
        for name in self.animation_names(node):
            hits = re.findall(pattern, self.keyframes[name])
            found = found or bool(hits)
            values += [fraction(v) for v in hits]
        numbers = [v for v in values if v is not None]
        return found, (max(numbers) if numbers else None)

    def opacity(self, node: Node, prop: str = "opacity") -> tuple[float, bool]:
        """Static value, or the peak animated value when it starts at 0 and an animation
        fades it in. The flag is True when that animation could not be read (then 1)."""
        raw = self.get(node, prop) if prop == "opacity" else self.computed(node, prop)
        value = fraction(raw)
        if value is None or value > 0:
            return (1.0 if value is None else value), False
        for n in [node] if prop == "opacity" else lineage(node):
            found, peak = self.animated(n, prop)
            if found:
                return (1.0, True) if peak is None else (peak, False)
        return 0.0, False

    def alpha(self, node: Node) -> tuple[float, bool]:
        """Opacity multiplied down from the root, and whether a fade had to be guessed."""
        total, guessed = 1.0, False
        for n in lineage(node):
            value, unsure = self.opacity(n)
            total, guessed = total * value, guessed or unsure
        return total, guessed

    def hidden(self, node: Node) -> bool:
        """Not painted: inside defs and the like, display:none or visibility:hidden, unless an
        animation changes that property."""
        chain = lineage(node)
        for n in chain:
            if n.tag in NOT_RENDERED:
                return True
            if (self.get(n, "display") or "").lower() == "none":
                if not self.animated(n, "display")[0]:
                    return True
        if (self.computed(node, "visibility") or "").lower() in ("hidden", "collapse"):
            return not any(self.animated(n, "visibility")[0] for n in chain)
        return False

    # paint

    def stops(self, gradient: Node, depth: int = 0) -> list[Color] | None:
        """Stop colors with stop-opacity, following href to inherited stops; None if unreadable."""
        stops = [c for c in gradient.children if c.tag == "stop"]
        if not stops:
            ref = (gradient.attr("href") or gradient.attr("href", XLINK_NS) or "").strip()
            target = self.ids.get(ref[1:]) if ref.startswith("#") else None
            if target is not None and target.tag in GRADIENTS and depth < 8:
                return self.stops(target, depth + 1)
            return []
        out = []
        for stop in stops:
            raw = self.get(stop, "stop-color") or "black"
            if raw.lower() == "currentcolor":
                raw = self.current_color(stop)
            color = parse_color(raw)
            if color is None:
                return None
            opacity = fraction(self.get(stop, "stop-opacity"))
            alpha = color[3] * (1.0 if opacity is None else opacity)
            out.append((color[0], color[1], color[2], alpha))
        return out

    def paint(self, node: Node, prop: str) -> Paint:
        """fill or stroke as candidate colors, with its -opacity and opacity applied."""
        raw = self.computed(node, prop)
        explicit = raw is not None
        value = raw if raw is not None else ("black" if prop == "fill" else "none")
        if value.lower() == "none":
            return Paint("none", [], value, explicit)
        alpha = self.alpha(node)[0] * self.opacity(node, f"{prop}-opacity")[0]
        m = PAINT_URL.match(value)
        if m:
            target = self.ids.get(m.group(1))
            if target is not None and target.tag in GRADIENTS:
                stops = self.stops(target)
                if stops is None:
                    return Paint("unknown", [], value, explicit)
                if not stops:
                    return Paint("none", [], value, explicit)
                colors = [(c[0], c[1], c[2], c[3] * alpha) for c in stops]
                return Paint("gradient", colors, value, explicit)
            fallback = m.group(2).strip()
            if target is not None or not fallback or fallback.lower() == "none":
                return Paint("unknown" if target is not None else "none", [], value, explicit)
            value = fallback
        resolved = self.current_color(node) if value.lower() == "currentcolor" else value
        color = parse_color(resolved)
        if color is None:
            return Paint("unknown", [], value, explicit)
        return Paint("color", [(color[0], color[1], color[2], color[3] * alpha)], value, explicit)

    # geometry

    def ctm(self, node: Node) -> Matrix:
        """Element space to root user space."""
        cached = self._ctm.get(id(node))
        if cached is None:
            local = parse_transform(node.attr("transform"))
            if node.tag == "svg" and node.parent is not None:  # nested viewport offset
                x, y = self.length(node.attr("x")) or 0.0, self.length(node.attr("y"), "y") or 0.0
                local = mul((1.0, 0.0, 0.0, 1.0, x, y), local)
            parent = self.ctm(node.parent) if node.parent is not None else IDENTITY
            cached = mul(parent, local)
            self._ctm[id(node)] = cached
        return cached

    def geometry(self, node: Node) -> Geometry | None:
        if id(node) not in self._geometry:
            self._geometry[id(node)] = self.shape_geometry(node)
        return self._geometry[id(node)]

    def shape_geometry(self, node: Node) -> Geometry | None:
        def size(name: str, axis: str, default: float | None = 0.0) -> float | None:
            value = self.length(node.attr(name), axis)
            return default if value is None else value

        tag = node.tag
        if tag in ("rect", "image"):
            w, h = size("width", "x", None), size("height", "y", None)
            x, y = size("x", "x") or 0.0, size("y", "y") or 0.0
            return Geometry((x, y, x + w, y + h), "box") if w and h and w > 0 and h > 0 else None
        if tag in ("circle", "ellipse"):
            cx, cy = size("cx", "x") or 0.0, size("cy", "y") or 0.0
            if tag == "circle":
                rx = ry = size("r", "r", None)
            else:
                rx, ry = size("rx", "x", None), size("ry", "y", None)
                rx, ry = rx or ry, ry or rx
            if not rx or not ry or rx <= 0 or ry <= 0:
                return None
            return Geometry((cx - rx, cy - ry, cx + rx, cy + ry), "ellipse")
        if tag == "line":
            ends = [size(name, name[0]) or 0.0 for name in ("x1", "y1", "x2", "y2")]
            rings = [[(ends[0], ends[1]), (ends[2], ends[3])]]
        elif tag in ("polyline", "polygon"):
            nums = [float(v) for v in NUM.findall(node.attr("points") or "")]
            rings = [list(zip(nums[0::2], nums[1::2], strict=False))]
        elif tag == "path":
            rings = path_rings(node.attr("d") or "")
        else:
            return None
        points = [p for r in rings for p in r]
        if not points:
            return None
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        return Geometry((min(xs), min(ys), max(xs), max(ys)), "rings", rings)

    def inside(self, node: Node, x: float, y: float) -> bool:
        geometry, inverse = self.geometry(node), invert(self.ctm(node))
        if geometry is None or inverse is None:
            return False
        return geometry.contains(*apply(inverse, x, y))

    def covers_canvas(self, node: Node) -> bool:
        """An opaque rect, path or polygon whose bounds span the whole viewBox (1% slack)."""
        geometry = self.geometry(node)
        if node.tag not in ("rect", "path", "polygon") or geometry is None:
            return False
        paint = self.paint(node, "fill")
        if paint.kind not in ("color", "gradient") or any(c[3] < OPAQUE for c in paint.colors):
            return False
        x0, y0, x1, y1 = geometry.box
        corners = [apply(self.ctm(node), x, y) for x in (x0, x1) for y in (y0, y1)]
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        vx, vy, vw, vh = self.box
        tx, ty = max(1.0, vw / 100), max(1.0, vh / 100)
        return (
            min(xs) <= vx + tx
            and min(ys) <= vy + ty
            and max(xs) >= vx + vw - tx
            and max(ys) >= vy + vh - ty
        )

    def text_point(self, node: Node, content: str) -> tuple[float, float]:
        """Root-space point near the middle of the text run; width is estimated from size."""
        size = self.font_size(node)
        x = y = None
        start = None
        n: Node | None = node
        while n is not None and n.tag in TEXT_TAGS:
            if n.tag == "textPath" and start is None:
                ref = (n.attr("href") or n.attr("href", XLINK_NS) or "").strip()
                path = self.ids.get(ref[1:]) if ref.startswith("#") else None
                geometry = self.geometry(path) if path is not None else None
                if path is not None and geometry is not None and geometry.rings:
                    start = apply(self.ctm(path), *geometry.rings[0][0])
            x = x if x is not None else self.length(first(n.attr("x")), "x")
            y = y if y is not None else self.length(first(n.attr("y")), "y")
            n = n.parent
        spacing = self.length(self.computed(node, "letter-spacing")) or 0.0
        width = len(content) * (size * 0.55 + spacing)
        anchor = (self.computed(node, "text-anchor") or "start").lower()
        shift = {"middle": 0.0, "end": -width / 2}.get(anchor, width / 2)
        baseline = (self.computed(node, "dominant-baseline") or "").lower()
        rise = {"middle": 0.0, "central": 0.0, "hanging": 0.4, "text-before-edge": 0.4}
        dy = rise.get(baseline, -0.35) * size
        if start is not None:
            return start[0] + width / 2, start[1] + dy
        return apply(self.ctm(node), (x or 0.0) + shift, (y or 0.0) + dy)

    # what lies beneath

    def beneath(self, index: int, x: float, y: float) -> Beneath:
        """What is painted under (x, y) before element `index`: an opaque base, tints above."""
        layers: list[list[Color]] = []
        tint = ""
        for node in reversed(self.surfaces):
            if self.index[id(node)] >= index:
                continue
            canvas = id(node) in self.canvas
            if not canvas and not self.inside(node, x, y):
                continue
            where = f"{'canvas ' if canvas else ''}<{node.tag}> line {node.line}"
            if node.tag == "image":
                return Beneath(where, None, layers[::-1], image=True, tint=tint)
            paint = self.paint(node, "fill")
            if paint.kind not in ("color", "gradient") or all(c[3] <= 0 for c in paint.colors):
                continue
            if all(c[3] >= OPAQUE for c in paint.colors):
                return Beneath(where, paint.colors, layers[::-1], tint=tint)
            layers.append(paint.colors)
            tint = tint or where
        return Beneath("page", None, layers[::-1], tint=tint)

    def grounds(self, below: Beneath, themes: tuple[str, ...]) -> list[tuple[str, list[Color]]]:
        """(label, candidate backgrounds) per base: the SVG's own, or each GitHub theme."""
        if below.base is not None:
            bases = [(below.source, [(c[0], c[1], c[2], 1.0) for c in below.base])]
        else:
            bases = [(f"github-{t}", [GITHUB_PAGES[t]]) for t in themes]
        out = []
        for label, colors in bases:
            bgs = extremes(colors)
            for layer in below.layers:
                bgs = extremes([over(c, b) for b in bgs for c in layer])
            out.append((label, bgs))
        return out


def where_text(label: str, bg: Color, tint: str) -> str:
    if label.startswith("github-"):
        return f"GitHub {label[7:]} {hex_color(bg)}" + (f" (through {tint})" if tint else "")
    return f"{hex_color(bg)} ({tint + ' over ' if tint else ''}{label})"


def measure(
    entries: list[dict[str, object]],
    grounds: list[tuple[str, list[Color]]],
    below: Beneath,
    paint: Paint,
    need: float,
    about: dict[str, object],
) -> list[str]:
    """Record the worst ratio against each background; return the failing ones for a message."""
    fails = []
    for label, bgs in grounds:
        ratio, fg, shown, bg = worst(paint.colors, bgs)
        entries.append(
            about
            | {
                "value": paint.label,
                "color": hex_color(fg),
                "shown": hex_color(shown),
                "background": hex_color(bg),
                "against": label,
                "tint": below.tint or None,
                "ratio": floor2(ratio),
                "required": need,
                "pass": ratio >= need,
            }
        )
        if ratio < need:
            fails.append(f"{floor2(ratio):.2f}:1 on {where_text(label, bg, below.tint)}")
    return fails


def contrast_checks(
    report: Report, root: Node, strict: bool = False, themes: tuple[str, ...] = ("dark", "light")
) -> list[dict[str, object]]:
    """SV021 and SV022 for text, SV023 for solid graphics; returns every measurement."""
    scene = Scene(root)
    severity = "error" if strict else "warn"
    entries: list[dict[str, object]] = []
    texts: list[tuple[int, float, float]] = []
    for node in scene.order:
        if node.tag not in TEXT_TAGS:
            continue
        content = " ".join("".join(node.text).split())
        if not content or scene.hidden(node):
            continue
        alpha, guessed = scene.alpha(node)
        if alpha <= 0:
            continue
        quote = content if len(content) <= 30 else content[:27] + "..."
        index = scene.index[id(node)]
        x, y = scene.text_point(node, content)
        texts.append((index, x, y))
        paint = scene.paint(node, "fill")
        if paint.kind == "unknown":
            report.add(
                "SV021",
                "info",
                node.line,
                f'text "{quote}" fill {paint.label} is not a color it can read; not checked',
            )
            continue
        if paint.kind == "none" or all(c[3] <= 0 for c in paint.colors):
            continue
        below = scene.beneath(index, x, y)
        if below.image:
            report.add(
                "SV021", "info", node.line, f'text "{quote}" sits on an <image>; not checked'
            )
            continue
        m = scene.ctm(node)
        px = scene.font_size(node) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) * scene.scale
        bold = scene.bold(node)
        large = px >= LARGE_PX or (bold and px >= LARGE_BOLD_PX)
        need = LARGE_RATIO if large else TEXT_RATIO
        about = {"kind": "text", "line": node.line, "element": node.tag, "text": quote}
        about |= {"paint": "fill", "font_px": round(px, 2), "bold": bold, "large": large}
        fails = measure(entries, scene.grounds(below, themes), below, paint, need, about)
        if fails and below.base is None:
            report.add(
                "SV022",
                severity,
                node.line,
                f'text "{quote}" is {" and ".join(fails)}; needs {need:g}:1 (add an opaque '
                "background, or ship a dark/light <picture> pair and check each with --theme)",
            )
        elif fails:
            report.add(
                "SV021",
                severity,
                node.line,
                f'text "{quote}" is {fails[0]}; needs {need:g}:1 '
                f"(change {paint.label} or the background)",
            )
        if guessed:
            report.add(
                "SV021",
                "info",
                node.line,
                f'text "{quote}" starts at opacity 0 and its fade-in could not be read; '
                "tested at full opacity",
            )
    defaults: list[int] = []
    for node in scene.surfaces:
        geometry = scene.geometry(node)
        if node.tag == "image" or id(node) in scene.canvas or geometry is None:
            continue
        if any(a.tag == "animateMotion" for a in scene.anims.get(id(node), [])):
            continue  # its static position is not where it is seen
        index = scene.index[id(node)]
        for prop in ("fill", "stroke"):
            if prop == "fill" and not geometry.area:
                continue
            if prop == "stroke" and (scene.length(scene.computed(node, "stroke-width")) or 1) <= 0:
                continue
            paint = scene.paint(node, prop)
            if paint.kind != "color" or paint.colors[0][3] < DECORATIVE_ALPHA:
                continue
            if prop == "fill" and any(
                i > index and scene.inside(node, tx, ty) for i, tx, ty in texts
            ):
                continue  # a surface under text: the text check covers it
            below = scene.beneath(index, *apply(scene.ctm(node), *geometry.sample))
            if below.image:
                continue
            about = {"kind": "graphic", "line": node.line, "element": node.tag, "paint": prop}
            grounds = scene.grounds(below, themes)
            fails = measure(entries, grounds, below, paint, GRAPHIC_RATIO, about)
            if fails and not paint.explicit:
                defaults.append(node.line)
            elif fails:
                report.add(
                    "SV023",
                    severity,
                    node.line,
                    f"<{node.tag}> {prop} {paint.label} is {' and '.join(fails)}; "
                    "needs 3:1 for graphics (WCAG 1.4.11)",
                )
    if defaults:
        report.add(
            "SV023",
            "info",
            defaults[0],
            f"{len(defaults)} shape(s) keep the default black fill and fall below 3:1; "
            "set an explicit fill to have them checked",
        )
    return entries


def validate_text(
    raw: bytes,
    name: str = "<svg>",
    target: str = "standalone",
    max_kb: float | None = None,
    contrast: str = "off",
    theme: str = "both",
) -> Report:
    """contrast is off (the API default), warn (the CLI default) or error; theme is both,
    dark or light: the GitHub page(s) a file with no background of its own is tested on."""
    report = Report(name, target)
    web = target == "web"
    budget = max_kb if max_kb is not None else BUDGET_KB[target]
    kb = len(raw) / 1024
    report.stats["bytes"] = len(raw)
    if kb > budget:
        report.add("SV013", "error", 1, f"{kb:.1f} KB is over the {budget:g} KB budget")
    elif kb > budget / 2:
        report.add("SV013", "warn", 1, f"{kb:.1f} KB is over half the {budget:g} KB budget")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        report.add("SV001", "error", 1, f"not UTF-8: {exc}")
        return report
    for n, line in enumerate(text.splitlines(), 1):
        for dash in DASHES:
            if dash in line:
                report.add("SV014", "error", n, f"U+{ord(dash):04X} dash; use - or --")
    try:
        root = parse(text)
    except DeclarationError as exc:
        report.add("SV001", "error", exc.line, f"{exc}; refused for safety")
        return report
    except expat.ExpatError as exc:
        report.add(
            "SV001", "error", exc.lineno, f"XML parse error: {expat.errors.messages[exc.code]}"
        )
        return report
    except IndexError:
        report.add("SV001", "error", 1, "no root element")
        return report

    if root.tag != "svg":
        report.add("SV002", "error", root.line, f"root element is <{root.tag}>, not <svg>")
    if root.ns != SVG_NS:
        severity = "warn" if web else "error"
        report.add("SV004", severity, root.line, f'root needs xmlns="{SVG_NS}"')
    box = (root.attr("viewBox") or "").replace(",", " ").split()
    try:
        ok_box = len(box) == 4 and float(box[2]) > 0 and float(box[3]) > 0
    except ValueError:
        ok_box = False
    if not ok_box:
        report.add("SV003", "error", root.line, "root needs viewBox with positive width and height")

    seen: dict[str, int] = {}
    for node in root.iter():
        if node.tag == "script":
            report.add(
                "SV005", "error", node.line, "<script> does not run in SVG images; remove it"
            )
        if node.tag == "foreignObject":
            report.add("SV007", "warn" if web else "error", node.line, "<foreignObject> is blocked")
        for key, value in node.attrs.items():
            ns, local = split(key)
            if re.fullmatch(r"on[a-z]+", local.lower()):
                report.add("SV006", "error", node.line, f"event handler attribute {local}")
            if local in ("href", "src") and ns in ("", XLINK_NS):
                check_ref(report, node.line, f"<{node.tag}> {local}", value, web)
            elif local != "style":
                for m in URL_REF.finditer(value):
                    check_ref(report, node.line, f"<{node.tag}> {local}", m.group(2), web)
        if node.attr("pathLength") is not None:
            effect = node.attr("vector-effect") or ""
            style = node.attr("style") or ""
            if "non-scaling-stroke" in effect or re.search(
                r"vector-effect\s*:\s*non-scaling", style
            ):
                report.add(
                    "SV019",
                    "warn",
                    node.line,
                    f"<{node.tag}> pathLength with non-scaling-stroke stops line draws short",
                )
        ident = node.attr("id")
        if ident:
            if ident in seen:
                report.add("SV012", "error", node.line, f'id "{ident}" repeats line {seen[ident]}')
            else:
                seen[ident] = node.line

    a11y_checks(report, root)
    smil = smil_checks(report, root)
    css = css_checks(report, root, web)
    animated = len(smil.pop("smil_parents")) + css["css_elements"]  # type: ignore[arg-type]
    if animated > MAX_ANIMATED:
        report.add(
            "SV015", "warn", 1, f"{animated} animated elements; above {MAX_ANIMATED} reads as noise"
        )
    durations = smil["smil_durations"] + css["css_durations"]  # type: ignore[operator]
    report.stats.update(
        {
            "smil": smil["smil"],
            "keyframes": css["keyframes"],
            "animated_elements": animated,
            "longest_s": round(max(durations), 3) if durations else 0,
            "infinite": smil["smil_infinite"] + css["css_infinite"],  # type: ignore[operator]
            "reduced_motion_query": any(
                "prefers-reduced-motion" in t for _, t in style_texts(root)
            ),
        }
    )
    if contrast != "off":
        themes = tuple(GITHUB_PAGES) if theme == "both" else (theme,)
        report.stats["contrast"] = contrast_checks(report, root, contrast == "error", themes)
    report.findings.sort(key=lambda f: (f.line, f.rule))
    return report


def validate_file(
    path: Path,
    target: str = "standalone",
    max_kb: float | None = None,
    contrast: str = "off",
    theme: str = "both",
) -> Report:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        report = Report(path.as_posix(), target)
        report.add("SV001", "error", 0, f"cannot read file: {exc.strerror or exc}")
        return report
    return validate_text(raw, path.as_posix(), target, max_kb, contrast, theme)


def expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for item in paths:
        p = Path(item)
        out.extend(sorted(p.rglob("*.svg")) if p.is_dir() else [p])
    return out


def summary(r: Report) -> str:
    s = r.stats
    state = "ok" if r.errors == 0 else "FAIL"
    head = f"{r.file}: {state} ({r.errors} errors, {r.warnings} warnings)"
    if "smil" not in s:
        return head
    kb = int(s["bytes"]) / 1024  # type: ignore[call-overload]
    return (
        f"{head} {kb:.1f} KB; {s['smil']} SMIL, {s['keyframes']} @keyframes, "
        f"{s['animated_elements']} animated elements, longest {s['longest_s']}s, "
        f"{s['infinite']} infinite"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate_svg.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", help="SVG files, or folders to scan for *.svg")
    ap.add_argument("--target", choices=list(BUDGET_KB), default="standalone")
    ap.add_argument("--max-kb", type=float, help="error above this size; warn above half")
    ap.add_argument("--json", action="store_true", help="print machine-readable results")
    ap.add_argument(
        "--strict-contrast", action="store_true", help="make SV021-SV023 errors, not warnings"
    )
    ap.add_argument(
        "--theme",
        choices=["both", *GITHUB_PAGES],
        default="both",
        help="GitHub theme(s) a file without its own background is shown on (default both)",
    )
    args = ap.parse_args(argv)
    contrast = "error" if args.strict_contrast else "warn"
    files = expand(args.files)
    if not files:
        print("validate_svg.py: no SVG files found", file=sys.stderr)
        return 1
    reports = [validate_file(p, args.target, args.max_kb, contrast, args.theme) for p in files]
    if args.json:
        print(json.dumps([r.as_dict() for r in reports], indent=2))
    else:
        for r in reports:
            print(summary(r))
            for f in r.findings:
                print(f"  {f.severity:<5} {f.rule} line {f.line}: {f.message}")
    return 1 if any(r.errors for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
