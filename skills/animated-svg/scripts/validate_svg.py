#!/usr/bin/env python3
"""Check SVG files for render-target safety, accessibility, weight and animation hygiene.

Usage: validate_svg.py FILE_OR_DIR... [--target standalone|web] [--max-kb N] [--json]

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

Exit status: 1 when any file has an error, 0 when there are only warnings or none.
"""

from __future__ import annotations

import argparse
import itertools
import json
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
}

URL_REF = re.compile(r"url\(\s*(['\"]?)([^'\")]*)\1\s*\)", re.I)
CLOCK = re.compile(r"^\s*(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)\s*(h|min|s|ms)?\s*$")
CSS_TIME = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b", re.I)
CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
KEYFRAMES = re.compile(r"@(?:-webkit-)?keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", re.I)


@dataclass
class Finding:
    rule: str
    severity: str  # error | warn
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


def validate_text(
    raw: bytes, name: str = "<svg>", target: str = "standalone", max_kb: float | None = None
) -> Report:
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
    report.findings.sort(key=lambda f: (f.line, f.rule))
    return report


def validate_file(path: Path, target: str = "standalone", max_kb: float | None = None) -> Report:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        report = Report(path.as_posix(), target)
        report.add("SV001", "error", 0, f"cannot read file: {exc.strerror or exc}")
        return report
    return validate_text(raw, path.as_posix(), target, max_kb)


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
    args = ap.parse_args(argv)
    files = expand(args.files)
    if not files:
        print("validate_svg.py: no SVG files found", file=sys.stderr)
        return 1
    reports = [validate_file(p, args.target, args.max_kb) for p in files]
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
