#!/usr/bin/env python3
"""Render moments of an animated SVG's timeline into one PNG contact sheet.

Usage: frames.py FILE.svg [--frames 6] [--times 0,0.5,1.2] [--duration auto|SECONDS]
                 [--width 360] [--cols 3] [--theme dark|light|both] [--out SHEET.png]
                 [--html-only] [--browser PATH]

The cycle (--duration auto) is the longest finite play in the file: SMIL begin + dur x
repeatCount (or repeatDur), following syncbase begins such as begin="0s;d3.end", and CSS
animation-delay + animation-duration x animation-iteration-count. Anything that repeats
forever counts one play. Default frames spread evenly from t=0 to the last frame before
the loop restarts (one 60 Hz frame before the cycle ends), or to the end state when nothing
loops, so the start and the seam are both on the sheet. Each caption shows t and k, the
keyTimes position t / cycle.

Each frame is an <iframe srcdoc> (ids stay isolated; scripts and network are blocked, as in
an <img>) that is paused and seeked: SMIL with pauseAnimations() + setCurrentTime(t), CSS
with getAnimations() pause() + currentTime. A headless Chrome, Edge or Chromium found on
PATH or in the usual install folders (or --browser) screenshots the page. The HTML sheet is
always written next to the PNG (SHEET.html) and can be opened in any browser.

Exit status: 0 every file asked for was written; 1 unreadable SVG, or the browser wrote no
PNG; 2 bad arguments; 3 no browser found, so only the HTML sheet was written (pass
--html-only to ask for just the HTML and get 0).
"""

from __future__ import annotations

import argparse
import html
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.parsers import expat

import validate_svg

THEMES = {"dark": ("#0d1117", "#8b949e"), "light": ("#ffffff", "#57606a")}  # page, caption
FRAME_S = 1 / 60  # one display frame at 60 Hz: the last frame shown before a loop restarts
PAD, GAP, HEAD, CAP = 12, 12, 24, 20  # sheet layout in px; sheet_size() mirrors the CSS
BUDGET_MS = 3000
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
BROWSERS = (
    "google-chrome",
    "google-chrome-stable",
    "chrome",
    "chromium",
    "chromium-browser",
    "msedge",
    "microsoft-edge",
    "microsoft-edge-stable",
)

SYNCBASE = re.compile(r"^(.+)\.(begin|end)\s*(?:([+-])\s*(\S.*))?$")
CSS_SECONDS = re.compile(r"^([+-]?\d*\.?\d+)(ms|s)$", re.I)
NUMBER = re.compile(r"^\d*\.?\d+$")
FUNCTION = re.compile(r"[\w-]+\([^()]*\)")
COMMENT = re.compile(r"/\*.*?\*/", re.S)
REDUCED = re.compile(
    r"@media[^{]*prefers-reduced-motion\s*:\s*reduce[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", re.I
)
LONGHANDS = ("animation-duration", "animation-delay", "animation-iteration-count")
LENGTH = re.compile(r"^\s*(\d*\.?\d+)\s*(?:px)?\s*$")

SEEK = """<script>
function seek(frame) {
  const t = Number(frame.dataset.t), doc = frame.contentDocument;
  if (!doc) return;
  for (const svg of doc.querySelectorAll("svg")) {
    if (!svg.ownerSVGElement && svg.pauseAnimations) {
      svg.pauseAnimations();
      svg.setCurrentTime(t);
    }
  }
  for (const a of doc.getAnimations()) {
    a.pause();
    a.currentTime = t * 1000;
  }
}
addEventListener("load", () => {
  const frames = [...document.querySelectorAll("iframe[data-t]")];
  frames.forEach(seek);
  requestAnimationFrame(() => {
    frames.forEach(seek);
    document.body.dataset.seeked = String(frames.length);
  });
});
</script>"""


def offset(token: str) -> float | None:
    """Signed SMIL offset: 2s, -0.5s, +120ms, 1.5."""
    token = token.strip()
    value = validate_svg.seconds(token.lstrip("+-"))
    if value is None:
        return None
    return -value if token.startswith("-") else value


def resolve(token: str, starts: dict[str, float], ends: dict[str, float]) -> float | None:
    """One begin value: an offset or id.begin / id.end (+/- offset). Events stay None."""
    m = SYNCBASE.match(token.strip())
    if not m:
        return offset(token)
    ref, edge, sign, shift = m.groups()
    base = (starts if edge == "begin" else ends).get(ref)
    delta = validate_svg.seconds(shift) if shift else 0.0
    if base is None or delta is None:
        return None
    return base - delta if sign == "-" else base + delta


def active(node: validate_svg.Node) -> float | None:
    """Length of one SMIL interval: dur x repeatCount or repeatDur; None when it never ends."""
    rc, rd = node.attr("repeatCount"), node.attr("repeatDur")
    if "indefinite" in (rc, rd):
        return None
    dur = validate_svg.seconds(node.attr("dur"))
    if dur is None:
        return 0.0  # <set> or dur="indefinite": the change lands at begin
    lengths = []
    if rc is not None:
        try:
            lengths.append(dur * float(rc))
        except ValueError:
            pass
    repeat_dur = validate_svg.seconds(rd)
    if repeat_dur is not None:
        lengths.append(repeat_dur)
    return min(lengths) if lengths else dur


def begin_times(
    node: validate_svg.Node, starts: dict[str, float], ends: dict[str, float]
) -> tuple[list[float], list[float]]:
    """(offset begins, syncbase begins) that resolve so far; events and indefinite drop out."""
    offsets: list[float] = []
    synced: list[float] = []
    for token in (node.attr("begin") or "0s").split(";"):
        value = resolve(token, starts, ends)
        if value is not None:
            (synced if SYNCBASE.match(token.strip()) else offsets).append(value)
    return offsets, synced


def smil_cycles(root: validate_svg.Node) -> list[tuple[float, bool]]:
    """(one play in seconds, loops) for every SMIL animation that starts on its own."""
    anims = [n for n in root.iter() if n.tag in validate_svg.SMIL]
    begins: dict[int, tuple[list[float], list[float]]] = {}
    starts: dict[str, float] = {}
    ends: dict[str, float] = {}
    for _ in range(len(anims) + 1):  # syncbase chains settle in at most one pass per link
        changed = False
        for i, node in enumerate(anims):
            found = begin_times(node, starts, ends)
            if found == begins.get(i):
                continue
            begins[i], changed = found, True
            ident = node.attr("id")
            if ident and found[0] + found[1]:
                starts[ident] = min(found[0] + found[1])
                length = active(node)
                if length is not None:
                    ends[ident] = starts[ident] + length
        if not changed:
            break
    out = []
    for i, node in enumerate(anims):
        offsets, synced = begins.get(i, ([], []))
        if not offsets + synced:
            continue
        first = min(offsets + synced)
        length = active(node)
        if length is None:
            dur = validate_svg.seconds(node.attr("dur")) or 0.0
            out.append((max(first, 0.0) + dur, True))
        else:
            # plays again at each later offset; a later syncbase begin is a chained loop
            out.append((max(offsets, default=first) + length, any(t > first for t in synced)))
    return out


def css_seconds(token: str) -> float | None:
    m = CSS_SECONDS.match(token.strip())
    if not m:
        return None
    return float(m.group(1)) * (0.001 if m.group(2).lower() == "ms" else 1)


def css_count(token: str) -> float | None:
    token = token.strip().lower()
    if token == "infinite":
        return math.inf
    return float(token) if NUMBER.match(token) else None


def commas(value: str) -> list[str]:
    """Split a CSS list on top-level commas (not the ones inside cubic-bezier())."""
    return [p.strip() for p in FUNCTION.sub(" ", value).split(",") if p.strip()]


def css_block(body: str) -> list[tuple[float, bool]]:
    """(one play in seconds, loops) for each animation in one declaration block."""
    decls: dict[str, str] = {}
    for part in body.split(";"):
        name, sep, value = part.partition(":")
        if sep:
            decls[name.strip().lower()] = value.replace("!important", "").strip()
    plays: list[list[float]] = []  # [duration, delay, count]
    for item in commas(decls.get("animation", "")):
        tokens = item.split()
        times = [t for t in map(css_seconds, tokens) if t is not None]
        counts = [c for c in map(css_count, tokens) if c is not None]
        plays.append([*(times + [0.0, 0.0])[:2], counts[0] if counts else 1.0])
    lists = [commas(decls.get(key, "")) for key in LONGHANDS]
    out = []
    for i in range(max([len(plays)] + [len(v) for v in lists])):
        play = plays[i] if i < len(plays) else [0.0, 0.0, 1.0]
        parsers = (css_seconds, css_seconds, css_count)
        for slot, (values, parse) in enumerate(zip(lists, parsers, strict=True)):
            if values:
                parsed = parse(values[i % len(values)])
                play[slot] = parsed if parsed is not None else play[slot]
        duration, delay, count = play
        if duration <= 0:
            continue
        if math.isinf(count):
            out.append((max(delay, 0.0) + duration, True))
        else:
            out.append((max(delay + duration * count, 0.0), False))
    return out


def css_cycles(texts: list[str]) -> list[tuple[float, bool]]:
    """CSS plays from <style> text and style attributes; reduced-motion blocks are skipped."""
    out = []
    for css in texts:
        css = validate_svg.KEYFRAMES.sub("", REDUCED.sub("", COMMENT.sub("", css)))
        bodies = [body for _, body in validate_svg.CSS_RULE.findall(css)] or [css]
        for body in bodies:
            out.extend(css_block(body))
    return out


def timeline(root: validate_svg.Node) -> tuple[float, bool]:
    """(cycle seconds, loops): the longest finite play, and whether anything repeats."""
    cycles = smil_cycles(root) + css_cycles([t for _, t in validate_svg.style_texts(root)])
    if not cycles:
        return 0.0, False
    return round(max(c for c, _ in cycles), 3), any(loop for _, loop in cycles)


def frame_times(duration: float, loops: bool, count: int) -> list[float]:
    """count moments from t=0 to the last frame before the loop restarts (or the end)."""
    end = max(duration - FRAME_S, 0.0) if loops else duration
    if count == 1 or end <= 0:
        return [0.0]
    return [round(end * i / (count - 1), 3) for i in range(count)]


def aspect(root: validate_svg.Node) -> float:
    """Height / width from the viewBox, else width and height attributes, else 1."""
    box = (root.attr("viewBox") or "").replace(",", " ").split()
    try:
        w, h = float(box[2]), float(box[3])
    except (IndexError, ValueError):
        sizes = [LENGTH.match(root.attr(a) or "") for a in ("width", "height")]
        w, h = (float(m.group(1)) if m else 0.0 for m in sizes)
    return h / w if w > 0 and h > 0 else 1.0


def fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def sheet_size(n: int, cols: int, width: int, height: int, themes: int) -> tuple[int, int]:
    cols = min(cols, n)
    rows = math.ceil(n / cols)
    section = 2 * PAD + HEAD + rows * (CAP + height) + (rows - 1) * GAP
    return 2 * PAD + cols * width + (cols - 1) * GAP, section * themes


def srcdoc(svg: str, background: str) -> str:
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        f"<style>html,body{{margin:0;height:100%;overflow:hidden;background:{background}}}"
        "body>svg{display:block;width:100%!important;height:100%!important}</style>"
        f"</head><body>{svg}</body></html>"
    )
    return html.escape(page, quote=True)


def build_html(
    svg: str,
    name: str,
    times: list[float],
    *,
    duration: float,
    auto: bool,
    loops: bool,
    seam: bool,
    width: int,
    height: int,
    cols: int,
    themes: list[str],
) -> str:
    """The contact sheet page: one section per theme, one sandboxed iframe per moment."""
    cols = min(cols, len(times))
    sheet_w = sheet_size(len(times), cols, width, height, len(themes))[0]
    title = html.escape(name)
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{title} frames</title>",
        "<style>",
        "*{box-sizing:border-box}",
        f"html,body{{margin:0;background:{THEMES[themes[0]][0]}}}",
        "body{font:12px/20px ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace}",
        f"section{{width:{sheet_w}px;padding:{PAD}px}}",
        f"h1{{margin:0;height:{HEAD}px;font-size:12px;line-height:16px;font-weight:600;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
        f".grid{{display:grid;grid-template-columns:repeat({cols},{width}px);gap:{GAP}px}}",
        "figure{margin:0}",
        f"figcaption{{height:{CAP}px;line-height:{CAP}px;white-space:nowrap;overflow:hidden;"
        "text-overflow:ellipsis}",
        f"iframe{{display:block;border:0;width:{width}px;height:{height}px}}",
        "</style>",
        "</head>",
        "<body>",
    ]
    cycle = f"cycle {fmt(duration)}s ({'auto' if auto else 'set'})"
    for theme in themes:
        page, ink = THEMES[theme]
        doc = srcdoc(svg, page)
        lines.append(f'<section style="background:{page};color:{ink}">')
        lines.append(f"<h1>{title} | {theme} {page} | {cycle}{' | loops' if loops else ''}</h1>")
        lines.append('<div class="grid">')
        for i, t in enumerate(times):
            caption = f"t={fmt(t)}s"
            if duration > 0:
                caption += f" k={fmt(t / duration)}"
            if seam and i == len(times) - 1:
                caption += " | loops to t=0"
            lines.append(
                f"<figure><figcaption>{caption}</figcaption>"
                f'<iframe sandbox="allow-same-origin" style="color-scheme:{theme}" '
                f'data-t="{fmt(t)}" title="{title} at t={fmt(t)}s" srcdoc="{doc}"></iframe>'
                "</figure>"
            )
        lines.append("</div>")
        lines.append("</section>")
    lines += [SEEK, "</body>", "</html>", ""]
    return "\n".join(lines)


def install_paths() -> list[Path]:
    """Usual Chrome, Edge and Chromium locations on Windows, macOS and Linux."""
    out = []
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            out += [
                Path(base, "Google", "Chrome", "Application", "chrome.exe"),
                Path(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                Path(base, "Chromium", "Application", "chrome.exe"),
            ]
    for apps in (Path("/Applications"), Path.home() / "Applications"):
        out += [
            apps / "Google Chrome.app" / "Contents" / "MacOS" / "Google Chrome",
            apps / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            apps / "Microsoft Edge.app" / "Contents" / "MacOS" / "Microsoft Edge",
        ]
    out += [
        Path(p)
        for p in (
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/opt/google/chrome/chrome",
            "/usr/bin/microsoft-edge",
        )
    ]
    return out


def find_browser(override: str | None = None) -> str | None:
    """--browser (a path or command), else the first Chromium-family browser found."""
    if override:
        found = shutil.which(override)
        return found or (override if Path(override).is_file() else None)
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    return next((str(p) for p in install_paths() if p.is_file()), None)


def screenshot(browser: str, page: Path, png: Path, size: tuple[int, int]) -> str | None:
    """Screenshot page with a headless browser; None on success, else what went wrong."""
    png.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="svg-forge-", ignore_cleanup_errors=True) as profile:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            # headless inherits the OS animation setting; show motion as most viewers see it
            "--force-prefers-no-reduced-motion",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--virtual-time-budget={BUDGET_MS}",
            f"--window-size={size[0]},{size[1]}",
            f"--screenshot={png.resolve()}",
            page.resolve().as_uri(),
        ]
        if sys.platform.startswith("linux") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")  # Chromium refuses to start as root without it
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"{browser} failed: {exc}"
    if png.is_file() and png.stat().st_size > 0:
        return None
    detail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return f"{browser} wrote no PNG (exit {proc.returncode}): {' '.join(detail)}"


def parse_times(value: str) -> list[float] | None:
    times = [offset(t) for t in value.split(",") if t.strip()]
    if not times or any(t is None or t < 0 for t in times):
        return None
    return [round(t, 3) for t in times if t is not None]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="frames.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("file", type=Path, help="the animated SVG")
    ap.add_argument("--frames", type=int, default=6, help="moments spread over one cycle")
    ap.add_argument("--times", help="exact moments, e.g. 0,0.5,1.2 or 500ms; beats --frames")
    ap.add_argument("--duration", default="auto", help="cycle length: auto or seconds")
    ap.add_argument("--width", type=int, default=360, help="frame width in px")
    ap.add_argument("--cols", type=int, default=3, help="frames per row")
    ap.add_argument("--theme", choices=["dark", "light", "both"], default="dark")
    ap.add_argument("--out", type=Path, help="PNG path (default FILE.frames.png here)")
    ap.add_argument("--html-only", action="store_true", help="write the HTML sheet only")
    ap.add_argument("--browser", help="Chrome, Edge or Chromium executable to use")
    args = ap.parse_args(argv)
    if args.frames < 1:
        ap.error("--frames must be at least 1")
    if args.width < 16:
        ap.error("--width must be at least 16")
    if args.cols < 1:
        ap.error("--cols must be at least 1")
    times = parse_times(args.times) if args.times else None
    if args.times and times is None:
        ap.error("--times takes non-negative times like 0,0.5,1.2s or 500ms")
    browser = None
    if not args.html_only:
        browser = find_browser(args.browser)
        if args.browser and browser is None:
            ap.error(f"--browser {args.browser} not found")

    try:
        svg = args.file.read_bytes().decode("utf-8-sig")
        root = validate_svg.parse(svg)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"frames.py: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    except (validate_svg.DeclarationError, expat.ExpatError, IndexError) as exc:
        print(f"frames.py: {args.file} is not a well-formed SVG: {exc}", file=sys.stderr)
        return 1

    found, loops = timeline(root)
    auto = args.duration == "auto"
    duration = found if auto else validate_svg.seconds(args.duration)
    if duration is None or (not auto and duration <= 0):
        ap.error("--duration takes auto or a positive time like 4.8 or 4800ms")
    if times is None:
        times = frame_times(duration, loops, args.frames)
        if duration == 0:
            print(
                f"frames.py: no finite animation found in {args.file.name}; showing t=0 "
                "(pass --duration or --times)",
                file=sys.stderr,
            )
    seam = args.times is None and loops and len(times) > 1
    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    width = args.width
    height = max(1, round(width * aspect(root)))
    png = args.out or Path(f"{args.file.stem}.frames.png")
    page = png.with_suffix(".html")
    page.parent.mkdir(parents=True, exist_ok=True)
    sheet = build_html(
        svg,
        args.file.name,
        times,
        duration=duration,
        auto=auto,
        loops=loops,
        seam=seam,
        width=width,
        height=height,
        cols=args.cols,
        themes=themes,
    )
    page.write_text(sheet, encoding="utf-8", newline="\n")
    moments = ", ".join(fmt(t) for t in times)
    plural = "frame" if len(times) == 1 else "frames"
    summary = f"{len(times)} {plural} at {moments}s over a {fmt(duration)}s cycle"
    if args.html_only:
        print(f"wrote {page}: {summary}")
        return 0
    if browser is None:
        print(f"wrote {page}: {summary}")
        print(
            "frames.py: no Chrome, Edge or Chromium found, so no PNG; open the HTML sheet in a "
            "browser, pass --browser PATH, or use --html-only",
            file=sys.stderr,
        )
        return 3
    size = sheet_size(len(times), args.cols, width, height, len(themes))
    error = screenshot(browser, page, png, size)
    if error:
        print(f"wrote {page}: {summary}")
        print(f"frames.py: {error}", file=sys.stderr)
        return 1
    print(f"wrote {png} ({size[0]}x{size[1]}) and {page}: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
