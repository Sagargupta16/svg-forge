#!/usr/bin/env python3
"""Make an animated SVG smaller without breaking it (stdlib only, every result re-checked).

Usage: optimize_svg.py FILE... (--out PATH | --in-place | --check) [--precision 2]

Safe operations only:
  - drop XML comments outside <style>; legal comments (<!--! ... -->) stay
  - drop <metadata>, editor elements and attributes (Inkscape, Sodipodi, Sketch, Illustrator,
    Figma, Affinity and the rest of SVGO's editor namespace list) with their xmlns
    declarations, and Illustrator / Figma data-name and data-figma-* attributes unless CSS
    selects on [data-...]
  - drop whitespace between tags, never inside <text>, <tspan>, <textPath>, <title>, <desc>,
    <style>, <script> or <foreignObject>
  - drop a default attribute only when certain: opacity="1"; x="0" y="0" on rect, use,
    image and svg; cx="0" cy="0" on circle and ellipse; x1, y1, x2, y2 ="0" on line
  - round numbers to --precision decimals in d, points, shape x y width height cx cy r rx ry
    x1 y1 x2 y2, and translate / rotate / skew / matrix e f in transform; path commands stay
    as written and relative coordinates are snapped against the rounded pen, so error never
    accumulates

Never: removes or renames an id; drops an element that renders (opacity="0" fade-in start
states stay); touches <animate*>, <set> or <style> (values, keyTimes, keySplines and
@keyframes stay byte-identical); merges or moves groups; rounds viewBox, scale() or the
matrix a-d factors; rounds shape geometry without pathLength in a file that uses stroke-dash
(the drawn length would change); rounds anything in a file with objectBoundingBox content
units (coordinates there are fractions).

After optimizing, the output must parse, have no validate_svg.py error the input did not
have, keep every id, and keep the animation inventory (animate*/set elements and their
attributes, @keyframes names, <style> text). If any check fails nothing is written.

Exit status: 1 when any file is refused or unreadable, 0 otherwise (--check included).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from xml.parsers import expat

import validate_svg

SVG_NS = validate_svg.SVG_NS
XML_NS = "http://www.w3.org/XML/1998/namespace"
SMIL = validate_svg.SMIL
XML_SPACE = " \t\n\r"
# same list as SVGO's removeEditorsNSData (plugins/_collections.js, editorNamespaces)
EDITOR_NS = frozenset(
    {
        "http://creativecommons.org/ns#",
        "http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd",
        "http://krita.org/namespaces/svg/krita",
        "http://ns.adobe.com/AdobeIllustrator/10.0/",
        "http://ns.adobe.com/AdobeSVGViewerExtensions/3.0/",
        "http://ns.adobe.com/Extensibility/1.0/",
        "http://ns.adobe.com/Flows/1.0/",
        "http://ns.adobe.com/GenericCustomNamespace/1.0/",
        "http://ns.adobe.com/Graphs/1.0/",
        "http://ns.adobe.com/ImageReplacement/1.0/",
        "http://ns.adobe.com/SaveForWeb/1.0/",
        "http://ns.adobe.com/Variables/1.0/",
        "http://ns.adobe.com/XPath/1.0/",
        "http://purl.org/dc/elements/1.1/",
        "http://schemas.microsoft.com/visio/2003/SVGExtensions/",
        "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
        "http://taptrix.com/vectorillustrator/svg_extensions",
        "http://www.bohemiancoding.com/sketch/ns",
        "http://www.figma.com/figma/ns",
        "http://www.inkscape.org/namespaces/inkscape",
        "http://www.serif.com/",
        "http://www.vector.evaxdesign.sk",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "https://boxy-svg.com",
    }
)
# whitespace inside these is content; between other tags it never renders
KEEP_SPACE = {
    "text",
    "tspan",
    "textPath",
    "tref",
    "title",
    "desc",
    "style",
    "script",
    "foreignObject",
}
XY = {"x", "y"}
XYWH = {"x", "y", "width", "height"}
GEOMETRY = {
    "path": {"d"},
    "polyline": {"points"},
    "polygon": {"points"},
    "rect": XYWH | {"rx", "ry"},
    "circle": {"cx", "cy", "r"},
    "ellipse": {"cx", "cy", "rx", "ry"},
    "line": {"x1", "y1", "x2", "y2"},
    "image": XYWH,
    "use": XYWH,
    "svg": XYWH,
    "foreignObject": XYWH,
    "text": XY,
    "tspan": XY,
}
SHAPES = {"path", "polyline", "polygon", "rect", "circle", "ellipse", "line"}
ZERO = {"0"}
DEFAULTS = {
    "rect": {"x": ZERO, "y": ZERO},
    "use": {"x": ZERO, "y": ZERO},
    "image": {"x": ZERO, "y": ZERO},
    "svg": {"x": {"0", "0px"}, "y": {"0", "0px"}},
    "circle": {"cx": ZERO, "cy": ZERO},
    "ellipse": {"cx": ZERO, "cy": ZERO},
    "line": {"x1": ZERO, "y1": ZERO, "x2": ZERO, "y2": ZERO},
}
BBOX_UNITS = re.compile(
    r"(?:clipPathUnits|maskContentUnits|patternContentUnits)\s*=\s*[\"']objectBoundingBox"
)
NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
FLAG = re.compile(r"[01]")
PATH_SEP = " \t\n\r\f,"
PATH_ARITY = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}
# per argument: the axis a coordinate moves (0 x, 1 y), or None for radii, angles and flags
PATH_AXES: dict[str, tuple[int | None, ...]] = {
    "M": (0, 1),
    "L": (0, 1),
    "T": (0, 1),
    "H": (0,),
    "V": (1,),
    "C": (0, 1, 0, 1, 0, 1),
    "S": (0, 1, 0, 1),
    "Q": (0, 1, 0, 1),
    "A": (None, None, None, None, None, 0, 1),
}
TRANSFORM_FN = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^()]*)\)")
ROUNDED_ARGS = {
    "translate": slice(None),
    "rotate": slice(None),
    "skewX": slice(None),
    "skewY": slice(None),
    "matrix": slice(4, 6),
    "scale": slice(0),
}
KEYFRAME_NAME = re.compile(r"@(?:-webkit-)?keyframes\s+([\w-]+)", re.I)
LEAF_FORMAT = {"cdata": "<![CDATA[{}]]>", "comment": "<!--{}-->", "pi": "<?{}?>"}
# dashes go back to character references, so a file that spelled them that way still passes
# validate_svg.py SV014 (it flags raw dash characters only)
DASH_REFS = tuple((d, f"&#{ord(d)};") for d in validate_svg.DASHES)
TEXT_REFS = (("&", "&amp;"), ("<", "&lt;"), ("]]>", "]]&gt;"), ("\r", "&#13;"), *DASH_REFS)
ATTR_REFS = (("&", "&amp;"), ("<", "&lt;"), ('"', "&quot;"), ("\t", "&#9;"), ("\n", "&#10;"))
ATTR_REFS += (("\r", "&#13;"), *DASH_REFS)


# ---------------------------------------------------------------- numbers


def snap(value: Decimal, precision: int) -> Decimal:
    """Round half up onto the 10^-precision grid; shifting by a grid step commutes with it."""
    grid = Decimal(1).scaleb(-precision)
    return (value + grid / 2).quantize(grid, rounding=ROUND_FLOOR)


def fmt(value: Decimal, like: str) -> str:
    """Shortest text for value, without a leading zero when the original had none."""
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    if like.lstrip("+-").startswith(".") and text.lstrip("-").startswith("0."):
        text = text.replace("0.", ".", 1)
    return text


def rounded(token: str, precision: int) -> str | None:
    """The token rounded to precision decimals, or None when it already fits."""
    if "e" in token.lower() or "." not in token:
        return None
    if len(token.split(".")[1]) <= precision:
        return None
    return fmt(snap(Decimal(token), precision), token)


def merges(left: str, right: str) -> bool:
    """True when right written straight after left would read as one number."""
    if right[0] in "+-":
        return False
    if right[0] == ".":
        return "." not in left and "e" not in left.lower()
    return True


def rebuild(value: str, spans: list[tuple[int, int]], new: dict[int, str]) -> str:
    """Swap the replaced number tokens in, adding a space only where two would merge."""
    out: list[str] = []
    pos = 0
    prev = ""
    for i, (start, end) in enumerate(spans):
        gap = value[pos:start]
        text = new.get(i, value[start:end])
        if not gap and i and (i in new or i - 1 in new) and merges(prev, text):
            gap = " "
        out += [gap, text]
        prev, pos = text, end
    out.append(value[pos:])
    return "".join(out)


def round_numbers(value: str, precision: int) -> str:
    """Round every number in a length or list attribute (x, points, width, ...)."""
    spans = [m.span() for m in NUM.finditer(value)]
    new = {}
    for i, (start, end) in enumerate(spans):
        text = rounded(value[start:end], precision)
        if text is not None:
            new[i] = text
    return rebuild(value, spans, new)


def round_transform(value: str, precision: int) -> str:
    """Round translate, rotate and skew arguments and matrix e f; scale and a-d keep."""
    if TRANSFORM_FN.sub("", value).strip(XML_SPACE + ","):
        return value  # not a plain transform list; leave it alone
    spans: list[tuple[int, int]] = []
    new: dict[int, str] = {}
    for fn in TRANSFORM_FN.finditer(value):
        args = list(NUM.finditer(value, fn.start(2), fn.end(2)))
        eligible = range(len(args))[ROUNDED_ARGS[fn.group(1)]]
        for k, m in enumerate(args):
            text = rounded(m.group(), precision) if k in eligible else None
            if text is not None:
                new[len(spans)] = text
            spans.append(m.span())
    return rebuild(value, spans, new)


def skip_sep(d: str, pos: int) -> int:
    while pos < len(d) and d[pos] in PATH_SEP:
        pos += 1
    return pos


def path_segments(d: str) -> tuple[list[tuple[int, int]], list[tuple[str, list[int]]]] | None:
    """Token spans and (command, token indexes) per segment, or None if d does not parse."""
    spans: list[tuple[int, int]] = []
    segments: list[tuple[str, list[int]]] = []
    pos, cmd = 0, ""
    while True:
        pos = skip_sep(d, pos)
        if pos == len(d):
            return spans, segments
        if d[pos] in "MmLlTtHhVvCcSsQqAaZz":
            cmd = d[pos]
            pos += 1
        elif not cmd or cmd in "Zz":
            return None
        indexes = []
        for k in range(PATH_ARITY[cmd.upper()]):
            pos = skip_sep(d, pos)
            m = (FLAG if cmd in "Aa" and k in (3, 4) else NUM).match(d, pos)
            if m is None:
                return None
            indexes.append(len(spans))
            spans.append(m.span())
            pos = m.end()
        segments.append((cmd, indexes))
        cmd = {"M": "L", "m": "l"}.get(cmd, cmd)


def round_path(d: str, precision: int) -> str:
    """Round path coordinates, keeping every command and argument in place."""
    parsed = path_segments(d)
    if parsed is None:
        return d
    spans, segments = parsed
    tokens = [d[a:b] for a, b in spans]
    new: dict[int, str] = {}
    zero = Decimal(0)
    pen, snapped_pen = [zero, zero], [zero, zero]
    start, snapped_start = [zero, zero], [zero, zero]
    for cmd, indexes in segments:
        upper = cmd.upper()
        if upper == "Z":
            pen, snapped_pen = start[:], snapped_start[:]
            continue
        relative = cmd != upper
        base, snapped_base = pen[:], snapped_pen[:]
        for k, i in enumerate(indexes):
            axis = PATH_AXES[upper][k]
            if axis is None:
                text = None if upper == "A" and k in (3, 4) else rounded(tokens[i], precision)
                if text is not None:
                    new[i] = text
                continue
            value = Decimal(tokens[i])
            true = base[axis] + value if relative else value
            on_grid = snap(true, precision)
            out = on_grid - snapped_base[axis] if relative else on_grid
            if out != value:
                new[i] = fmt(out, tokens[i])
            pen[axis], snapped_pen[axis] = true, on_grid  # the last pair is the end point
        if upper == "M":
            start, snapped_start = pen[:], snapped_pen[:]
    out_d = rebuild(d, spans, new)
    return out_d if len(out_d) <= len(d) else d


# ---------------------------------------------------------------- tree


@dataclass
class Leaf:
    kind: str  # text | cdata | comment | pi
    data: str


@dataclass
class Elem:
    name: str  # qualified name as written
    attrs: list[tuple[str, str]]
    ns: str
    scope: dict[str, str]
    children: list[Elem | Leaf] = field(default_factory=list)

    @property
    def local(self) -> str:
        return self.name.rpartition(":")[2]

    def get(self, name: str) -> str | None:
        return next((v for k, v in self.attrs if k == name), None)

    def iter(self):  # noqa: ANN201 - generator of Elem
        yield self
        for child in self.children:
            if isinstance(child, Elem):
                yield from child.iter()


@dataclass
class Doc:
    decl: str
    items: list[Elem | Leaf]  # prolog and epilog comments / PIs around the root

    @property
    def root(self) -> Elem:
        return next(i for i in self.items if isinstance(i, Elem))


def parse_doc(text: str) -> Doc:
    """Parse without namespace processing so prefixes and attribute order survive."""
    parser = expat.ParserCreate()
    parser.ordered_attributes = True
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    doc = Doc("", [])
    stack: list[Elem] = []
    in_cdata = False

    def refuse(*_args: object) -> None:
        raise ValueError("DOCTYPE or ENTITY declaration")

    def decl(version: str, encoding: str | None, standalone: int) -> None:
        enc = ' encoding="UTF-8"' if encoding else ""
        alone = {1: ' standalone="yes"', 0: ' standalone="no"'}.get(standalone, "")
        doc.decl = f'<?xml version="{version}"{enc}{alone}?>'

    def add(node: Elem | Leaf) -> None:
        (stack[-1].children if stack else doc.items).append(node)

    def start(name: str, flat: list[str]) -> None:
        attrs = list(zip(flat[::2], flat[1::2], strict=True))
        scope = stack[-1].scope if stack else {"xml": XML_NS}
        decls = {k.partition(":")[2]: v for k, v in attrs if k == "xmlns" or k[:6] == "xmlns:"}
        if decls:
            scope = {**scope, **decls}
        prefix = name.rpartition(":")[0]
        node = Elem(name, attrs, scope.get(prefix, ""), scope)
        add(node)
        stack.append(node)

    def end(_name: str) -> None:
        stack.pop()

    def chars(data: str) -> None:
        if not stack:
            return  # whitespace around the root
        kids = stack[-1].children
        kind = "cdata" if in_cdata else "text"
        if kids and isinstance(kids[-1], Leaf) and kids[-1].kind == kind:
            kids[-1].data += data
        else:
            kids.append(Leaf(kind, data))

    def cdata_start() -> None:
        nonlocal in_cdata
        in_cdata = True
        stack[-1].children.append(Leaf("cdata", ""))

    def cdata_end() -> None:
        nonlocal in_cdata
        in_cdata = False

    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.XmlDeclHandler = decl
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    parser.StartCdataSectionHandler = cdata_start
    parser.EndCdataSectionHandler = cdata_end
    parser.CommentHandler = lambda data: add(Leaf("comment", data))
    parser.ProcessingInstructionHandler = lambda target, data: add(
        Leaf("pi", f"{target} {data}" if data else target)
    )
    parser.Parse(text, True)
    return doc


def referenced(text: str, ident: str) -> bool:
    """True when the id appears anywhere besides its own id attribute."""
    pattern = rf"(?<![\w.:-]){re.escape(ident)}(?![\w:-])"
    return len(re.findall(pattern, text)) > 1


class Optimizer:
    def __init__(self, text: str, precision: int) -> None:
        self.text = text
        self.precision = precision
        self.round_ok = not BBOX_UNITS.search(text)
        self.dash = "stroke-dash" in text
        self.drop_data = not re.search(r"\[\s*data-", text)  # no CSS [data-...] selector

    def run(self, doc: Doc) -> Doc:
        items: list[Elem | Leaf] = []
        for item in doc.items:
            if isinstance(item, Elem):
                items.append(self.element(item, keep_space=False) or item)
            elif item.kind == "pi" or item.data.startswith("!"):
                items.append(item)
        return Doc(doc.decl, items)

    def droppable(self, el: Elem) -> bool:
        if el.ns not in EDITOR_NS and not (el.ns == SVG_NS and el.local == "metadata"):
            return False
        ids = [i for node in el.iter() if (i := node.get("id"))]
        return not any(referenced(self.text, i) for i in ids)

    def element(self, el: Elem, keep_space: bool) -> Elem | None:
        if self.droppable(el):
            return None
        svg = el.ns in (SVG_NS, "")
        if svg and el.local in SMIL:
            attrs = list(el.attrs)  # animation elements are never touched
        else:
            attrs = [a for k, v in el.attrs if (a := self.attribute(el, svg, k, v))]
        keep_space = keep_space or not svg or el.local in KEEP_SPACE
        children: list[Elem | Leaf] = []
        for child in el.children:
            if isinstance(child, Elem):
                kept = self.element(child, keep_space)
                if kept is not None:
                    children.append(kept)
            elif child.kind == "comment":
                if el.local == "style" or child.data.startswith("!"):
                    children.append(child)
            elif child.kind == "text" and not keep_space and not child.data.strip(XML_SPACE):
                continue
            else:
                children.append(child)
        return Elem(el.name, attrs, el.ns, el.scope, children)

    def attribute(self, el: Elem, svg: bool, name: str, value: str) -> tuple[str, str] | None:
        prefix = name.rpartition(":")[0]
        if name == "xmlns" or prefix == "xmlns":
            return name, value  # unused editor declarations go at serialization
        if prefix:
            return None if el.scope.get(prefix) in EDITOR_NS else (name, value)
        if not svg:
            return name, value
        if self.drop_data and (name == "data-name" or name.startswith("data-figma")):
            return None
        if value in DEFAULTS.get(el.local, {}).get(name, ()) or (name, value) == ("opacity", "1"):
            return None
        return name, self.round_attr(el, name, value)

    def round_attr(self, el: Elem, name: str, value: str) -> str:
        if not self.round_ok:
            return value
        if name == "transform":
            return round_transform(value, self.precision)
        if name not in GEOMETRY.get(el.local, ()):
            return value
        if self.dash and el.local in SHAPES and el.get("pathLength") is None:
            return value  # rounding changes the length a stroke-dash line draw was built for
        if name == "d":
            return round_path(value, self.precision)
        return round_numbers(value, self.precision)


# ---------------------------------------------------------------- output


def escape(value: str, pairs: tuple[tuple[str, str], ...]) -> str:
    for raw, ref in pairs:
        value = value.replace(raw, ref)
    return value


def prefixes(el: Elem, used: set[str]) -> set[str]:
    for name in [el.name, *(k for k, _ in el.attrs)]:
        prefix = name.rpartition(":")[0]
        if prefix and prefix != "xmlns":
            used.add(prefix)
    for child in el.children:
        if isinstance(child, Elem):
            prefixes(child, used)
    return used


def emit(node: Elem | Leaf, used: set[str], out: list[str]) -> None:
    if isinstance(node, Leaf):
        if node.kind == "text":
            out.append(escape(node.data, TEXT_REFS))
        else:
            out.append(LEAF_FORMAT[node.kind].format(node.data))
        return
    out.append(f"<{node.name}")
    for name, value in node.attrs:
        if name[:6] == "xmlns:" and value in EDITOR_NS and name[6:] not in used:
            continue
        out.append(f' {name}="{escape(value, ATTR_REFS)}"')
    if not node.children:
        out.append("/>")
        return
    out.append(">")
    for child in node.children:
        emit(child, used, out)
    out.append(f"</{node.name}>")


def serialize(doc: Doc) -> str:
    used = prefixes(doc.root, set())
    out = [doc.decl]
    for item in doc.items:
        emit(item, used, out)
    return "".join(out) + "\n"


def optimize(text: str, precision: int = 2) -> str:
    """The optimized document; the input must already parse (see run)."""
    return serialize(Optimizer(text, precision).run(parse_doc(text)))


# ---------------------------------------------------------------- verification


def content_ids(root: validate_svg.Node) -> set[str]:
    """Ids outside <metadata> and editor-namespace elements (those may be dropped)."""
    out: set[str] = set()

    def walk(node: validate_svg.Node) -> None:
        if node.ns in EDITOR_NS or (node.ns == SVG_NS and node.tag == "metadata"):
            return
        if ident := node.attr("id"):
            out.add(ident)
        for child in node.children:
            walk(child)

    walk(root)
    return out


def inventory(root: validate_svg.Node) -> dict[str, object]:
    """Animation inventory: animate*/set counts by tag and @keyframes names."""
    smil = Counter(n.tag for n in root.iter() if n.tag in SMIL)
    css = "".join("".join(n.text) for n in root.iter() if n.tag == "style")
    return {"smil": dict(sorted(smil.items())), "keyframes": sorted(KEYFRAME_NAME.findall(css))}


def animation_attrs(root: validate_svg.Node) -> list[dict[str, str]]:
    return [n.attrs for n in root.iter() if n.tag in SMIL]


def style_texts(root: validate_svg.Node) -> list[str]:
    return ["".join(n.text) for n in root.iter() if n.tag == "style"]


def verify(before: bytes, after: bytes) -> list[str]:
    """Reasons the optimized bytes are not safe to write; empty when they are."""
    report = validate_svg.validate_text(after)
    broken = [f.message for f in report.findings if f.rule == "SV001"]
    if broken:
        return [f"output does not parse: {broken[0]}"]
    problems = []
    errors_before = Counter(
        f.rule for f in validate_svg.validate_text(before).findings if f.severity == "error"
    )
    errors_after = Counter(f.rule for f in report.findings if f.severity == "error")
    for rule, n in sorted((errors_after - errors_before).items()):
        first = next(f for f in report.findings if f.rule == rule and f.severity == "error")
        problems.append(f"{n} new {rule} error(s): {first.message}")
    text = before.decode("utf-8-sig")
    old = validate_svg.parse(text)
    new = validate_svg.parse(after.decode("utf-8"))
    old_ids = {i for n in old.iter() if (i := n.attr("id"))}
    new_ids = {i for n in new.iter() if (i := n.attr("id"))}
    keep = content_ids(old)
    keep |= {i for i in old_ids - keep if referenced(text, i)}
    if lost := sorted(keep - new_ids):
        problems.append(f"ids lost: {', '.join(lost)}")
    if inventory(old) != inventory(new):
        problems.append(f"animation inventory changed: {inventory(old)} -> {inventory(new)}")
    if animation_attrs(old) != animation_attrs(new):
        problems.append("animate/set attributes changed")
    if style_texts(old) != style_texts(new):
        problems.append("<style> text changed")
    return problems


def run(raw: bytes, precision: int = 2) -> tuple[bytes, list[str]]:
    """Optimize and verify; returns (output bytes, reasons to refuse)."""
    report = validate_svg.validate_text(raw)
    broken = [f.message for f in report.findings if f.rule == "SV001"]
    if broken:
        return raw, [f"input does not parse: {broken[0]}"]
    after = optimize(raw.decode("utf-8-sig"), precision).encode("utf-8")
    return after, verify(raw, after)


# ---------------------------------------------------------------- CLI


def saved(before: int, after: int) -> str:
    return f"{before} -> {after} bytes, {100 * (before - after) / before:.1f}% saved"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="optimize_svg.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="+", type=Path, help="SVG files to optimize")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path, help="output file, or a folder for several files")
    mode.add_argument("--in-place", action="store_true", help="overwrite each input")
    mode.add_argument("--check", action="store_true", help="report the savings, write nothing")
    ap.add_argument("--precision", type=int, default=2, help="decimals to keep (default 2)")
    args = ap.parse_args(argv)
    if args.precision < 0:
        ap.error("--precision must be 0 or more")
    to_dir = args.out is not None and (len(args.files) > 1 or args.out.is_dir())
    names = [p.name for p in args.files]
    if to_dir and len(set(names)) != len(names):
        ap.error("--out folder: two inputs share a file name")
    failed = 0
    total = [0, 0]
    for path in args.files:
        shown = path.as_posix()
        try:
            raw = path.read_bytes()
        except OSError as exc:
            print(f"{shown}: cannot read: {exc.strerror or exc}", file=sys.stderr)
            failed += 1
            continue
        after, problems = run(raw, args.precision)
        if problems:
            print(f"{shown}: refused, nothing written: {'; '.join(problems)}", file=sys.stderr)
            failed += 1
            continue
        if args.in_place and after != raw:
            path.write_bytes(after)
        elif args.out is not None:
            dest = args.out / path.name if to_dir else args.out
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(after)
        note = " (check only, nothing written)" if args.check else ""
        print(f"{shown}: {saved(len(raw), len(after))}{note}")
        total[0] += len(raw)
        total[1] += len(after)
    if len(args.files) > 1 and total[0]:
        print(f"total: {saved(*total)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
