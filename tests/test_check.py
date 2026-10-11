"""scripts/check.py: each repo rule fires on a throwaway tree."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import check


def tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


GOOD_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" role="img" aria-label="x"></svg>'
)
MANIFESTS = {
    ".claude-plugin/plugin.json": json.dumps({"name": "p", "version": "0.1.0"}),
    ".claude-plugin/marketplace.json": json.dumps({"plugins": [{"name": "p", "version": "0.1.0"}]}),
}
SKILL = "---\nname: demo\ndescription: >-\n  Does a thing. Use when the user asks.\n---\n\nBody.\n"


def run(root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> str:
    monkeypatch.setattr(check, "ROOT", root)
    code = check.main()
    out = capsys.readouterr().out
    assert (code == 0) == out.endswith(" 0 problems\n")
    return out


def test_clean_tree_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree(
        tmp_path,
        {
            **MANIFESTS,
            "skills/demo/SKILL.md": SKILL,
            "examples/a.svg": GOOD_SVG,
            "README.md": '[a](examples/a.svg)\n\n```html\n<img src="missing.svg">\n```\n',
        },
    )

    assert run(tmp_path, monkeypatch, capsys).endswith(" 0 problems\n")


def test_each_rule_fires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    home = "C:" + "/Users/someone/x"
    tree(
        tmp_path,
        {
            ".claude-plugin/plugin.json": json.dumps({"name": "p", "version": "0.2.0"}),
            ".claude-plugin/marketplace.json": json.dumps(
                {"plugins": [{"name": "p", "version": "0.1.0"}]}
            ),
            "notes.md": f'a {chr(0x2013)} b\n[x](nope.md)\n<img src="gone.svg">\n{home}\n',
            "key.txt": "AKIA" + "A" * 16 + "\n",
            "bad.json": "{",
            "skills/demo/SKILL.md": "---\nname: other\ndescription: does: things\n---\n",
            "examples/bad.svg": "<svg><script/></svg>",
        },
    )

    out = run(tmp_path, monkeypatch, capsys)

    for rule in ("SF001", "SF002", "SF003", "SF004", "SF005", "SF006", "SF007", "SF008"):
        assert rule in out, rule
    assert out.count("SF005") == 2


LOW = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20" role="img" aria-label="x">'
    '<text x="2" y="12" fill="#0d1117">Hi</text></svg>'
)


def test_shipped_svg_contrast_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree(tmp_path, {**MANIFESTS, "examples/low.svg": LOW, "examples/low-light.svg": LOW})

    out = run(tmp_path, monkeypatch, capsys)

    assert "examples/low.svg:1 SF008 SV022" in out  # dark text fails on GitHub dark
    assert "low-light.svg" not in out  # one half of a pair: checked on GitHub light only


def test_data_svgs_skip_the_contrast_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree(tmp_path, {**MANIFESTS, "examples/data/logo.svg": LOW})

    assert run(tmp_path, monkeypatch, capsys).endswith(" 0 problems\n")


def test_eval_results_are_not_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree(tmp_path, {**MANIFESTS, "evals/results/run.json": '{"cwd": "C:' + '/Users/a/b"}'})

    assert run(tmp_path, monkeypatch, capsys).endswith(" 0 problems\n")
