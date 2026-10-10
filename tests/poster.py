"""Poster check: what a static renderer (link preview, resvg, PNG export) would draw.

Strip every SMIL animation and CSS animation, then list content left invisible. Allowed:
packets (circles that only exist while riding a path), spotlight overlays that sit on a
visible rect, and rotating alternates that share their position with a visible line.
"""

from __future__ import annotations

import re
from xml.dom import minidom

ANIMATIONS = {"animate", "animateTransform", "animateMotion", "set", "animateColor"}
KEYFRAMES = re.compile(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")


def _elements(node: minidom.Node) -> list[minidom.Element]:
    return [c for c in node.childNodes if c.nodeType == c.ELEMENT_NODE]


def _strip(node: minidom.Element) -> None:
    for child in _elements(node):
        if child.tagName in ANIMATIONS:
            node.removeChild(child)
        else:
            if child.tagName == "style":
                css = "".join(t.data for t in child.childNodes if t.nodeType == t.TEXT_NODE)
                css = re.sub(r"animation(?:-[\w-]+)?\s*:[^;}]*;?", "", KEYFRAMES.sub("", css))
                for t in list(child.childNodes):
                    child.removeChild(t)
                child.appendChild(child.ownerDocument.createTextNode(css))
            _strip(child)


def _num(el: minidom.Element, name: str, default: float = 0.0) -> float:
    value = el.getAttribute(name)
    return float(value) if value else default


def problems(svg: str) -> list[str]:
    doc = minidom.parseString(svg)
    root = doc.documentElement
    _strip(root)
    out: list[str] = []
    seen: list[tuple[minidom.Element, float]] = []

    def walk(el: minidom.Element, inherited: float, in_defs: bool) -> None:
        own = _num(el, "opacity", 1.0)
        eff = inherited * own
        if not in_defs:
            seen.append((el, eff))
        for child in _elements(el):
            walk(child, eff, in_defs or child.tagName in ("defs", "clipPath", "pattern"))

    walk(root, 1.0, False)
    visible_text = {
        (e.getAttribute("x"), e.getAttribute("y")) for e, o in seen if e.tagName == "text" and o > 0
    }
    visible_rects = [e for e, o in seen if e.tagName == "rect" and o > 0]
    for el, eff in seen:
        tag = el.tagName
        if "scale(0" in el.getAttribute("transform").replace(" ", ""):
            out.append(f"<{tag}> is scaled to 0")
        dash, offset = el.getAttribute("stroke-dasharray"), el.getAttribute("stroke-dashoffset")
        if (
            offset
            and float(offset) > 0
            and dash.split()
            and float(offset) >= float(dash.split()[0])
        ):
            out.append(f"<{tag}> line draw is left undrawn (dashoffset {offset})")
        if tag == "circle" and el.getAttribute("r") in ("0", "0.0"):
            out.append("<circle> has r=0")
        if eff > 0 or tag == "circle":
            continue
        if tag == "text" and (el.getAttribute("x"), el.getAttribute("y")) in visible_text:
            continue
        if tag == "rect" and any(
            abs(_num(el, "x") - _num(r, "x")) <= 1 and abs(_num(el, "y") - _num(r, "y")) <= 1
            for r in visible_rects
        ):
            continue
        text = el.toxml()[:80]
        out.append(f"<{tag}> hidden in the static frame: {text}")
    for clip in root.getElementsByTagName("clipPath"):
        for rect in clip.getElementsByTagName("rect"):
            if rect.getAttribute("width") in ("0", "0.0"):
                out.append("clipPath rect has width 0, so its content is hidden")
    return out
