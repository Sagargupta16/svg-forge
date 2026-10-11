"""validate_svg.py: each rule fires on a tiny fixture, clean files pass, CLI exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import validate_svg

NS = 'xmlns="http://www.w3.org/2000/svg"'
NAMED = 'role="img" aria-labelledby="t"'


def svg(body: str = "", root: str = f'{NS} viewBox="0 0 10 10" {NAMED}', title: bool = True) -> str:
    head = '<title id="t">Card</title>' if title else ""
    return f"<svg {root}>{head}{body}</svg>"


def rules(text: str, target: str = "standalone", **kw: object) -> dict[str, str]:
    report = validate_svg.validate_text(text.encode("utf-8"), target=target, **kw)
    return {f.rule: f.severity for f in report.findings}


def anim(attrs: str) -> str:
    """A rect animating x, with the given animate attributes."""
    return f'<rect width="1" height="1"><animate attributeName="x" {attrs}/></rect>'


def animated(n: int) -> str:
    return anim('values="0;1" dur="1s"') * n


DASH = chr(0x2014)
BIG_DATA = "data:image/png;base64," + "A" * (65 * 1024)

WHITE = '<rect width="10" height="10" fill="#ffffff"/>'
WARN = {"contrast": "warn"}  # the contrast rules run only when asked (the CLI default)

# rule -> (fixture, target, extra kwargs, expected severity)
CASES: dict[str, tuple[str, str, dict[str, object], str]] = {
    "SV001": ("<svg", "standalone", {}, "error"),
    "SV002": (
        f'<g {NS} viewBox="0 0 1 1" {NAMED}><title id="t">x</title></g>',
        "standalone",
        {},
        "error",
    ),
    "SV003": (svg(root=f"{NS} {NAMED}"), "standalone", {}, "error"),
    "SV004": (svg(root=f'viewBox="0 0 10 10" {NAMED}'), "standalone", {}, "error"),
    "SV005": (svg("<script>alert(1)</script>"), "standalone", {}, "error"),
    "SV006": (svg('<rect onclick="x()" width="1" height="1"/>'), "standalone", {}, "error"),
    "SV007": (svg("<foreignObject/>"), "standalone", {}, "error"),
    "SV008": (svg('<image href="https://example.com/a.png"/>'), "standalone", {}, "error"),
    "SV009": (svg("<style>@import url(a.css);</style>"), "standalone", {}, "error"),
    "SV010": (svg(root=f'{NS} viewBox="0 0 10 10"', title=False), "standalone", {}, "error"),
    "SV011": (
        svg(root=f'{NS} viewBox="0 0 10 10" role="img" aria-labelledby="t nope"'),
        "standalone",
        {},
        "error",
    ),
    "SV012": (svg('<g id="a"/><g id="a"/>'), "standalone", {}, "error"),
    "SV013": (svg("<!--" + "x" * 3000 + "-->"), "standalone", {"max_kb": 2}, "error"),
    "SV014": (svg(f"<text>a {DASH} b</text>"), "standalone", {}, "error"),
    "SV015": (svg(animated(41)), "standalone", {}, "warn"),
    "SV016": (
        svg(anim('values="0;1" dur="50ms" repeatCount="indefinite"')),
        "standalone",
        {},
        "warn",
    ),
    "SV017": (
        svg(anim('values="0;1;2" keyTimes="0;1" dur="1s"')),
        "standalone",
        {},
        "warn",
    ),
    "SV018": (
        svg(anim('values="0;1" keyTimes="0;1" keySplines="0 0 1 1" dur="1s"')),
        "standalone",
        {},
        "warn",
    ),
    "SV019": (
        svg('<path d="M0 0H9" pathLength="1" vector-effect="non-scaling-stroke"/>'),
        "standalone",
        {},
        "warn",
    ),
    "SV020": (svg(f'<image href="{BIG_DATA}"/>'), "standalone", {"max_kb": 500}, "warn"),
    "SV021": (
        svg(WHITE + '<text x="1" y="5" fill="#cccccc">Hi</text>'),
        "standalone",
        WARN,
        "warn",
    ),
    "SV022": (svg('<text x="1" y="5" fill="#0d1117">Hi</text>'), "standalone", WARN, "warn"),
    "SV023": (svg('<circle cx="5" cy="5" r="2" fill="#0d1117"/>'), "standalone", WARN, "warn"),
}


def test_every_rule_has_a_fixture() -> None:
    assert set(CASES) == set(validate_svg.RULES)


@pytest.mark.parametrize("rule", sorted(CASES))
def test_rule_fires(rule: str) -> None:
    text, target, kw, severity = CASES[rule]

    found = rules(text, target, **kw)

    assert found.get(rule) == severity, found


def test_clean_file_has_no_findings() -> None:
    text = svg(
        "<desc>d</desc>"
        '<defs><linearGradient id="g"><stop offset="0"/></linearGradient></defs>'
        '<rect width="5" height="5" fill="url(#g)">'
        '<animate attributeName="opacity" values="0;1;1" keyTimes="0;0.5;1" '
        'calcMode="spline" keySplines="0 0 1 1;0 0 1 1" dur="2s" repeatCount="indefinite"/></rect>'
        '<image href="data:image/png;base64,AAAA" width="1" height="1"/>'
    )

    report = validate_svg.validate_text(text.encode())

    assert report.findings == []
    assert report.stats["smil"] == 1
    assert report.stats["infinite"] == 1
    assert report.stats["longest_s"] == 2


def test_aria_label_and_aria_hidden_satisfy_accessibility() -> None:
    labelled = svg(root=f'{NS} viewBox="0 0 1 1" role="img" aria-label="Chart"', title=False)
    hidden = svg(root=f'{NS} viewBox="0 0 1 1" aria-hidden="true"', title=False)

    assert rules(labelled) == {}
    assert rules(hidden) == {}


def test_doctype_and_entities_are_refused() -> None:
    bomb = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]>' + svg("<text>&a;</text>")

    assert rules(bomb) == {"SV001": "error"}


@pytest.mark.parametrize(
    "ref",
    ["http://example.com/a.png", "//cdn.example.com/a.png", "file:///etc/passwd", "logo.png"],
)
def test_external_references_in_href_and_url(ref: str) -> None:
    assert rules(svg(f'<use href="{ref}"/>'))["SV008"] == "error"
    assert rules(svg(f'<rect width="1" height="1" fill="url({ref})"/>'))["SV008"] == "error"
    assert rules(svg(f"<style>.a{{fill:url('{ref}')}}</style>"))["SV008"] == "error"


def test_xlink_href_and_javascript_urls() -> None:
    xlink = 'xmlns:xlink="http://www.w3.org/1999/xlink"'
    text = svg(
        '<a xlink:href="javascript:alert(1)"><use xlink:href="https://e.x/s.svg#i"/></a>',
        root=f'{NS} {xlink} viewBox="0 0 1 1" {NAMED}',
    )

    found = rules(text)

    assert found["SV006"] == "error"
    assert found["SV008"] == "error"


def test_remote_font_face_is_flagged() -> None:
    css = "<style>@font-face{font-family:x;src:url(https://fonts.example/x.woff2)}</style>"

    assert rules(svg(css))["SV009"] == "error"


def test_web_target_relaxes_remote_refs_and_foreign_object() -> None:
    body = '<image href="https://example.com/a.png"/><foreignObject/>'
    root = f'viewBox="0 0 10 10" {NAMED}'

    found = rules(svg(body, root=root), target="web")

    assert found == {"SV008": "warn", "SV007": "warn", "SV004": "warn"}
    assert rules(svg('<image href="file:///a.png"/>'), target="web")["SV008"] == "error"


def test_size_warns_above_half_the_budget() -> None:
    text = svg("<!--" + "x" * 1400 + "-->")

    assert rules(text, max_kb=2)["SV013"] == "warn"


def test_keytimes_must_run_from_zero_to_one() -> None:
    bad = svg(anim('values="0;1" keyTimes="0.2;1" dur="1s"'))
    discrete = svg(anim('values="0;1" keyTimes="0;0.5" calcMode="discrete" dur="1s"'))

    assert rules(bad)["SV017"] == "warn"
    assert "SV017" not in rules(discrete)


def test_keypoints_count_must_match_keytimes() -> None:
    text = svg(
        '<circle r="1"><animateMotion path="M0 0H9" keyPoints="0;1" keyTimes="0;0.5;1" '
        'calcMode="linear" dur="1s"/></circle>'
    )

    assert rules(text)["SV017"] == "warn"


def test_css_animation_inventory() -> None:
    css = (
        "<style>.spin{animation:spin 1.2s linear infinite}"
        "@keyframes spin{to{transform:rotate(360deg)}}</style>"
        '<rect class="spin" width="1" height="1"/><rect class="spin" width="1" height="1"/>'
    )

    report = validate_svg.validate_text(svg(css).encode())

    assert report.stats["keyframes"] == 1
    assert report.stats["animated_elements"] == 2
    assert report.stats["infinite"] == 1
    assert report.stats["longest_s"] == 1.2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4.8s", 4.8),
        ("120ms", 0.12),
        ("1min", 60.0),
        ("00:01:02.5", 62.5),
        ("02:30", 150.0),
        ("3", 3.0),
    ],
)
def test_clock_values(value: str, expected: float) -> None:
    assert validate_svg.seconds(value) == pytest.approx(expected)


def test_cli_exit_codes_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = tmp_path / "good.svg"
    warn = tmp_path / "warn.svg"
    bad = tmp_path / "bad.svg"
    good.write_text(svg(), encoding="utf-8")
    warn.write_text(svg(animated(41)), encoding="utf-8")
    bad.write_text(svg("<script/>"), encoding="utf-8")

    assert validate_svg.main([str(good), str(warn)]) == 0
    capsys.readouterr()
    assert validate_svg.main([str(tmp_path), "--json"]) == 1

    results = {Path(r["file"]).name: r for r in json.loads(capsys.readouterr().out)}
    assert results["bad.svg"]["ok"] is False
    assert results["bad.svg"]["findings"][0]["rule"] == "SV005"
    assert results["warn.svg"]["ok"] is True and results["warn.svg"]["warnings"] == 1
    assert set(results["good.svg"]) == {
        "file",
        "target",
        "ok",
        "errors",
        "warnings",
        "findings",
        "stats",
    }


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    assert validate_svg.main([str(tmp_path / "nope.svg")]) == 1
