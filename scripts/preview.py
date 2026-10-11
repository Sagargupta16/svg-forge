#!/usr/bin/env python3
"""Build a local gallery of every shipped SVG, and optionally regenerate them first.

  python scripts/preview.py             write preview/index.html (gitignored)
  python scripts/preview.py --rebuild   regenerate templates, examples and
                                        examples/README.md from RECIPES, then the gallery
  python scripts/preview.py --open      also open the gallery in the default browser
  python scripts/preview.py --frames    also write a frames.py contact sheet per example into
                                        preview/frames/ (skipped when no browser is found)

Each SVG is shown on GitHub's dark (#0d1117) and light (#ffffff) page colors with its size
and validator result. Commands run from the repository root.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import io
import os
import shlex
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "animated-svg" / "scripts"
TEMPLATES = ROOT / "skills" / "animated-svg" / "assets" / "templates"
EXAMPLES = ROOT / "examples"
DOCS = ROOT / "docs"
OUT = ROOT / "preview"
sys.path.insert(0, str(SCRIPTS))

import forge  # noqa: E402
import frames  # noqa: E402
import validate_svg  # noqa: E402

FORGE = "python skills/animated-svg/scripts/forge.py"


@dataclass(frozen=True)
class Recipe:
    """One shipped file: where it goes and the forge.py arguments that produce it."""

    out: str  # path from the repo root; with --theme both, -dark/-light files appear
    args: tuple[str, ...]
    note: str = ""

    @property
    def kind(self) -> str:
        return self.args[self.args.index("--kind") + 1]

    @property
    def preset(self) -> str:
        if "--timing" in self.args:
            return self.args[self.args.index("--timing") + 1]
        return forge.KINDS[self.kind].timing

    @property
    def both(self) -> bool:
        return "both" in self.args

    def files(self) -> list[str]:
        if not self.both:
            return [self.out]
        stem = self.out.removesuffix(".svg")
        return [f"{stem}-dark.svg", f"{stem}-light.svg"]

    def argv(self) -> list[str]:
        return [*self.args, "--out", self.out]

    def command(self) -> str:
        return f"{FORGE} {shlex.join(self.argv())}"


T = "skills/animated-svg/assets/templates"
E = "examples"
RECIPES: list[Recipe] = [
    *(Recipe(f"{T}/{kind}.svg", ("--kind", kind)) for kind in forge.KINDS),
    Recipe(f"{T}/hero-light.svg", ("--kind", "hero", "--theme", "light")),
    Recipe(f"{T}/flow-short.svg", ("--kind", "flow", "--timing", "short")),
    Recipe(f"{T}/flow-long.svg", ("--kind", "flow", "--timing", "long")),
    Recipe(
        f"{T}/marquee-ambient.svg",
        (
            "--kind",
            "marquee",
            "--timing",
            "ambient",
            "--speed",
            "24",
            "--data",
            f"{E}/data/stack.json",
        ),
    ),
    Recipe(
        "docs/hero.svg",
        ("--kind", "hero", "--theme", "both", "--accent", "#38bdf8", "--data", "docs/hero.json"),
        "the README header",
    ),
    Recipe(
        f"{E}/hero-violet.svg",
        (
            "--kind",
            "hero",
            "--theme",
            "both",
            "--accent",
            "#a78bfa",
            "--data",
            f"{E}/data/hero.json",
        ),
        "both themes, custom accent",
    ),
    Recipe(
        f"{E}/tiles-once.svg",
        (
            "--kind",
            "tiles",
            "--timing",
            "short",
            "--accent",
            "#22c55e",
            "--data",
            f"{E}/data/tiles.json",
        ),
        "staggered entrance that holds",
    ),
    Recipe(
        f"{E}/tiles-spotlight.svg",
        ("--kind", "tiles", "--timing", "medium", "--data", f"{E}/data/tiles.json"),
        "spotlight cycling the tiles",
    ),
    Recipe(
        f"{E}/flow-storyboard.svg",
        (
            "--kind",
            "flow",
            "--timing",
            "long",
            "--accent",
            "#38bdf8",
            "--data",
            f"{E}/data/pipeline.json",
        ),
        "8-beat storyboard with a return arc",
    ),
    Recipe(
        f"{E}/flow-architecture.svg",
        ("--kind", "flow", "--accent", "#f472b6", "--data", f"{E}/data/architecture.json"),
        "fixed node positions, edge labels",
    ),
    Recipe(
        f"{E}/flow-once.svg",
        ("--kind", "flow", "--timing", "long", "--once", "--data", f"{E}/data/pipeline.json"),
        "storyboard played once, then held",
    ),
    Recipe(
        f"{E}/marquee-rows.svg",
        (
            "--kind",
            "marquee",
            "--speed",
            "30",
            "--accent",
            "#f59e0b",
            "--data",
            f"{E}/data/stack.json",
        ),
        "two rows in opposite directions at 30 px/s",
    ),
    Recipe(
        f"{E}/chart-loop.svg",
        (
            "--kind",
            "chart",
            "--timing",
            "medium",
            "--accent",
            "#34d399",
            "--data",
            f"{E}/data/weekly.json",
        ),
        "draws, holds, fades, repeats",
    ),
    Recipe(
        f"{E}/chart-light.svg",
        ("--kind", "chart", "--theme", "light", "--data", f"{E}/data/weekly.json"),
        "light theme, one-shot",
    ),
    Recipe(
        f"{E}/bars-loop.svg",
        ("--kind", "bars", "--timing", "long", "--data", f"{E}/data/checklist.json"),
        "value/max labels, long loop",
    ),
    Recipe(
        f"{E}/loader-dots.svg", ("--kind", "loader", "--variant", "dots", "--accent", "#22c55e")
    ),
    Recipe(f"{E}/loader-bar.svg", ("--kind", "loader", "--variant", "bar", "--timing", "short")),
    Recipe(
        f"{E}/loader-spinner-ambient.svg",
        ("--kind", "loader", "--timing", "ambient", "--accent", "#fb7185"),
        "slow drift from --speed",
    ),
    Recipe(
        f"{E}/typing-medium.svg",
        (
            "--kind",
            "typing",
            "--timing",
            "medium",
            "--reduced-motion",
            "respect",
            "--data",
            f"{E}/data/terminal.json",
        ),
        "opt-in reduced-motion block for the CSS cursor",
    ),
    Recipe(
        f"{E}/divider-ambient.svg",
        ("--kind", "divider", "--timing", "ambient", "--speed", "80"),
        "pulse crossing at 80 px/s",
    ),
    Recipe(
        f"{E}/badge-status.svg",
        ("--kind", "badge", "--theme", "both", "--data", f"{E}/data/status.json"),
        "both themes",
    ),
    Recipe(
        f"{E}/badge-once.svg",
        (
            "--kind",
            "badge",
            "--timing",
            "short",
            "--accent",
            "#fb7185",
            "--data",
            f"{E}/data/coverage.json",
        ),
        "one entrance and one shine",
    ),
    Recipe(
        f"{E}/timeline-career.svg",
        ("--kind", "timeline", "--data", f"{E}/data/career.json"),
        "rail draws in, the current role pulses",
    ),
    Recipe(
        f"{E}/timeline-vertical.svg",
        (
            "--kind",
            "timeline",
            "--variant",
            "vertical",
            "--timing",
            "short",
            "--theme",
            "light",
            "--accent",
            "#0ea5e9",
            "--data",
            f"{E}/data/career.json",
        ),
        "vertical rail, one-shot, light theme",
    ),
    Recipe(
        f"{E}/logos-wall.svg",
        ("--kind", "logos", "--data", f"{E}/data/logos.json"),
        "inline SVG symbols, a PNG and text pills",
    ),
    Recipe(
        f"{E}/logos-marquee.svg",
        (
            "--kind",
            "logos",
            "--timing",
            "ambient",
            "--speed",
            "24",
            "--data",
            f"{E}/data/logos.json",
        ),
        "slow marquee at 24 px/s",
    ),
    Recipe(
        f"{E}/calendar-green.svg",
        ("--kind", "calendar", "--data", f"{E}/data/contributions.json"),
        "quartile levels: one 140-count day does not flatten the rest",
    ),
    Recipe(
        f"{E}/calendar-accent.svg",
        (
            "--kind",
            "calendar",
            "--variant",
            "accent",
            "--accent",
            "#a78bfa",
            "--theme",
            "light",
            "--timing",
            "medium",
            "--data",
            f"{E}/data/activity.json",
        ),
        "accent ramp from start and counts, looping reveal",
    ),
    Recipe(
        f"{E}/ring-goals.svg",
        ("--kind", "ring", "--theme", "both", "--data", f"{E}/data/goals.json"),
        "both themes, value/max labels and tones",
    ),
    Recipe(
        f"{E}/ring-loop.svg",
        (
            "--kind",
            "ring",
            "--timing",
            "medium",
            "--accent",
            "#34d399",
            "--width",
            "480",
            "--height",
            "360",
            "--data",
            f"{E}/data/goals.json",
        ),
        "fixed 480x360 canvas wraps the rings into rows",
    ),
    Recipe(
        f"{E}/flow-text.svg",
        ("--kind", "flow", "--timing", "long", "--data", f"{E}/data/pipeline.txt"),
        "text spec file: parallel steps, edge labels, a return arc",
    ),
    Recipe(
        f"{E}/flow-text-inline.svg",
        ("--kind", "flow", "--data", "push -> build -> unit, e2e -> deploy"),
        "inline text spec",
    ),
]


def rebuild() -> list[str]:
    """Run every recipe from the repo root; return the files whose bytes changed."""
    changed = []
    cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        for recipe in RECIPES:
            before = {
                f: (ROOT / f).read_bytes() if (ROOT / f).is_file() else b"" for f in recipe.files()
            }
            with contextlib.redirect_stdout(io.StringIO()):
                code = forge.main(recipe.argv())
            if code:
                raise SystemExit(f"recipe failed ({code}): {recipe.command()}")
            changed += [f for f in recipe.files() if (ROOT / f).read_bytes() != before[f]]
    finally:
        os.chdir(cwd)
    write_readme()
    return changed


def readme_text() -> str:
    """examples/README.md: one table row per example recipe."""
    rows = []
    for recipe in RECIPES:
        if not recipe.out.startswith(f"{E}/"):
            continue
        alt = f"{recipe.kind} {recipe.preset}"
        imgs = " ".join(
            f'<img src="{html.escape(f.removeprefix(E + "/"))}" width="360" alt="{alt}">'
            for f in recipe.files()
        )
        preset = recipe.preset + (", once" if "--once" in recipe.args else "")
        note = f"<br>{recipe.note}" if recipe.note else ""
        rows.append(f"| {recipe.kind} | {preset}{note} | {imgs} | `{recipe.command()}` |")
    text = "\n".join(
        [
            "# Examples",
            "",
            "Every file here is generated. `python scripts/preview.py --rebuild` reruns the",
            "commands below from the repository root, and the tests check that each command",
            "still reproduces its file byte for byte. Input data lives in [data/](data/).",
            "",
            "Starter files for each kind (dark theme, default timing) are in",
            "[skills/animated-svg/assets/templates/](../skills/animated-svg/assets/templates/).",
            "",
            "| kind | preset | preview | command |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
            "Files made with `--theme both` come as a `-dark` and `-light` pair; forge.py prints",
            "the `<picture>` snippet that switches between them on GitHub:",
            "",
            "```html",
            forge.picture(
                "examples/hero-violet-dark.svg", "examples/hero-violet-light.svg", "Northwind Labs"
            ),
            "```",
            "",
        ]
    )
    return text


def write_readme() -> None:
    (EXAMPLES / "README.md").write_bytes(readme_text().encode("utf-8"))


def gallery() -> Path:
    files = (
        sorted(TEMPLATES.glob("*.svg"))
        + sorted(EXAMPLES.glob("*.svg"))
        + sorted(DOCS.glob("*.svg"))
    )
    cards = []
    for path in files:
        report = validate_svg.validate_file(path)
        rel = path.relative_to(ROOT).as_posix()
        status = "ok" if report.errors == 0 else f"{report.errors} errors"
        if report.warnings:
            status += f", {report.warnings} warnings"
        src = html.escape(os.path.relpath(path, OUT).replace(os.sep, "/"))
        cards.append(
            f'<figure><div class="pair"><div class="dark"><img src="{src}" alt=""></div>'
            f'<div class="light"><img src="{src}" alt=""></div></div>'
            f"<figcaption><b>{html.escape(rel)}</b> {path.stat().st_size / 1024:.1f} KB, "
            f'<span class="{"ok" if report.errors == 0 else "bad"}">{html.escape(status)}</span>'
            "</figcaption></figure>"
        )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>svg-forge gallery</title>
<style>
body{{margin:0;padding:16px;background:#161b22;color:#e6edf3;font:14px system-ui,sans-serif}}
h1{{font-size:18px;margin:4px 0 16px}}
main{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(min(100%,460px),1fr))}}
figure{{margin:0;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
.pair>div{{padding:14px;display:flex;justify-content:center}}
.dark{{background:#0d1117}}.light{{background:#ffffff}}
img{{max-width:100%;height:auto}}
figcaption{{padding:8px 12px;font-size:12px;border-top:1px solid #30363d}}
.ok{{color:#3fb950}}.bad{{color:#f85149}}
</style></head><body>
<h1>svg-forge gallery: {len(files)} files, each on GitHub dark and light</h1>
<main>
{chr(10).join(cards)}
</main></body></html>
"""
    OUT.mkdir(exist_ok=True)
    index = OUT / "index.html"
    index.write_bytes(page.encode("utf-8"))
    return index


def contact_sheets() -> tuple[list[Path], str]:
    """A frames.py contact sheet per example in preview/frames/: a -dark or -light file on its
    own page, any other on both. Returns the PNGs written, or no PNGs and why."""
    browser = frames.find_browser()
    if browser is None:
        return [], "no Chrome, Edge or Chromium found"
    written = []
    for path in sorted(EXAMPLES.glob("*.svg")):
        png = OUT / "frames" / f"{path.stem}.png"
        theme = next((t for t in ("dark", "light") if path.stem.endswith(f"-{t}")), "both")
        argv = [str(path), "--out", str(png), "--theme", theme, "--browser", browser]
        with contextlib.redirect_stdout(io.StringIO()):
            code = frames.main(argv)
        if code:
            raise SystemExit(f"frames.py failed ({code}) on {path.relative_to(ROOT).as_posix()}")
        written.append(png)
    return written, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="preview.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--rebuild", action="store_true", help="regenerate templates and examples")
    ap.add_argument("--open", action="store_true", help="open the gallery in a browser")
    ap.add_argument(
        "--frames", action="store_true", help="write a contact sheet per example (needs Chrome)"
    )
    args = ap.parse_args(argv)
    if args.rebuild:
        changed = rebuild()
        print(f"rebuilt {sum(len(r.files()) for r in RECIPES)} files, {len(changed)} changed")
        for f in changed:
            print(f"  {f}")
    index = gallery()
    print(f"gallery: {index.relative_to(ROOT).as_posix()}")
    if args.frames:
        sheets, skipped = contact_sheets()
        if skipped:
            print(f"contact sheets skipped: {skipped}")
        else:
            print(
                f"contact sheets: {len(sheets)} in {(OUT / 'frames').relative_to(ROOT).as_posix()}"
            )
    if args.open:
        webbrowser.open(index.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
