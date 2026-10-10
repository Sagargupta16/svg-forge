"""frames.py: cycle detection, frame times, the HTML sheet, browser fallback, a real render."""

from __future__ import annotations

import zlib
from html.parser import HTMLParser
from pathlib import Path

import frames
import pytest

import validate_svg

NS = 'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" role="img" aria-label="probe"'


def svg(body: str) -> str:
    return f"<svg {NS}>{body}</svg>"


def cycle(body: str) -> tuple[float, bool]:
    return frames.timeline(validate_svg.parse(svg(body)))


def anim(attrs: str) -> str:
    return f'<rect width="1" height="1"><animate attributeName="x" values="0;1" {attrs}/></rect>'


def css(rules: str) -> str:
    return f"<style>{rules}</style>"


class Sheet(HTMLParser):
    """Collects iframes, sections and scripts from a contact sheet page."""

    def __init__(self) -> None:
        super().__init__()
        self.iframes: list[dict[str, str | None]] = []
        self.sections: list[dict[str, str | None]] = []
        self.scripts = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "iframe":
            self.iframes.append(dict(attrs))
        elif tag == "section":
            self.sections.append(dict(attrs))
        elif tag == "script":
            self.scripts += 1


def sheet_of(text: str) -> Sheet:
    parser = Sheet()
    parser.feed(text)
    return parser


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(frames.shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setattr(frames, "install_paths", list)


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "probe.svg"
    path.write_text(svg(body), encoding="utf-8")
    return path


def html_only(tmp_path: Path, src: Path, *extra: str) -> str:
    out = tmp_path / "sheet.png"
    assert frames.main([str(src), "--out", str(out), "--html-only", *extra]) == 0
    return (tmp_path / "sheet.html").read_text(encoding="utf-8")


# cycle detection


def test_smil_repeating_forever_counts_one_play() -> None:
    assert cycle(anim('dur="2s" repeatCount="indefinite"')) == (2.0, True)


def test_smil_finite_repeat_adds_begin_and_every_play() -> None:
    assert cycle(anim('begin="1s" dur="2s" repeatCount="3"')) == (7.0, False)


def test_smil_repeat_dur_caps_the_play() -> None:
    assert cycle(anim('dur="2s" repeatCount="5" repeatDur="3s"')) == (3.0, False)


def test_smil_second_offset_begin_plays_again() -> None:
    assert cycle(anim('begin="0s;5s" dur="1s"')) == (6.0, False)


def test_smil_syncbase_chain_resolves_to_one_loop() -> None:
    body = (
        anim('id="a1" begin="0s;a3.end" dur="1s"')
        + anim('id="a2" begin="a1.end" dur="1s"')
        + anim('id="a3" begin="a2.end+0.5s" dur="1s"')
    )
    assert cycle(body) == (3.5, True)


def test_smil_event_begin_never_starts_on_its_own() -> None:
    assert cycle(anim('begin="click" dur="1s"')) == (0.0, False)


def test_css_shorthand_reads_duration_delay_and_infinite() -> None:
    assert cycle(css(".a{animation:a 2.4s ease-out 0.5s infinite}")) == (2.9, True)


def test_css_longhands_and_iteration_count() -> None:
    rules = ".a{animation-name:a;animation-duration:1s;animation-delay:500ms;"
    rules += "animation-iteration-count:3}"
    assert cycle(css(rules)) == (3.5, False)


def test_css_style_attribute_counts() -> None:
    assert cycle('<rect style="animation: spin 1500ms linear infinite"/>') == (1.5, True)


def test_css_commas_inside_cubic_bezier_do_not_split_animations() -> None:
    rules = ".a{animation:a 2s cubic-bezier(0.1, 0.2, 0.3, 1) infinite, b 3s linear}"
    assert cycle(css(rules)) == (3.0, True)


def test_css_reduced_motion_block_is_ignored() -> None:
    rules = ".a{animation:a 1s infinite}"
    rules += "@media (prefers-reduced-motion: reduce){.a{animation-duration:9s!important}}"
    assert cycle(css(rules)) == (1.0, True)


def test_css_no_preference_block_still_counts() -> None:
    rules = "@media (prefers-reduced-motion: no-preference){.a{animation:a 3s}}"
    assert cycle(css(rules)) == (3.0, False)


def test_mixed_smil_and_css_takes_the_longest_play() -> None:
    body = anim('dur="5.365s" repeatCount="indefinite"') + css(".c{animation:c 1.05s infinite}")
    assert cycle(body) == (5.365, True)


def test_static_file_has_no_cycle() -> None:
    assert cycle('<rect width="10" height="10"/>') == (0.0, False)


# frame times


def test_loop_frames_run_from_zero_to_the_last_frame_before_restart() -> None:
    times = frames.frame_times(4.8, True, 6)
    assert len(times) == 6
    assert times[0] == 0.0
    assert times[-1] == round(4.8 - 1 / 60, 3)


def test_one_shot_frames_end_on_the_final_state() -> None:
    assert frames.frame_times(1.0, False, 6) == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def test_no_animation_gives_one_frame_at_zero() -> None:
    assert frames.frame_times(0.0, False, 6) == [0.0]


# the HTML sheet


def test_sheet_has_one_iframe_per_frame_with_its_time(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="4.8s" repeatCount="indefinite"'))
    page = sheet_of(html_only(tmp_path, src))
    assert [f["data-t"] for f in page.iframes] == ["0", "0.957", "1.913", "2.87", "3.827", "4.783"]


def test_sheet_labels_the_seam_frame(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="4.8s" repeatCount="indefinite"'))
    text = html_only(tmp_path, src)
    assert "t=4.783s k=0.996 | loops to t=0</figcaption>" in text
    assert "cycle 4.8s (auto) | loops" in text


def test_explicit_times_override_frames(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="4.8s" repeatCount="indefinite"'))
    text = html_only(tmp_path, src, "--frames", "9", "--times", "0,500ms,1.2s")
    assert [f["data-t"] for f in sheet_of(text).iframes] == ["0", "0.5", "1.2"]
    assert "loops to t=0" not in text


def test_explicit_duration_spreads_frames_over_it(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    text = html_only(tmp_path, src, "--duration", "10", "--frames", "3")
    assert [f["data-t"] for f in sheet_of(text).iframes] == ["0", "5", "10"]
    assert "cycle 10s (set)" in text


def test_theme_both_renders_a_dark_and_a_light_section(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s" repeatCount="indefinite"'))
    page = sheet_of(html_only(tmp_path, src, "--theme", "both"))
    assert [s["style"] for s in page.sections] == [
        "background:#0d1117;color:#8b949e",
        "background:#ffffff;color:#57606a",
    ]
    assert len(page.iframes) == 12
    assert {f["style"] for f in page.iframes} == {"color-scheme:dark", "color-scheme:light"}


def test_frames_are_sandboxed_and_network_blocked(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    for frame in sheet_of(html_only(tmp_path, src)).iframes:
        assert frame["sandbox"] == "allow-same-origin"
        assert f'content="{frames.CSP}"' in (frame["srcdoc"] or "")


def test_srcdoc_escapes_hostile_svg_text(tmp_path: Path) -> None:
    hostile = '"&gt;&lt;/iframe&gt;&lt;script&gt;alert(1)&lt;/script&gt;'
    src = write(tmp_path, f"<text>{hostile}</text>" + anim('dur="1s"'))
    page = sheet_of(html_only(tmp_path, src))
    assert page.scripts == 1  # only the seek script; nothing broke out of srcdoc
    assert all(hostile in (f["srcdoc"] or "") for f in page.iframes)


def test_hostile_file_name_is_escaped() -> None:
    text = frames.build_html(
        svg(""),
        '"><script>x</script>.svg',
        [0.0],
        duration=0.0,
        auto=True,
        loops=False,
        seam=False,
        width=100,
        height=50,
        cols=3,
        themes=["dark"],
    )
    assert sheet_of(text).scripts == 1
    assert "&quot;&gt;&lt;script&gt;x&lt;/script&gt;.svg" in text


def test_sheet_is_deterministic_lf_text(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="2s" repeatCount="indefinite"'))
    first = tmp_path / "a.png"
    second = tmp_path / "b.png"
    assert frames.main([str(src), "--out", str(first), "--html-only"]) == 0
    assert frames.main([str(src), "--out", str(second), "--html-only"]) == 0
    data = first.with_suffix(".html").read_bytes()
    assert data == second.with_suffix(".html").read_bytes()
    assert b"\r" not in data


def test_sheet_size_matches_the_layout() -> None:
    assert frames.sheet_size(6, 3, 360, 144, 1) == (1128, 388)
    assert frames.sheet_size(2, 3, 100, 50, 2) == (236, 236)


def test_frame_height_follows_the_viewbox(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    assert "iframe{display:block;border:0;width:300px;height:150px}" in html_only(
        tmp_path, src, "--width", "300"
    )


# browser discovery and exit codes


@pytest.mark.usefixtures("no_browser")
def test_no_browser_writes_html_and_exits_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    out = tmp_path / "sheet.png"
    assert frames.main([str(src), "--out", str(out)]) == 3
    assert (tmp_path / "sheet.html").is_file()
    assert not out.exists()
    assert "no Chrome, Edge or Chromium found" in capsys.readouterr().err


@pytest.mark.usefixtures("no_browser")
def test_html_only_needs_no_browser(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    assert frames.main([str(src), "--out", str(tmp_path / "s.png"), "--html-only"]) == 0


@pytest.mark.usefixtures("no_browser")
def test_install_paths_are_searched_after_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "chrome"
    fake.write_bytes(b"")
    monkeypatch.setattr(frames, "install_paths", lambda: [tmp_path / "missing", fake])
    assert frames.find_browser() == str(fake)


def test_missing_browser_override_is_a_usage_error(tmp_path: Path) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    with pytest.raises(SystemExit) as exc:
        frames.main([str(src), "--browser", str(tmp_path / "no-such-browser")])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "args",
    [["--duration", "soon"], ["--duration", "0"], ["--times", "1,-2"], ["--frames", "0"]],
)
def test_bad_arguments_exit_2(tmp_path: Path, args: list[str]) -> None:
    src = write(tmp_path, anim('dur="1s"'))
    with pytest.raises(SystemExit) as exc:
        frames.main([str(src), "--html-only", "--out", str(tmp_path / "s.png"), *args])
    assert exc.value.code == 2


def test_malformed_svg_exits_1(tmp_path: Path) -> None:
    src = tmp_path / "bad.svg"
    src.write_text("<svg", encoding="utf-8")
    assert frames.main([str(src), "--html-only", "--out", str(tmp_path / "s.png")]) == 1


# a real render


def read_png(path: Path) -> tuple[int, int, list[bytes]]:
    """Decode an 8-bit, non-interlaced RGB or RGBA PNG into RGB rows (stdlib only)."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat = 8, b""
    width = height = channels = 0
    while pos < len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind, body = data[pos + 4 : pos + 8], data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height = int.from_bytes(body[:4], "big"), int.from_bytes(body[4:8], "big")
            assert body[8] == 8 and body[12] == 0
            channels = {2: 3, 6: 4}[body[9]]
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw, stride = zlib.decompress(idat), width * channels
    rows, prev = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        rows.append(bytes(line[j] for j in range(stride) if j % channels < 3))
    return width, height, rows


def rgb(rows: list[bytes], x: int, y: int) -> tuple[int, ...]:
    return tuple(rows[y][x * 3 : x * 3 + 3])


@pytest.mark.skipif(frames.find_browser() is None, reason="no Chrome, Edge or Chromium here")
def test_real_browser_shows_smil_and_css_at_each_time(tmp_path: Path) -> None:
    body = (
        css(
            ".c{animation:c 2s steps(1) infinite}@keyframes c{50%{fill:#00ff00}}"
            "@media (prefers-reduced-motion: reduce){.c{animation:none}}"
        )
        + '<rect width="100" height="100" fill="#ff0000"><animate attributeName="fill" '
        'values="#ff0000;#0000ff" calcMode="discrete" dur="2s" repeatCount="indefinite"/></rect>'
        + '<rect class="c" x="100" width="100" height="100" fill="#000000"/>'
    )
    src = write(tmp_path, body)
    out = tmp_path / "sheet.png"
    assert frames.main([str(src), "--out", str(out), "--times", "0,1.5", "--width", "200"]) == 0
    width, height, rows = read_png(out)
    assert (width, height) == frames.sheet_size(2, 3, 200, 100, 1)
    top = frames.PAD + frames.HEAD + frames.CAP + 50
    cells = [frames.PAD + i * (200 + frames.GAP) for i in range(2)]
    smil = [rgb(rows, x + 50, top) for x in cells]
    style = [rgb(rows, x + 150, top) for x in cells]
    assert smil == [(255, 0, 0), (0, 0, 255)]
    assert style == [(0, 0, 0), (0, 255, 0)]  # motion shows even if the OS asks for less
