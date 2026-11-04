"""pack.py: one pack renders a README's cards through forge and writes snippet.md."""

from __future__ import annotations

import dataclasses
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import check
import forge
import pack
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "skills" / "animated-svg" / "assets" / "packs"
STARTERS = sorted(PACKS.glob("*.json"))
HTML_BLOCK = re.compile(r"```html\n(.*)\n```\n\Z", re.S)


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = pack.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def write_pack(folder: Path, body: dict[str, Any]) -> Path:
    path = folder / "pack.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def devices_of(body: dict[str, Any], card: dict[str, Any]) -> list[str]:
    """The pack's device reaches kinds with a phone layout and no size; the card's own wins."""
    device = card.get("device")
    if device is None:
        phone = forge.KINDS[card["kind"]].phone and "size" not in card
        device = body.get("device", "desktop") if phone else "desktop"
    return ["desktop", "phone"] if device == "both" else [device]


def expected_files(body: dict[str, Any]) -> dict[str, list[str]]:
    """Card name -> the file names it should write, from the pack and forge's registry."""
    out = {}
    for card in body["cards"]:
        theme, mode = card.get("theme", body.get("theme")), card.get("mode", body.get("mode"))
        halves = ["dark", "light"] if "both" in (theme, mode) else [None]
        out[card["name"]] = [
            forge.file_name(Path(card["name"]), half, device).name
            for half in halves
            for device in devices_of(body, card)
        ]
    return out


def svg_width(path: Path) -> str:
    found = re.search(r'<svg [^>]*?width="([\d.]+)"', path.read_text(encoding="utf-8"))
    assert found
    return str(round(float(found.group(1))))


@pytest.mark.parametrize("starter", STARTERS, ids=lambda p: p.stem)
def test_starter_pack_renders_files_that_validate(
    starter: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run([str(starter), "--out-dir", str(tmp_path)], capsys)

    assert code == 0, err
    body = json.loads(starter.read_text(encoding="utf-8"))
    names = {name for files in expected_files(body).values() for name in files}
    assert {p.name for p in tmp_path.iterdir()} == names | {"snippet.md"}
    for svg in sorted(tmp_path.glob("*.svg")):
        report = validate_svg.validate_file(svg, contrast="error", theme=check.svg_theme(svg))
        assert report.findings == [], (svg.name, report.findings)
        data = svg.read_bytes()
        assert b"\r" not in data and data.endswith(b"</svg>\n")


def test_starter_packs_cover_a_profile_and_a_project() -> None:
    kinds = {
        p.stem: {card["kind"] for card in json.loads(p.read_text(encoding="utf-8"))["cards"]}
        for p in STARTERS
    }

    assert kinds["profile"] == {
        "hero",
        "heading",
        "stats",
        "streak",
        "breakdown",
        "tiles",
        "marquee",
        "timeline",
        "divider",
        "banner",
    }
    assert kinds["project"] == {"banner", "badge", "flow", "chart", "typing", "breakdown"}


def test_snippet_lists_sources_alt_links_and_width_only_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    starter = tmp_path / "project.json"
    shutil.copy(PACKS / "project.json", starter)

    assert run([str(starter)], capsys)[0] == 0

    out = tmp_path / "assets" / "cards"
    text = (out / "snippet.md").read_text(encoding="utf-8")
    assert text.startswith("# svg-forge snippet\n") and "\r" not in text
    found = HTML_BLOCK.search(text)
    assert found
    markup = found.group(1)
    body = json.loads(starter.read_text(encoding="utf-8"))
    files = expected_files(body)
    firsts = [markup.index(f"assets/cards/{card['name']}-") for card in body["cards"]]
    assert firsts == sorted(firsts), "cards keep pack order"
    for card in body["cards"]:
        for name in files[card["name"]]:
            assert f'srcset="assets/cards/{name}"' in markup
        img = files[card["name"]][1 if len(files[card["name"]]) == 4 else 0]  # dark, phone first
        assert f'<img alt="{html.escape(card["alt"])}" src="assets/cards/{img}"' in markup
    assert "height=" not in markup

    rows = re.findall(r'<p align="center">\n(.*?)\n</p>', markup, re.S)
    badges = [card for card in body["cards"] if card.get("row") == "badges"]
    assert len(rows) == 1 and len(badges) == 3
    lines = rows[0].split("\n")
    assert len(lines) == len(badges)
    for line, card in zip(lines, badges, strict=True):
        assert line.startswith(f'<a href="{card["link"]}"><picture><source ')
        assert line.endswith("></picture></a>")
        img = re.findall(r"<img [^>]*>", line)
        assert len(img) == 1
        width = svg_width(out / f"{card['name']}-dark.svg")
        assert img[0].endswith(f' width="{width}">') and img[0].count("width=") == 1
    assert markup.count("<a href=") == sum("link" in card for card in body["cards"])


def test_phone_layouts_swap_at_desktop_width_and_rows_set_only_width(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(forge.KINDS, "tiles", dataclasses.replace(forge.KINDS["tiles"], phone=True))
    path = write_pack(
        tmp_path,
        {
            "theme": "both",
            "device": "both",
            "cards": [
                {"name": "stats", "kind": "tiles", "alt": "Stats", "row": "top"},
                {"name": "more", "kind": "tiles", "alt": "More", "link": "https://x.test/?a=1&b=2"},
                {"name": "rule", "kind": "divider", "alt": ""},
                {"name": "wide", "kind": "tiles", "alt": "Wide", "size": "og"},
            ],
        },
    )

    assert run([str(path)], capsys)[0] == 0

    out = tmp_path / "assets" / "cards"
    names = {p.name for p in out.iterdir()}
    assert {"stats-dark-mobile.svg", "stats-light-mobile.svg", "more-light-mobile.svg"} <= names
    assert {"rule-dark.svg", "rule-light.svg", "wide-dark.svg", "wide-light.svg"} <= names
    assert not {"rule-dark-mobile.svg", "wide-dark-mobile.svg"} & names
    text = (out / "snippet.md").read_text(encoding="utf-8")
    assert text.count(f' and {forge.DESKTOP_MEDIA}" srcset=') == 4
    more = re.search(r'^<a href="https://x\.test/\?a=1&amp;b=2"><picture><source .*$', text, re.M)
    assert more, "a linked card sits on one line inside its <a>"
    more_width = svg_width(out / "more-dark.svg")
    img = f'<img alt="More" src="assets/cards/more-dark-mobile.svg" width="{more_width}">'
    assert more.group(0).endswith(f"{img}</picture></a>")
    row = re.search(r'<p align="center">\n(.*)\n</p>', text)
    assert row
    width = svg_width(out / "stats-dark.svg")
    assert row.group(1).endswith(
        f'<img alt="Stats" src="assets/cards/stats-dark-mobile.svg" width="{width}"></picture>'
    )


def test_pack_breakpoint_reaches_every_desktop_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cards = [{"name": "stats", "kind": "stats", "alt": "Stats"}]
    path = write_pack(
        tmp_path, {"theme": "both", "device": "both", "breakpoint": 900, "cards": cards}
    )

    assert run([str(path)], capsys)[0] == 0

    text = (tmp_path / "assets" / "cards" / "snippet.md").read_text(encoding="utf-8")
    assert text.count(" and (min-width: 900px)") == 2 and "1012px" not in text


@pytest.mark.parametrize("value", [320, 5000, 900.5, "wide", True])
def test_bad_breakpoint_exits_2(
    value: object, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_pack(tmp_path, {"breakpoint": value, "cards": [GOOD]})

    code, _, err = run([str(path)], capsys)

    assert code == 2 and "pack.json: breakpoint: must be a whole px width over 320" in err


def test_pack_card_matches_forge_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    hero = {"kicker": "Hello", "taglines": ["Fast builds", "Small diffs"]}
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "stats.json").write_text(
        json.dumps([{"value": "42", "label": "repos"}, {"value": "7", "label": "languages"}]),
        encoding="utf-8",
    )
    path = write_pack(
        tmp_path,
        {
            "theme": "both",
            "accent": "#22c55e",
            "out_dir": "out",
            "cards": [
                {
                    "name": "hero",
                    "kind": "hero",
                    "alt": "Hero",
                    "timing": "short",
                    "title": "Northwind",
                    "data": hero,
                },
                {
                    "name": "stats",
                    "kind": "tiles",
                    "alt": "Stats",
                    "data_file": "data/stats.json",
                    "loop": False,
                    "width": 600,
                },
                {
                    "name": "dots",
                    "kind": "loader",
                    "alt": "Loading",
                    "theme": "nord",
                    "variant": "dots",
                    "size": "icon-128",
                },
            ],
        },
    )
    monkeypatch.chdir(tmp_path / "data")  # the pack's paths resolve from its own folder

    assert run([str(path)], capsys)[0] == 0

    out = tmp_path / "out"
    same = forge.render(
        "hero",
        theme="dark",
        pair=True,
        accent="#22c55e",
        timing="short",
        title="Northwind",
        data=hero,
    )
    assert (out / "hero-dark.svg").read_text(encoding="utf-8") == same
    monkeypatch.chdir(tmp_path)
    accent = ["--accent", "#22c55e"]
    commands = {
        "hero": ["--kind", "hero", "--theme", "both", *accent, "--timing", "short"],
        "stats": ["--kind", "tiles", "--theme", "both", *accent, "--once", "--width", "600"],
        "dots": ["--kind", "loader", "--theme", "nord", *accent, "--variant", "dots"],
    }
    commands["hero"] += ["--title", "Northwind", "--data", json.dumps(hero)]
    commands["stats"] += ["--data", "data/stats.json"]
    commands["dots"] += ["--size", "icon-128"]
    for name, argv in commands.items():
        assert forge.main([*argv, "--out", f"forge/{name}.svg"]) == 0
    capsys.readouterr()
    built = sorted((tmp_path / "forge").glob("*.svg"))
    assert [p.name for p in built] == sorted(p.name for p in out.glob("*.svg"))
    for p in built:
        assert p.read_bytes() == (out / p.name).read_bytes(), p.name


def test_second_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "cards"
    argv = [str(PACKS / "project.json"), "--out-dir", str(out)]
    code, first, _ = run(argv, capsys)
    stamps = {p: p.stat().st_mtime_ns for p in out.iterdir()}

    code_again, second, _ = run(argv, capsys)

    assert code == code_again == 0
    assert first.count("wrote ") == len(stamps)
    assert "wrote " not in second and second.count("unchanged ") == len(stamps)
    assert {p: p.stat().st_mtime_ns for p in out.iterdir()} == stamps


def test_check_exits_0_when_current_and_1_when_stale_or_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cards"
    argv = [str(PACKS / "profile.json"), "--out-dir", str(out)]

    assert run([*argv, "--check"], capsys)[0] == 1
    assert not out.exists(), "--check never writes"
    assert run(argv, capsys)[0] == 0
    code, report, _ = run([*argv, "--check"], capsys)
    assert code == 0
    total = len(list(out.iterdir()))
    assert report == f"{total} of {total} files match\n"

    hero = out / "hero-dark.svg"
    hero.write_bytes(hero.read_bytes().replace(b"</svg>", b"<g/></svg>"))
    (out / "snippet.md").unlink()
    code, report, _ = run([*argv, "--check"], capsys)

    assert code == 1
    assert f"differs {hero.as_posix()}\n" in report
    assert f"missing {(out / 'snippet.md').as_posix()}\n" in report
    assert report.endswith(f"{total - 2} of {total} files match\n")


GOOD = {"name": "stats", "kind": "tiles", "alt": "Stats"}


@pytest.mark.parametrize(
    ("card", "field"),
    [
        ({"name": "stats", "kind": "tiles"}, "alt"),
        ({**GOOD, "alt": 3}, "alt"),
        ({**GOOD, "kind": "tile"}, "kind"),
        ({**GOOD, "timing": "fast"}, "timing"),
        ({**GOOD, "width": "wide"}, "width"),
        ({**GOOD, "loop": "yes"}, "loop"),
        ({**GOOD, "colour": "#ffffff"}, "colour"),
        ({**GOOD, "link": "javascript:alert(1)"}, "link"),
        ({**GOOD, "row": ""}, "row"),
        ({**GOOD, "data": {"items": "nope"}}, "items"),
        ({**GOOD, "data_file": "missing.json"}, "data_file"),
        ({**GOOD, "data": [], "data_file": "x.json"}, "data_file"),
        ({**GOOD, "name": "stats-dark"}, "name"),
        ({**GOOD, "link": " javascript:alert(1)"}, "link"),
        ({**GOOD, "link": "java\tscript:alert(1)"}, "link"),
        ({**GOOD, "width": 10**400}, "width"),
        ({"name": "rule", "kind": "divider", "alt": "", "device": "phone"}, "device"),
    ],
)
def test_bad_card_exits_2_naming_the_card_and_field(
    card: dict[str, Any], field: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cards = [{"name": "ok", "kind": "badge", "alt": "Badge"}, card]
    path = write_pack(tmp_path, {"theme": "both", "cards": cards})

    code, out, err = run([str(path)], capsys)

    assert code == 2 and out == ""
    assert err.startswith(f"pack.py: error: pack.json: cards[1] ({card['name']}): ")
    assert field in err and err.count("\n") == 1
    assert not (tmp_path / "assets").exists(), "a bad pack writes nothing"


def test_every_problem_is_reported_at_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cards = [GOOD, GOOD, {"name": "x", "kind": "nope", "alt": ""}, "hero"]
    path = write_pack(tmp_path, {"theme": "both", "acent": "#fff", "cards": cards})

    code, _, err = run([str(path)], capsys)

    assert code == 2
    lines = err.splitlines()
    assert lines[0] == "pack.py: error: pack.json: acent: unknown key, did you mean 'accent'?"
    assert lines[1].startswith("pack.py: error: pack.json: cards[1] (stats): name: ")
    assert lines[2].startswith("pack.py: error: pack.json: cards[2] (x): kind: ")
    assert lines[3].startswith("pack.py: error: pack.json: cards[3]: must be an object")
    assert len(lines) == 4


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{", "pack.json: line 1: not valid JSON"),
        ("[]", "pack.json: must be a JSON object"),
        ('{"cards": []}', "pack.json: cards: required"),
    ],
)
def test_bad_pack_file_exits_2(
    text: str, message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "pack.json"
    path.write_text(text, encoding="utf-8")

    code, _, err = run([str(path)], capsys)

    assert code == 2 and message in err


def test_utf16_pack_exits_2_and_a_bom_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "pack.json"
    path.write_text(json.dumps({"cards": [GOOD]}), encoding="utf-16")

    code, _, err = run([str(path)], capsys)

    assert code == 2 and "pack.json: not UTF-8 text" in err
    path.write_text(json.dumps({"cards": [GOOD]}), encoding="utf-8-sig")
    assert run([str(path)], capsys)[0] == 0
