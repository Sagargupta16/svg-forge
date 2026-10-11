"""Shipped SVGs: every template and example validates, and its recorded command rebuilds it."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from xml.dom import minidom

import pytest

import check
import forge
import poster
import preview
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "skills" / "animated-svg" / "assets" / "templates"
EXAMPLES = ROOT / "examples"
DOCS = ROOT / "docs"
SHIPPED = (
    sorted(TEMPLATES.glob("*.svg")) + sorted(EXAMPLES.glob("*.svg")) + sorted(DOCS.glob("*.svg"))
)
EXTRA_TEMPLATES = {"hero-light", "flow-short", "flow-long", "marquee-ambient"}


def test_one_template_per_kind_plus_timing_variants() -> None:
    names = {p.stem for p in TEMPLATES.glob("*.svg")}

    assert names == set(forge.KINDS) | EXTRA_TEMPLATES


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_shipped_svg_is_valid_and_poster_safe(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    report = validate_svg.validate_file(path, contrast="error", theme=check.svg_theme(path))

    assert report.errors == 0, report.findings
    minidom.parseString(text)
    assert poster.problems(text) == []
    assert path.read_bytes().endswith(b"</svg>\n") and b"\r" not in path.read_bytes()


@pytest.mark.parametrize("recipe", preview.RECIPES, ids=lambda r: r.out)
def test_recipe_reproduces_committed_bytes(
    recipe: preview.Recipe, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    out = tmp_path / Path(recipe.out).name
    argv = [*recipe.args, "--out", str(out)]

    with contextlib.redirect_stdout(io.StringIO()):
        assert forge.main(argv) == 0

    for committed in recipe.files():
        built = tmp_path / Path(committed).name
        assert built.read_bytes() == (ROOT / committed).read_bytes(), (
            f"{committed} is stale; run python scripts/preview.py --rebuild"
        )


def test_every_shipped_svg_has_a_recipe() -> None:
    recorded = {f for r in preview.RECIPES for f in r.files()}

    assert {p.relative_to(ROOT).as_posix() for p in SHIPPED} == recorded


def test_examples_readme_is_current() -> None:
    assert (EXAMPLES / "README.md").read_text(encoding="utf-8") == preview.readme_text()


def test_examples_stay_under_600_kb() -> None:
    total = sum(p.stat().st_size for p in EXAMPLES.rglob("*") if p.is_file())

    assert total < 600 * 1024


def test_gallery_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview, "OUT", tmp_path)

    index = preview.gallery()

    html = index.read_text(encoding="utf-8")
    assert html.count("<figure>") == len(SHIPPED)
    assert "http" not in html.replace("http-equiv", "")


def test_contact_sheets_are_skipped_without_a_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview.frames, "find_browser", lambda override=None: None)

    assert preview.contact_sheets() == ([], "no Chrome, Edge or Chromium found")


def test_contact_sheets_render_each_example_on_its_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(preview, "OUT", tmp_path)
    monkeypatch.setattr(preview.frames, "find_browser", lambda override=None: "chrome")
    monkeypatch.setattr(preview.frames, "main", lambda argv: calls.append(argv) or 0)

    sheets, skipped = preview.contact_sheets()

    examples = sorted(EXAMPLES.glob("*.svg"))
    assert skipped == "" and len(sheets) == len(calls) == len(examples)
    themes = {Path(argv[0]).stem: argv[argv.index("--theme") + 1] for argv in calls}
    assert themes["badge-status-light"] == "light" and themes["badge-status-dark"] == "dark"
    assert themes["badge-once"] == "both"
    assert all(Path(argv[2]).parent == tmp_path / "frames" for argv in calls)
