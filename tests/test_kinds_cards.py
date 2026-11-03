"""forge.py card and quote kinds: project cards and quote cards, desktop and phone."""

from __future__ import annotations

import re
from pathlib import Path
from xml.dom import minidom

import pytest

import forge
import poster
import validate_svg
from test_integration import overflow

KINDS = ["card", "quote"]
TIMINGS = ["micro", "short", "medium", "long", "ambient"]
SHAPES: list[dict[str, object]] = [
    {},
    {"device": "phone"},
    {"width": 600},
    {"width": 260},
    {"width": 900, "height": 300},
    {"size": "card"},
    {"size": "readme-half"},
    {"size": "story"},
]
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]
MANY_TAGS = [f"tag{i}" for i in range(12)]
LONG = " ".join(["word"] * 40 + ["tail"] * 80)


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the GitHub page(s) the file is shown on;
    parses with minidom."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def texts(svg: str, cls: str | None = None) -> list[minidom.Element]:
    """<text> elements, optionally only those whose class ends in -cls."""
    found = minidom.parseString(svg).getElementsByTagName("text")
    return [t for t in found if cls is None or t.getAttribute("class").endswith(f"-{cls}")]


def content(node: minidom.Element) -> str:
    return "".join(n.data for n in node.childNodes if n.nodeType == n.TEXT_NODE)


def size_of(svg: str) -> tuple[str, str]:
    root = minidom.parseString(svg).documentElement
    return root.getAttribute("width"), root.getAttribute("height")


# ---------------------------------------------------------------- both kinds


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("timing", TIMINGS)
@pytest.mark.parametrize("loop", [None, True, False])
def test_kind_is_valid_poster_safe_and_deterministic(
    kind: str, theme: str, timing: str, loop: bool | None
) -> None:
    svg = forge.render(kind, theme=theme, timing=timing, loop=loop)

    check(svg)
    assert poster.problems(svg) == []
    assert overflow(svg) == []
    assert svg == forge.render(kind, theme=theme, timing=timing, loop=loop)
    assert svg.endswith("</svg>\n") and "\r" not in svg


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("shape", SHAPES, ids=str)
def test_text_stays_inside_any_canvas(kind: str, shape: dict[str, object]) -> None:
    svg = forge.render(kind, **shape)

    check(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_phone_layout_is_320_wide_with_phone_text(kind: str, theme: str) -> None:
    svg = forge.render(kind, theme=theme, device="phone")

    check(svg)
    assert size_of(svg)[0] == str(forge.PHONE_W)
    sizes = [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]
    assert sizes and min(sizes) >= forge.PHONE_TEXT
    assert overflow(svg) == [] and poster.problems(svg) == []


@pytest.mark.parametrize("kind", KINDS)
def test_pair_halves_read_on_their_own_page(kind: str, tmp_path: Path) -> None:
    out = tmp_path / f"{kind}.svg"

    code = forge.main(["--kind", kind, "--theme", "both", "--device", "both", "--out", str(out)])

    assert code == 0
    for suffix in ("dark", "light"):
        desktop = (tmp_path / f"{kind}-{suffix}.svg").read_text(encoding="utf-8")
        phone = (tmp_path / f"{kind}-{suffix}-mobile.svg").read_text(encoding="utf-8")
        check(desktop, suffix)
        check(phone, suffix)
        assert size_of(phone)[0] == str(forge.PHONE_W)
        assert overflow(phone) == [] and poster.problems(phone) == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("timing", ["short", "micro"])
def test_one_shot_entrance_finishes_in_time(kind: str, timing: str) -> None:
    report = check(forge.render(kind, timing=timing))

    assert report.stats["longest_s"] <= forge.PRESETS[timing].total
    assert report.stats["infinite"] == 0


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("timing", ["medium", "long", "ambient"])
def test_one_clock_per_file(kind: str, timing: str) -> None:
    svg = forge.render(kind, timing=timing)

    durations = {float(d) for d in re.findall(r'dur="([\d.]+)s"', svg)}
    longest = max(durations)
    assert forge.PRESETS[timing].lo <= longest <= forge.PRESETS[timing].hi
    assert all(abs(longest / d - round(longest / d)) < 0.01 for d in durations)  # ms rounding


@pytest.mark.parametrize("kind", KINDS)
def test_ids_and_classes_carry_one_prefix(kind: str) -> None:
    svg = forge.render(kind)

    prefix = re.search(r'<title id="([\w-]+?)title"', svg).group(1)
    assert all(i.startswith(prefix) for i in re.findall(r'\bid="([^"]+)"', svg))
    assert all(c.startswith(prefix) for c in re.findall(r'class="([^"]+)"', svg))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_text_is_escaped(kind: str, text: str) -> None:
    data = {
        "card": {"title": text, "description": text, "status": text, "tags": [text]},
        "quote": {"quotes": [{"text": text, "author": text}, {"text": text}]},
    }[kind]

    svg = forge.render(kind, title=text, data=data)

    check(svg)
    assert "<script" not in svg and "&lt;" in svg
    shown = [content(t) for t in texts(svg, "r")]
    assert text in shown  # the description or the quote itself, escaped and parsed back


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("card", {}),
        ("card", {"title": ""}),
        ("card", {"title": {"a": 1}}),
        ("card", {"title": "x", "tags": "python"}),
        ("card", {"title": "x", "tags": [{"b": 2}]}),
        ("card", {"title": "x", "tags": ["t"] * 31}),
        ("card", {"title": "x", "stars": -1}),
        ("card", {"title": "x", "forks": True}),
        ("card", {"title": "x", "description": ["a"]}),
        ("card", ["python", "go"]),
        ("card", 42),
        ("quote", {}),
        ("quote", {"quotes": []}),
        ("quote", {"quotes": [{"author": "x"}]}),
        ("quote", {"quotes": [7.5]}),
        ("quote", {"quotes": ["a"] * 7}),
        ("quote", {"text": ""}),
        ("quote", {"text": "a", "author": ["b"]}),
        ("quote", 42),
    ],
)
def test_bad_data_is_rejected(kind: str, data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render(kind, data=data)


@pytest.mark.parametrize(("kind", "data"), [("card", "{}"), ("quote", '{"quotes": []}')])
def test_cli_bad_data_exits_2(kind: str, data: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert forge.main(["--kind", kind, "--data", data]) == 2
    assert "forge.py: error:" in capsys.readouterr().err


# ---------------------------------------------------------------- card


def test_card_tags_cap_with_a_more_chip() -> None:
    svg = forge.render("card", data={"title": "Northwind", "tags": MANY_TAGS})

    check(svg)
    labels = [content(t) for t in texts(svg, "m")]
    chips = [t for t in labels if t.startswith("tag")]
    more = [t for t in labels if t.endswith(" more")]
    assert chips == MANY_TAGS[: len(chips)] and 0 < len(chips) < len(MANY_TAGS)
    assert more == [f"+{len(MANY_TAGS) - len(chips)} more"]


def test_card_tags_that_fit_need_no_more_chip() -> None:
    svg = forge.render("card", data={"title": "Northwind", "tags": ["go", "cli"]})

    labels = [content(t) for t in texts(svg, "m")]
    assert "go" in labels and "cli" in labels
    assert not any(t.endswith(" more") for t in labels)


@pytest.mark.parametrize("device", forge.DEVICES)
def test_card_long_description_wraps_and_ends_with_an_ellipsis(device: str) -> None:
    svg = forge.render("card", device=device, data={"title": "Northwind", "description": LONG})

    check(svg)
    lines = texts(svg, "r")
    width = float(size_of(svg)[0])
    room = width - 2 * 22 * forge.layout_scale(width, 410, None, lambda k: 0)
    assert len(lines) == 3
    assert content(lines[-1]).endswith(forge.ELLIPSIS)
    for line in lines:
        size = float(line.getAttribute("font-size"))
        assert forge.text_width(content(line), size, "sans") <= room + 0.01


def test_card_shows_the_repo_pin_facts() -> None:
    svg = forge.render("card")

    shown = [content(t) for t in texts(svg)]
    assert "Python" in shown and "1.2k" in shown and "86" in shown
    assert forge.GLYPHS["star"][1] in svg and forge.GLYPHS["fork"][0] in svg
    assert "LIVE" in shown and "MAR 2026" in shown


def test_card_counts_take_numbers_or_text() -> None:
    svg = forge.render("card", data={"title": "x", "stars": 2_500_000, "forks": "many"})

    shown = [content(t) for t in texts(svg)]
    assert "2.5M" in shown and "many" in shown


def test_card_height_does_not_follow_its_data() -> None:
    bare = forge.render("card", data={"title": "Bluefin"})

    assert size_of(bare) == size_of(forge.render("card")) == ("410", "196")
    check(bare)
    assert poster.problems(bare) == []


def test_card_live_dot_pulses_only_when_looping() -> None:
    looping = forge.render("card")
    once = forge.render("card", timing="short")

    assert '<animate attributeName="opacity" values="1;0.35;1"' in looping
    assert 'values="1;0.35;1"' not in once


def test_card_shine_sweeps_inside_the_card() -> None:
    svg = forge.render("card")

    assert re.search(r'<g clip-path="url\(#[\w-]+clip\)"><rect [^>]*skewX\(-18\)', svg)
    assert 'additive="sum"' in svg


# ---------------------------------------------------------------- quote


def still_quote(svg: str) -> str:
    """The quote lines a static renderer draws (rows a quote leaves empty are skipped)."""
    lines = texts(svg, "r")
    return " ".join(content(t) for t in lines if t.getAttribute("opacity") != "0" and content(t))


def test_quotes_take_turns_and_the_still_frame_shows_the_first() -> None:
    svg = forge.render("quote")

    check(svg)
    assert still_quote(svg) == forge.SAMPLES["quote"]["quotes"][0]["text"]
    assert all(t.getElementsByTagName("animate") for t in texts(svg, "r"))


def test_quotes_played_once_end_on_the_last() -> None:
    svg = forge.render("quote", loop=False)

    check(svg)
    assert still_quote(svg) == forge.SAMPLES["quote"]["quotes"][-1]["text"]
    assert poster.problems(svg) == []


def test_single_quote_fades_in_and_holds() -> None:
    data = {"text": "Leave the campsite tidier than you found it.", "author": "Lumen"}

    svg = forge.render("quote", data=data, loop=False)

    check(svg)
    assert 'opacity="0"' not in svg
    assert [content(t) for t in texts(svg, "r")] == [data["text"]]
    assert "LUMEN" in [content(t) for t in texts(svg, "m")]
    assert 'fill="freeze"' in svg and "indefinite" not in svg


def test_bare_string_and_list_are_quotes() -> None:
    one = forge.render("quote", data="Small steps, every day.")
    two = forge.render("quote", data=["First line.", {"text": "Second line.", "author": "B"}])

    assert [content(t) for t in texts(one, "r")] == ["Small steps, every day."]
    check(one)
    check(two)


@pytest.mark.parametrize("device", forge.DEVICES)
def test_long_quote_wraps_into_five_lines_with_an_ellipsis(device: str) -> None:
    svg = forge.render("quote", device=device, data={"text": LONG, "author": "Quartz"})

    check(svg)
    lines = texts(svg, "r")
    assert len(lines) == 5
    assert content(lines[-1]).endswith(forge.ELLIPSIS)
    assert overflow(svg) == []


def test_six_long_quotes_stay_within_the_animation_budget() -> None:
    data = [{"text": LONG, "author": f"Team {i}"} for i in range(6)]

    report = check(forge.render("quote", data=data))

    assert report.stats["animated_elements"] <= 40


def test_one_shot_quote_shows_the_first_only() -> None:
    svg = forge.render("quote", timing="short")

    first = forge.SAMPLES["quote"]["quotes"][0]["text"]
    assert " ".join(content(t) for t in texts(svg, "r")) == first
