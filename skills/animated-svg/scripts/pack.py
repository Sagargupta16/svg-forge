#!/usr/bin/env python3
"""Render a README's matching set of animated SVG cards from one pack file (stdlib only).

  python pack.py PACK.json                 write every card and snippet.md into the out dir
  python pack.py PACK.json --out-dir DIR   write them into DIR instead
  python pack.py PACK.json --check         render in memory; exit 1 if a file differs or is missing

A pack describes the set once, in JSON:

  {
    "theme": "both",
    "accent": "#38bdf8",
    "device": "both",
    "out_dir": "assets/cards",
    "cards": [
      {"name": "hero", "kind": "hero", "alt": "Northwind Labs: developer tools for cloud teams",
       "data": {"title": "Northwind Labs", "taglines": ["Developer tools for cloud teams"]}},
      {"name": "license", "kind": "badge", "row": "badges", "alt": "License: MIT",
       "link": "LICENSE", "data": {"label": "license", "value": "MIT"}}
    ]
  }

Pack keys: out_dir (default assets/cards), cards, and the defaults every card inherits:
theme, mode, accent, device, font_stack, reduced_motion. Card keys: name (the file stem),
kind, alt (required; "" marks a decorative card), data (inline JSON) or data_file (a JSON
file, or a .txt text spec for flow), link, row, and any forge.py option under its flag name
with underscores: theme, mode, accent, device, size, timing, variant, width, height, title,
desc, loop, speed, reduced_motion, font_stack, id_prefix.

Every card renders through forge.build() exactly as forge.main() would for the same flags,
so `forge.py --kind hero --theme both ... --out DIR/hero.svg` writes the same bytes. Paths
in the pack (out_dir, data_file, and file paths inside data or a palette theme) resolve
from the pack file's folder; --out-dir resolves from the current folder. The pack's device
applies to kinds that have a phone layout and set no size; the others get one desktop file,
which serves every screen. A device set on the card itself is used as written.

snippet.md holds the README markup for every card in pack order, from forge.picture_set():
image paths that start with the out dir exactly as given (as forge.py prints the paths
passed to --out, so keep the pack next to the README and out_dir relative), the pack's alt
text, an <a> around the <picture> when the card has a link, and the cards that share a row
in one <p align="center">, each image sized by width alone (its desktop file's width).

Exit codes: 0 done, 1 --check found a stale or missing file, 2 a bad pack (every problem
is reported, each naming the card and the field, and nothing is written).
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import html
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import forge
import sizes
import themes

DEFAULT_OUT = "assets/cards"
SHARED = ("theme", "mode", "accent", "device", "font_stack", "reduced_motion")
OWN = ("size", "timing", "variant", "width", "height", "title", "desc", "loop", "speed")
OPTIONS = (*SHARED, *OWN, "id_prefix")
PACK_KEYS = ("out_dir", "cards", *SHARED)
CARD_KEYS = ("name", "kind", "alt", "data", "data_file", "link", "row", *OPTIONS)
NUMBERS = frozenset({"width", "height", "speed"})
KEYWORD = {"font_stack": "font"}  # the forge.build() keyword where it differs from the flag
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SUFFIXES = ("-dark", "-light", "-mobile")  # forge.file_name() adds these
SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")
LINK_SCHEMES = frozenset({"http", "https", "mailto"})
SVG_WIDTH = re.compile(r'<svg\b[^>]*?\swidth="([0-9.]+)"')
IMG = re.compile(r'<img ([^>]*?)(?: width="[^"]*")?>')


class PackError(Exception):
    """A bad pack: one line per problem."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


class Problem(Exception):
    """One bad field of a card or of the pack: 'field: what is wrong'."""


@dataclass(frozen=True)
class Card:
    name: str
    alt: str
    link: str | None
    row: str | None
    files: dict[tuple[str | None, str], str]  # (theme suffix, device) -> SVG, in plan order

    @property
    def width(self) -> str:
        """The desktop file's width in px (the phone file's when there is no desktop one)."""
        svgs = [svg for (_, device), svg in self.files.items() if device == "desktop"]
        found = SVG_WIDTH.search((svgs or list(self.files.values()))[0])
        return str(max(1, round(float(found.group(1)))))


def unknown(key: str, allowed: tuple[str, ...]) -> str:
    near = difflib.get_close_matches(key, allowed, n=1)
    return f"{key}: unknown key" + (f", did you mean {near[0]!r}?" if near else "")


def option(key: str, value: object) -> object:
    """A forge option from the pack, as forge.main() would get it from its flag."""
    if key == "loop":
        if not isinstance(value, bool):
            raise Problem("loop: must be true (loop forever) or false (play once and hold)")
        return value
    if key == "size" and isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if key in NUMBERS:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise Problem(f"{key}: must be a number, got {json.dumps(value)}")
        if not math.isfinite(value):
            raise Problem(f"{key}: must be a finite number")
        return float(value)
    if not isinstance(value, str):
        raise Problem(f"{key}: must be text, got {json.dumps(value)}")
    if key == "device" and value not in (*forge.DEVICES, "both"):
        raise Problem(f"device: must be desktop, phone or both, got {value!r}")
    return value


def data_from(value: object, base: Path, kind: str) -> Any:
    """data_file read the way forge.py reads --data PATH."""
    if not isinstance(value, str) or not value.strip():
        raise Problem("data_file: must be a path to a JSON file (or a .txt text spec for flow)")
    path = base / value
    if not path.is_file():
        raise Problem(f"data_file: no such file {value} next to the pack")
    try:
        return forge.load_data(str(path), text_spec=kind == "flow")
    except forge.ForgeError as exc:
        raise Problem(f"data_file: {exc}") from exc


def render_card(
    raw: dict[str, Any], shared: dict[str, object], base: Path
) -> tuple[Card, list[str]]:
    """One card's files through forge.build(), and forge's notes on adjusted colors."""
    for key in raw:
        if key not in CARD_KEYS:
            raise Problem(unknown(key, CARD_KEYS))
    name = raw.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise Problem("name: required, lowercase letters, digits and hyphens, like stats-2")
    if name.endswith(SUFFIXES):
        raise Problem("name: must not end in -dark, -light or -mobile; pack.py adds those")
    kind = raw.get("kind")
    if kind not in forge.KINDS:
        near = difflib.get_close_matches(str(kind), list(forge.KINDS), n=1)
        hint = f" (did you mean {near[0]!r}?)" if near else ""
        raise Problem(f"kind: unknown kind {kind!r}{hint}; choose from {', '.join(forge.KINDS)}")
    if "alt" not in raw:
        raise Problem('alt: required, what the card shows for a screen reader ("" if decorative)')
    if not isinstance(raw["alt"], str):
        raise Problem("alt: must be text")
    link = raw.get("link")
    if link is not None:
        if not isinstance(link, str) or not link.strip():
            raise Problem("link: must be a URL or a relative path")
        scheme = SCHEME.match(link)
        if scheme and scheme.group(1).lower() not in LINK_SCHEMES:
            raise Problem("link: must be an http, https or mailto URL, or a relative path")
    row = raw.get("row")
    if row is not None and (not isinstance(row, str) or not row.strip()):
        raise Problem("row: must be text naming the row, like badges")
    if "data" in raw and "data_file" in raw:
        raise Problem("data_file: give data or data_file, not both")
    data = data_from(raw["data_file"], base, kind) if "data_file" in raw else raw.get("data")
    opts = dict(shared)
    opts.update({key: option(key, raw[key]) for key in OPTIONS if key in raw})
    device = opts.pop("device", "desktop")
    if "device" not in raw and (not forge.KINDS[kind].phone or "size" in opts):
        device = "desktop"
    plan = forge.plan(opts.pop("theme", None), opts.pop("mode", None))
    devices = list(forge.DEVICES) if device == "both" else [device]
    kwargs = {KEYWORD.get(key, key): value for key, value in opts.items()}
    files: dict[tuple[str | None, str], str] = {}
    notes: list[str] = []
    for (suffix, spec, mode), dev in itertools.product(plan, devices):
        files[(suffix, dev)], got = forge.build(
            kind, theme=spec, mode=mode, pair=len(plan) == 2, device=dev, data=data, **kwargs
        )
        notes += got
    alt = forge.clean(raw["alt"]).strip()
    return Card(name, alt, link, row.strip() if row else None, files), notes


def one_line(markup: str) -> str:
    """picture_set() markup on one line: no whitespace inside an <a> or between row images."""
    return "".join(line.strip() for line in markup.splitlines())


def linked(markup: str, link: str | None) -> str:
    return markup if link is None else f'<a href="{html.escape(link)}">{one_line(markup)}</a>'


def snippet(cards: list[Card], src_dir: str, label: str) -> str:
    """README markup for every card, in pack order, as one fenced block."""
    blocks: list[tuple[str | None, list[str]]] = []
    for card in cards:
        paths = {
            key: f"{src_dir}/{forge.file_name(Path(card.name), *key).name}" for key in card.files
        }
        markup = forge.picture_set(paths, card.alt)
        if card.row is None:
            blocks.append((None, [linked(markup, card.link)]))
            continue
        sized = IMG.sub(rf'<img \1 width="{card.width}">', markup, count=1)  # width only
        item = linked(one_line(sized), card.link)
        row = next((items for key, items in blocks if key == card.row), None)
        if row is None:
            blocks.append((card.row, [item]))
        else:
            row.append(item)
    body = "\n\n".join(
        items[0] if key is None else '<p align="center">\n' + "\n".join(items) + "\n</p>"
        for key, items in blocks
    )
    return (
        "# svg-forge snippet\n\n"
        f"Markup for every card in {label}, in pack order. Copy what you need into your README; "
        f"image paths start with the out dir exactly as given ({src_dir}).\n\n"
        f"```html\n{body}\n```\n"
    )


def render_pack(path: Path, out_dir: str | None = None) -> tuple[dict[Path, str], list[str]]:
    """Every file the pack writes (SVGs in pack order, then snippet.md) and forge's notes.

    out_dir (the --out-dir flag) resolves from the current folder and replaces the pack's
    out_dir, which resolves from the pack's folder. Raises PackError with every problem.
    """
    label = path.name
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PackError([f"{label}: cannot read the pack ({exc.strerror or exc})"]) from exc
    except json.JSONDecodeError as exc:
        raise PackError([f"{label}: line {exc.lineno}: not valid JSON ({exc.msg})"]) from exc
    if not isinstance(pack, dict):
        raise PackError([f"{label}: must be a JSON object with a cards list"])
    problems = [f"{label}: {unknown(key, PACK_KEYS)}" for key in pack if key not in PACK_KEYS]
    shared: dict[str, object] = {}
    for key in SHARED:
        try:
            if key in pack:
                shared[key] = option(key, pack[key])
        except Problem as exc:
            problems.append(f"{label}: {exc}")
    base = path.resolve().parent
    out = pack.get("out_dir", DEFAULT_OUT) if out_dir is None else out_dir
    if not isinstance(out, str) or not out.strip():
        problems.append(f"{label}: out_dir: must be a folder path")
        out = DEFAULT_OUT
    target = Path(out) if out_dir is not None else path.parent / out
    raws = pack.get("cards")
    if not isinstance(raws, list) or not raws:
        problems.append(f"{label}: cards: required, a list of at least one card")
        raws = []
    cards: list[Card] = []
    notes: list[str] = []
    with contextlib.chdir(base):  # forge reads logo files and palettes from the current folder
        for i, raw in enumerate(raws):
            name = raw.get("name") if isinstance(raw, dict) else None
            where = f"{label}: cards[{i}]" + (f" ({name})" if isinstance(name, str) else "")
            if not isinstance(raw, dict):
                problems.append(f"{where}: must be an object with name, kind and alt")
                continue
            if any(card.name == name for card in cards):
                problems.append(f"{where}: name: {name!r} is already used by an earlier card")
                continue
            try:
                card, got = render_card(raw, shared, base)
            except (Problem, forge.ForgeError, themes.ThemeError, sizes.SizeError) as exc:
                problems.append(f"{where}: {exc}")
                continue
            cards.append(card)
            notes += [f"{card.name}: {note}" for note in got]
    if problems:
        raise PackError(problems)
    files = {
        forge.file_name(target / card.name, *key): svg
        for card in cards
        for key, svg in card.files.items()
    }
    files[target / "snippet.md"] = snippet(cards, Path(out).as_posix(), label)
    return files, notes


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pack.py",
        description="Render a README's set of animated SVG cards and snippet.md from a pack.",
        epilog="The pack format is in this script's docstring; starter packs are in assets/packs/.",
    )
    ap.add_argument("pack", help="the pack .json")
    ap.add_argument("--out-dir", help="write here instead of the pack's out_dir")
    ap.add_argument(
        "--check",
        action="store_true",
        help="render in memory and exit 1 when a file on disk differs or is missing",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        files, notes = render_pack(Path(args.pack), args.out_dir)
    except PackError as exc:
        for problem in exc.problems:
            print(f"pack.py: error: {problem}", file=sys.stderr)
        return 2
    for note in dict.fromkeys(notes):
        print(f"pack.py: note: {note}", file=sys.stderr)
    if args.check:
        stale = [
            p for p, text in files.items() if not p.is_file() or p.read_bytes() != text.encode()
        ]
        for p in stale:
            print(f"{'differs' if p.is_file() else 'missing'} {p.as_posix()}")
        print(f"{len(files) - len(stale)} of {len(files)} files match")
        return 1 if stale else 0
    for p, text in files.items():
        changed = forge.write(p, text)
        print(f"{'wrote' if changed else 'unchanged'} {p.as_posix()} ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
