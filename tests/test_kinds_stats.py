"""forge.py kinds stats and streak: the summary card and the contribution streak card."""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path
from xml.dom import minidom

import pytest
from test_integration import overflow

import forge
import poster
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
KINDS = ["stats", "streak"]
CONTRIBUTIONS = json.loads((ROOT / "examples" / "data" / "contributions.json").read_text("utf-8"))
HOSTILE = ['a<b&c"d', "</text><script>alert(1)</script>"]
SIZES = [(None, None), (320, None), (360, 200), (400, 200), (900, None), (1600, 900), (200, 120)]
VARIANTS: list[tuple[str, dict[str, object]]] = [
    ("stats", {}),
    ("stats", {"data": {"rows": [{"label": "Stars", "value": 3}]}}),
    ("stats", {"data": [{"label": f"row {i}", "value": i, "glyph": "eye"} for i in range(6)]}),
    (
        "stats",
        {
            "title": "Project",
            "data": {"rows": [{"label": "a", "value": "1"}], "grade": {"label": "B", "value": 0}},
        },
    ),
    ("streak", {}),
    ("streak", {"data": CONTRIBUTIONS}),
    ("streak", {"title": "Streak", "data": {"total": 0, "current": 0, "longest": 0}}),
]


def check(svg: str, theme: str = "both") -> validate_svg.Report:
    """No findings at all, contrast as errors on the given GitHub page(s); parses."""
    report = validate_svg.validate_text(svg.encode("utf-8"), contrast="error", theme=theme)
    assert report.findings == [], report.findings
    minidom.parseString(svg)
    return report


def reference_streaks(days: list[int]) -> tuple[int, int]:
    """streaks() as published in github-stats-card-action (MIT, same author)."""
    longest = run = 0
    for count in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current = 0
    # today may still be empty; a streak is only broken by an empty yesterday
    tail = days[:-1] if days and days[-1] == 0 else days
    for count in reversed(tail):
        if not count:
            break
        current += 1
    return current, longest


def texts(svg: str) -> list[str]:
    return re.findall(r"<text [^>]*>([^<]*)</text>", svg)


def font_sizes(svg: str) -> list[float]:
    return [float(v) for v in re.findall(r'font-size="([\d.]+)"', svg)]


def text_y(svg: str, content: str) -> float:
    return float(re.search(rf'<text [^>]*y="([\d.]+)"[^>]*>{re.escape(content)}</text>', svg)[1])


# ---------------------------------------------------------------- both kinds


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("timing", ["short", "medium", "long", "ambient", "micro"])
@pytest.mark.parametrize("loop", [None, True, False])
def test_kind_is_valid_deterministic_and_poster_safe(
    kind: str, theme: str, timing: str, loop: bool | None
) -> None:
    svg = forge.render(kind, theme=theme, timing=timing, loop=loop)

    report = check(svg)
    assert svg == forge.render(kind, theme=theme, timing=timing, loop=loop)
    assert poster.problems(svg) == []
    assert overflow(svg) == []
    assert report.stats["animated_elements"] <= 12
    assert len(set(re.findall(r'dur="([\d.]+)s"', svg))) == 1  # one clock
    assert "prefers-reduced-motion" not in svg


@pytest.mark.parametrize(("kind", "options"), VARIANTS, ids=str)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_variant_is_valid_and_poster_safe(
    kind: str, options: dict[str, object], theme: str
) -> None:
    svg = forge.render(kind, theme=theme, **options)

    check(svg)
    assert poster.problems(svg) == []
    assert overflow(svg) == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_text_stays_inside_the_canvas_at_any_size(
    kind: str, size: tuple[float | None, float | None]
) -> None:
    svg = forge.render(kind, width=size[0], height=size[1])

    check(svg)
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert min(font_sizes(svg)) >= forge.FONT_FLOOR


@pytest.mark.parametrize("kind", KINDS)
def test_default_card_is_495_by_195_so_two_sit_side_by_side(kind: str) -> None:
    root = minidom.parseString(forge.render(kind)).documentElement

    assert (root.getAttribute("width"), root.getAttribute("height")) == ("495", "195")


@pytest.mark.parametrize("kind", KINDS)
def test_short_entrance_finishes_by_one_and_a_half_seconds(kind: str) -> None:
    report = check(forge.render(kind, timing="short"))

    assert report.stats["longest_s"] <= 1.5
    assert report.stats["infinite"] == 0


@pytest.mark.parametrize("kind", KINDS)
def test_marks_use_the_accent(kind: str) -> None:
    svg = forge.render(kind, accent="#a78bfa")

    ink = forge.accent_ink("#a78bfa", forge.THEMES["dark"])
    assert f'stroke="{ink}"' in svg


# ---------------------------------------------------------------- pairs and phones


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "flags", [["--theme", "both"], ["--theme", "catppuccin", "--mode", "both"]], ids=str
)
def test_pair_halves_read_on_their_own_page(kind: str, flags: list[str], tmp_path: Path) -> None:
    out = tmp_path / "card.svg"

    with contextlib.redirect_stdout(io.StringIO()) as printed:
        code = forge.main(["--kind", kind, *flags, "--device", "both", "--out", str(out)])

    assert code == 0
    assert "<picture>" in printed.getvalue()
    for name, page in (
        ("card-dark", "dark"),
        ("card-light", "light"),
        ("card-dark-mobile", "dark"),
        ("card-light-mobile", "light"),
    ):
        svg = (tmp_path / f"{name}.svg").read_text(encoding="utf-8")
        check(svg, page)
        assert poster.problems(svg) == [] and overflow(svg) == []


@pytest.mark.parametrize(("kind", "options"), VARIANTS, ids=str)
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_phone_layout_is_320_wide_with_phone_text(
    kind: str, options: dict[str, object], theme: str
) -> None:
    svg = forge.render(kind, theme=theme, device="phone", **options)

    check(svg)
    assert minidom.parseString(svg).documentElement.getAttribute("width") == "320"
    assert min(font_sizes(svg)) >= forge.PHONE_TEXT
    assert overflow(svg) == []
    assert poster.problems(svg) == []
    assert svg == forge.render(kind, theme=theme, device="phone", **options)


def test_streak_phone_puts_the_current_streak_on_top() -> None:
    phone = forge.render("streak", device="phone")
    desk = forge.render("streak")

    assert text_y(phone, "12") < text_y(phone, "1,284")  # current above total
    assert text_y(phone, "1,284") == text_y(phone, "41")  # total and longest side by side
    assert abs(text_y(desk, "12") - text_y(desk, "1,284")) < 15  # one row on desktop


def test_streak_runs_stacked_under_400_px() -> None:
    svg = forge.render("streak", width=360)

    assert text_y(svg, "12") < text_y(svg, "1,284")


# ---------------------------------------------------------------- streak rule


DAY_LISTS = [
    [],
    [0],
    [3],
    [1, 1, 0],  # today empty: the streak still stands
    [1, 1, 0, 0],  # yesterday empty: broken
    [1, 0, 1, 1],  # a gap, then two days up to today
    [3, 0, 2, 2, 2, 0, 1],
    [0, 1, 1, 1, 0],
    [1] * 40,  # one long run
    [1] * 12 + [0] + [1] * 5 + [0],
    [0, 0, 0, 0],
    [2, 2, 0, 2, 2, 0, 0],  # two runs tie for longest
    forge.sample_counts(),
]


@pytest.mark.parametrize("days", DAY_LISTS, ids=lambda d: ",".join(map(str, d[:12])))
def test_streak_rule_matches_the_ported_one(days: list[int]) -> None:
    current, _, longest, _ = forge.streaks(days)

    assert (current, longest) == reference_streaks(days)


def test_streak_rule_reports_where_each_run_ends() -> None:
    assert forge.streaks([1, 1, 0, 1, 0]) == (1, 3, 2, 1)
    assert forge.streaks([2, 2, 0, 2, 2, 0, 0]) == (0, -1, 2, 4)  # a tie: the latest run
    assert forge.streaks([]) == (0, -1, 0, -1)


def test_streak_from_contributions_computes_numbers_and_ranges() -> None:
    data = {"start": "2026-03-01", "counts": [2, 2, 2, 2, 0, 1, 1, 0]}  # today, Mar 8, empty

    svg = forge.render("streak", data=data)

    shown = texts(svg)
    for want in (
        "10",
        "Mar 1 - Mar 8, 2026",
        "2",
        "Mar 6 - Mar 7, 2026",
        "4",
        "Mar 1 - Mar 4, 2026",
    ):
        assert want in shown, want
    assert "current streak 2 days (Mar 6 - Mar 7, 2026)" in svg


def test_streak_with_no_current_run_shows_today() -> None:
    svg = forge.render("streak", data={"start": "2026-03-01", "counts": [1, 1, 0, 0]})

    assert "Mar 4, 2026" in texts(svg)
    assert "current streak 0 days (Mar 4, 2026)" in svg


def test_streak_days_and_counts_formats_draw_the_same_card() -> None:
    days = {"days": [{"date": "2026-03-01", "count": 2}, {"date": "2026-03-03", "count": 5}]}
    counts = {"start": "2026-03-01", "counts": [2, 0, 5]}

    assert forge.render("streak", data=days, id_prefix="k") == forge.render(
        "streak", data=counts, id_prefix="k"
    )


def test_streak_bare_list_is_a_days_list() -> None:
    svg = forge.render("streak", data=[{"date": "2026-01-02", "count": 4}])

    assert "4 contributions (Jan 2, 2026)" in svg


def test_streak_example_data_agrees_with_the_ported_rule() -> None:
    days = forge.calendar_days(CONTRIBUTIONS)
    first, last = min(days), max(days)
    counts = [days.get(first + timedelta(days=k), 0) for k in range((last - first).days + 1)]

    current, longest = reference_streaks(counts)
    svg = forge.render("streak", data=CONTRIBUTIONS)

    assert f"current streak {current} days" in svg and f"longest streak {longest} days" in svg


@pytest.mark.parametrize(
    ("a", "b", "options"),
    [
        ("2026-03-02", "2026-03-02", ["Mar 2, 2026", "Mar 2"]),
        ("2026-03-02", "2026-03-30", ["Mar 2 - Mar 30, 2026", "Mar 2 - Mar 30"]),
        (
            "2025-12-28",
            "2026-01-06",
            ["Dec 28, 2025 - Jan 6, 2026", "Dec 28 - Jan 6, 2026", "Dec 2025 - Jan 2026"],
        ),
        ("2025-10-07", "2026-10-10", ["Oct 7, 2025 - Oct 10, 2026", "Oct 2025 - Oct 2026"]),
    ],
)
def test_date_ranges_shorten_to_fit(a: str, b: str, options: list[str]) -> None:
    got = forge.span_texts(date.fromisoformat(a), date.fromisoformat(b))

    assert got == options
    assert forge.first_fit(options, 1000, 10) == options[0]
    assert forge.first_fit(options, forge.text_width(options[-1], 10), 10) == options[-1]


def test_given_numbers_are_shown_with_their_ranges() -> None:
    data = {"total": 12345, "total_range": "Since 2019", "current": 1, "longest": 7}

    svg = forge.render("streak", data=data)

    shown = texts(svg)
    assert {"12,345", "Since 2019", "1", "7"} <= set(shown)
    assert "current streak 1 day;" in svg


# ---------------------------------------------------------------- stats


def test_stats_values_are_static_text_shown_as_given() -> None:
    rows = [{"label": "Stars", "value": "1.2k"}, {"label": "Commits", "value": 864}]

    svg = forge.render("stats", data=rows)

    assert re.search(r"<text [^>]*>1\.2k</text>", svg)  # no animate child: nothing counts up
    assert re.search(r"<text [^>]*>864</text>", svg)


def test_stats_grade_arc_is_dash_math() -> None:
    grade = {"label": "B", "value": 0.25}

    svg = forge.render("stats", data={"rows": [{"label": "a", "value": 1}], "grade": grade})

    arc = re.search(
        r'<circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)"[^>]*stroke-dasharray="([\d.]+) ([\d.]+)"',
        svg,
    )
    r, dash, gap = (float(v) for v in arc.groups())
    assert dash == pytest.approx(2 * math.pi * r * 0.25, abs=0.02)
    assert gap == pytest.approx(2 * math.pi * r, abs=0.02)
    assert ">B</text>" in svg and "grade B (25%)" in svg


def test_stats_without_a_grade_draws_no_ring() -> None:
    svg = forge.render("stats", data=[{"label": "Stars", "value": "9"}])

    assert "<circle" not in svg


def test_stats_zero_grade_draws_only_the_track() -> None:
    grade = {"label": "C", "value": 0}

    svg = forge.render("stats", data={"rows": [{"label": "a", "value": 1}], "grade": grade})

    assert svg.count("<circle") == 1


def test_stats_draws_each_rows_glyph() -> None:
    rows = [{"label": name, "value": 1, "glyph": name} for name in ("star", "pull", "flame")]

    svg = forge.render("stats", data=rows)

    for name in ("star", "pull", "flame"):
        stroked, filled = forge.GLYPHS[name]
        assert f'd="{stroked or filled}"' in svg


def test_stats_long_label_gives_way_to_the_value_and_stays_in_the_desc() -> None:
    row = {"label": "x" * 40, "value": "1234567890123456", "glyph": "star"}

    svg = forge.render("stats", data={"rows": [row], "grade": {"label": "A", "value": 1}})

    assert forge.ELLIPSIS in svg
    assert ">1234567890123456</text>" in svg  # the value is never cut for the label
    assert "x" * 40 in svg.split("</desc>")[0]


# ---------------------------------------------------------------- escaping and bad data


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_text_is_escaped(kind: str, text: str) -> None:
    data = {
        "stats": {
            "title": text,
            "rows": [{"label": text, "value": text[:16]}],
            "grade": {"label": text[:6], "value": 0.5},
        },
        "streak": {
            "title": text,
            "total": 3,
            "total_range": text,
            "current": 1,
            "current_range": text,
            "longest": 2,
            "longest_range": text,
        },
    }[kind]

    svg = forge.render(kind, title=text, data=data)

    check(svg)
    assert "<script" not in svg and "&lt;" in svg
    if "&" in text:
        assert "&amp;" in svg


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("stats", {"rows": []}),
        ("stats", {"rows": [{"label": "a", "value": "1"}] * 7}),
        ("stats", {"rows": ["text"]}),
        ("stats", {"rows": [{"label": "a"}]}),
        ("stats", {"rows": [{"value": "1"}]}),
        ("stats", {"rows": [{"label": "a", "value": "1", "glyph": "rocket"}]}),
        ("stats", {"rows": [{"label": "a", "value": "1", "glyph": ["star"]}]}),
        ("stats", {"rows": [{"label": "a", "value": {"n": 1}}]}),
        ("stats", {"rows": [{"label": "a", "value": "1"}], "grade": "A"}),
        ("stats", {"rows": [{"label": "a", "value": "1"}], "grade": {"label": "A", "value": 2}}),
        ("stats", {"rows": [{"label": "a", "value": "1"}], "grade": {"value": 0.5}}),
        ("stats", {"rows": [{"label": "a", "value": "1"}], "grade": {"label": "A", "value": "x"}}),
        ("stats", 5),
        ("streak", {"total": 1}),
        ("streak", {"total": 1, "current": 1}),
        ("streak", {"total": -1, "current": 0, "longest": 0}),
        ("streak", {"total": 1, "current": 1.5, "longest": 2}),
        ("streak", {"total": "many", "current": 1, "longest": 2}),
        ("streak", {"total": 1, "current": 1, "longest": 2, "total_range": ["x"]}),
        ("streak", {"weeks": 3}),
        ("streak", {"days": []}),
        ("streak", {"days": [{"date": "2026-13-01", "count": 1}]}),
        ("streak", {"start": "soon", "counts": [1]}),
        ("streak", {"days": [{"date": "2010-01-01", "count": 1}, {"date": "2026-01-01"}]}),
    ],
)
def test_bad_data_is_rejected(kind: str, data: object) -> None:
    with pytest.raises(forge.ForgeError):
        forge.render(kind, data=data)


@pytest.mark.parametrize(
    ("kind", "data", "message"),
    [
        ("stats", '{"rows": [{"label": "a", "value": "1", "glyph": "rocket"}]}', "glyph"),
        ("streak", '{"total": 5}', "needs current"),
    ],
)
def test_cli_exits_2_on_bad_data(
    kind: str, data: str, message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert forge.main(["--kind", kind, "--data", data]) == 2
    assert message in capsys.readouterr().err
