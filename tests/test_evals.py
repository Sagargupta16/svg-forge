"""evals/: the `claude plugin eval` suite is well formed and its deterministic graders discriminate.

Offline only. Each case is a directory under evals/ holding prompt.md (frontmatter plus the
prompt), optional case.yaml (scaffold) and graders/*.md. Regex graders run as JavaScript
regexes inside `claude plugin eval`; here they run through Python `re`, so patterns must stay
in the syntax both engines read the same way (checked below).
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Any

import pytest

import forge
import validate_svg

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
FIXTURES = EVALS / "fixtures"
SKILLS = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))

# Documented case and grader fields (code.claude.com/docs/en/plugin-evals); unknown keys fail.
PROMPT_KEYS = {
    "schema_version",
    "name",
    "description",
    "tags",
    "plugins",
    "runs",
    "expected_outcome",
    "model",
    "max_turns",
    "timeout_seconds",
    "allowed_tools",
    "append_system_prompt",
    "env",
}
CASE_KEYS = PROMPT_KEYS - {"model", "max_turns", "timeout_seconds", "allowed_tools", "env"} | {
    "execution",
    "context",
    "graders",
}
CONTEXT_KEYS = {"scaffold_script", "history_file", "add_dirs"}
GRADER_KEYS = {
    "regex": {"pattern", "flags", "match", "target"},
    "tool_used": {"tool", "input_match", "min", "max"},
    "tool_order": {"before", "after"},
    "file_exists": {"path", "exists"},
    "llm": {"criteria", "focus"},
    "baseline": {"baseline_file", "criteria"},
}
TARGETS = {"last_message", "trace", "files", "mock_calls"}
TOOLS = {
    "Read",
    "Glob",
    "Grep",
    "NotebookRead",
    "Skill",
    "AskUserQuestion",
    "Agent",
    "TodoWrite",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskUpdate",
    "TaskStop",
    "Bash",
    "Write",
    "Edit",
    "WebFetch",
    "WebSearch",
}
# Python and JavaScript read these differently, or one of them lacks them.
NOT_PORTABLE = re.compile(r"\(\?P|\(\?<[=!]|\(\?<\w|\(\?>|\(\?[aiLmsux-]+[:)]|\\[AZzpP]|(?<!\\)\$")
# Shared SVG graders: same pattern in every case, deterministic stand-ins for validate_svg.py.
SHARED = ("svg-root", "accessible-name", "self-contained", "animates", "under-50kb", "no-dashes")


# ---------------------------------------------------------------- loading


def scalar(raw: str, where: str) -> Any:
    """One YAML scalar from the subset the suite uses."""
    if re.fullmatch(r"'(?:[^']|'')*'", raw):
        return raw[1:-1].replace("''", "'")
    if raw.startswith('"'):
        return json.loads(raw)
    if raw.startswith("[") and raw.endswith("]"):
        items = [item.strip() for item in raw[1:-1].split(",") if item.strip()]
        if not all(re.fullmatch(r"[\w./*-]+", item) for item in items):
            raise ValueError(f"{where}: flow list items must be plain words: {raw}")
        return items
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return float(raw) if "." in raw else int(raw)
    if raw in ("true", "false"):
        return raw == "true"
    if re.match(r"[\[\]{}!&*?|>'\"%@`#,]", raw) or ": " in raw or " #" in raw or raw[-1] == ":":
        raise ValueError(f"{where}: quote this value, YAML cannot read it plain: {raw}")
    return raw


def mini_yaml(text: str, where: str) -> dict[str, Any]:
    """key: scalar lines, flow lists of words, and one level of nested mapping."""
    out: dict[str, Any] = {}
    nested: dict[str, Any] | None = None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.fullmatch(r"( *)([\w-]+):(?: +(.*))?", line)
        if not m:
            raise ValueError(f"{where}:{n}: expected 'key: value', got {line!r}")
        indent, key, raw = m.group(1), m.group(2), (m.group(3) or "").strip()
        scope = out if not indent else nested
        if scope is None or (indent and not raw):
            raise ValueError(f"{where}:{n}: unexpected indent or nesting: {line!r}")
        if key in scope:
            raise ValueError(f"{where}:{n}: duplicate key {key!r}")
        if indent:
            scope[key] = scalar(raw, f"{where}:{n}")
        elif raw:
            scope[key] = scalar(raw, f"{where}:{n}")
            nested = None
        else:
            nested = scope[key] = {}
    return out


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    rel = path.relative_to(ROOT).as_posix()
    m = re.match(r"---\n(.*?)\n---\n?(.*)\Z", read(path), re.S)
    if not m:
        raise ValueError(f"{rel}: needs --- frontmatter ---")
    return mini_yaml(m.group(1), rel), m.group(2).strip()


def case_dirs() -> list[Path]:
    found = {p.parent for name in ("prompt.md", "case.yaml") for p in EVALS.rglob(name)}
    return sorted(d for d in found if "results" not in d.relative_to(EVALS).parts)


CASE_DIRS = case_dirs()
CASE_IDS = [d.relative_to(EVALS).as_posix() for d in CASE_DIRS]


@functools.cache
def load(case: str) -> dict[str, Any]:
    d = EVALS / case
    meta, prompt = frontmatter(d / "prompt.md") if (d / "prompt.md").exists() else ({}, "")
    yml = (
        mini_yaml(read(d / "case.yaml"), f"{case}/case.yaml") if (d / "case.yaml").exists() else {}
    )
    graders = {p.stem: frontmatter(p) for p in sorted((d / "graders").glob("*.md"))}
    prompt = prompt or str(yml.get("execution", {}).get("prompt", ""))
    return {"meta": meta, "yaml": yml, "prompt": prompt, "graders": graders}


def all_graders() -> list[tuple[str, str]]:
    return [(c, p.stem) for c in CASE_IDS for p in sorted((EVALS / c / "graders").glob("*.md"))]


GRADER_IDS = all_graders()


def grader(case: str, name: str) -> dict[str, Any]:
    return load(case)["graders"][name][0]


def file_target(g: dict[str, Any]) -> str | None:
    target = g.get("target") if g.get("type") == "regex" else None
    return target["path"] if isinstance(target, dict) else None


def fixture_of(case: str) -> Path | None:
    script = load(case)["yaml"].get("context", {}).get("scaffold_script")
    if not script:
        return None
    m = re.search(r"fixtures/([\w.-]+)", read(EVALS / case / script))
    return FIXTURES / m.group(1) if m else None


def staged(case: str) -> dict[str, str]:
    """Files the case's scaffold copies into the run workspace."""
    src = fixture_of(case)
    if src is None:
        return {}
    return {p.relative_to(src).as_posix(): read(p) for p in sorted(src.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- grading


def py_regex(pattern: str, flags: str = "") -> re.Pattern[str]:
    bits = {"i": re.I, "m": re.M, "s": re.S}
    mode = 0
    for flag in flags:
        mode |= bits[flag]
    return re.compile(pattern, mode)


def passes(g: dict[str, Any], text: str) -> bool:
    """A regex grader's verdict on text, the way `claude plugin eval` scores it."""
    rx = py_regex(str(g["pattern"]), str(g.get("flags", "")))
    match = str(g.get("match", ""))
    if match == "not_contains":
        return rx.search(text) is None
    if match.startswith("count:"):
        return len(list(rx.finditer(text))) == int(match[6:])
    return rx.search(text) is not None


def shared(name: str) -> dict[str, Any]:
    case = next(c for c, g in GRADER_IDS if g == name)
    return grader(case, name)


# ---------------------------------------------------------------- suite structure


def test_suite_has_ten_to_fifteen_cases() -> None:
    assert 10 <= len(CASE_DIRS) <= 15, CASE_IDS


def test_case_names_are_unique() -> None:
    names = [load(c)["meta"].get("name") or load(c)["yaml"].get("name") or c for c in CASE_IDS]
    assert len(names) == len(set(names)), names


def test_no_case_hides_inside_fixtures() -> None:
    assert not [c for c in CASE_IDS if c.startswith("fixtures/")]


@pytest.mark.parametrize("case", CASE_IDS)
def test_case_has_a_prompt(case: str) -> None:
    assert len(load(case)["prompt"]) > 20


@pytest.mark.parametrize("case", CASE_IDS)
def test_case_has_a_grader(case: str) -> None:
    assert load(case)["graders"] or load(case)["yaml"].get("graders")


@pytest.mark.parametrize("case", CASE_IDS)
def test_prompt_frontmatter_uses_known_keys(case: str) -> None:
    assert set(load(case)["meta"]) <= PROMPT_KEYS


@pytest.mark.parametrize("case", CASE_IDS)
def test_run_limits_are_in_range(case: str) -> None:
    meta = load(case)["meta"]
    assert 1 <= meta.get("max_turns", 10) <= 200
    assert 1 <= meta.get("timeout_seconds", 300) <= 3600
    assert 1 <= meta.get("runs", 3) <= 50


@pytest.mark.parametrize("case", CASE_IDS)
def test_allowed_tools_are_known(case: str) -> None:
    tools = load(case)["meta"].get("allowed_tools", [])
    assert tools and set(tools) <= TOOLS


@pytest.mark.parametrize("case", [c for c in CASE_IDS if (EVALS / c / "case.yaml").exists()])
def test_case_yaml_is_valid(case: str) -> None:
    yml = load(case)["yaml"]
    assert yml["schema_version"] == "1.1"
    assert yml["name"] == case
    assert set(yml) <= CASE_KEYS
    assert set(yml.get("context", {})) <= CONTEXT_KEYS


@pytest.mark.parametrize("case", [c for c in CASE_IDS if load(c)["yaml"].get("context")])
def test_scaffold_stages_an_existing_fixture(case: str) -> None:
    script = EVALS / case / load(case)["yaml"]["context"]["scaffold_script"]
    src = fixture_of(case)
    assert script.is_file() and read(script).startswith("#!/usr/bin/env bash\n")
    assert src is not None and src.is_dir() and staged(case)


@pytest.mark.parametrize(("case", "name"), GRADER_IDS)
def test_grader_frontmatter_is_valid(case: str, name: str) -> None:
    g = grader(case, name)
    kind = g.get("type")
    assert kind in GRADER_KEYS
    assert set(g) <= {"type", "weight", "arm"} | GRADER_KEYS[kind]
    assert g.get("arm") in (None, "with-only", "both")
    assert float(g.get("weight", 1)) > 0
    required = {"regex": "pattern", "tool_used": "tool", "file_exists": "path"}.get(kind)
    assert required is None or g.get(required) not in (None, "")


@pytest.mark.parametrize(("case", "name"), GRADER_IDS)
def test_regexes_are_portable_and_compile(case: str, name: str) -> None:
    g = grader(case, name)
    for key in ("pattern", "input_match"):
        if key in g:
            assert not NOT_PORTABLE.search(str(g[key])), f"{key} uses non-portable syntax"
            py_regex(str(g[key]), str(g.get("flags", "")))
    assert set(str(g.get("flags", ""))) <= {"i", "m", "s"}
    assert str(g.get("match", "not_contains")) == "not_contains" or re.fullmatch(
        r"count:\d+", str(g["match"])
    )


@pytest.mark.parametrize(("case", "name"), GRADER_IDS)
def test_grader_target_is_known(case: str, name: str) -> None:
    g = grader(case, name)
    target = g.get("target", g.get("focus", "last_message"))
    if isinstance(target, dict):
        assert target.get("source") == "file" and set(target) == {"source", "path"}
        assert ".." not in target["path"] and not target["path"].startswith("/")
    else:
        assert target in TARGETS


def fixed_path(g: dict[str, Any]) -> str | None:
    path = file_target(g) or (g.get("path") if g.get("type") == "file_exists" else None)
    return None if path is None or "*" in path else str(path)


@pytest.mark.parametrize(("case", "name"), [i for i in GRADER_IDS if fixed_path(grader(*i))])
def test_file_graders_name_a_path_the_case_provides(case: str, name: str) -> None:
    path = fixed_path(grader(case, name)) or ""
    assert path in load(case)["prompt"] or path in staged(case)


@pytest.mark.parametrize(("case", "name"), [i for i in GRADER_IDS if grader(*i)["type"] == "llm"])
def test_llm_rubrics_state_pass_and_fail(case: str, name: str) -> None:
    body = load(case)["graders"][name][1]
    assert "PASS if" in body and "FAIL if" in body


@pytest.mark.parametrize(
    ("case", "name"), [i for i in GRADER_IDS if grader(*i).get("tool") == "Skill"]
)
def test_skill_graders_name_a_real_skill(case: str, name: str) -> None:
    named = re.findall(r"[a-z]+(?:-[a-z]+)+", str(grader(case, name).get("input_match", "")))
    assert named and set(named) <= set(SKILLS)


@pytest.mark.parametrize("skill", SKILLS)
def test_every_skill_has_a_case_that_expects_it(skill: str) -> None:
    expects = [
        c
        for c, n in GRADER_IDS
        if grader(c, n).get("tool") == "Skill"
        and grader(c, n).get("max") is None
        and skill in str(grader(c, n).get("input_match", ""))
    ]
    assert expects


def test_results_dir_is_gitignored() -> None:
    assert "results/" in read(EVALS / ".gitignore").splitlines()


@pytest.mark.parametrize("name", SHARED)
def test_shared_svg_grader_is_identical_in_every_case(name: str) -> None:
    copies = {
        (str(g["pattern"]), g.get("flags"), g.get("match"))
        for c, n in GRADER_IDS
        if n.removeprefix("dark-").removeprefix("light-") == name
        for g in [grader(c, n)]
    }
    assert len(copies) == 1, copies


# ---------------------------------------------------------------- fixtures


def test_broken_card_trips_exactly_the_planted_rules() -> None:
    report = validate_svg.validate_file(FIXTURES / "audit-card" / "card.svg")
    found = {f.rule: f.severity for f in report.findings}
    assert found == {"SV008": "error", "SV010": "error", "SV018": "warn", "SV019": "warn"}


def test_static_logo_is_valid_and_has_no_animation() -> None:
    report = validate_svg.validate_file(FIXTURES / "static-logo" / "logo.svg")
    assert report.findings == []
    assert report.stats["smil"] == 0 and report.stats["keyframes"] == 0


def test_audit_fixture_readme_shows_the_card_as_an_image() -> None:
    assert '<img src="card.svg"' in read(FIXTURES / "audit-card" / "README.md")


def test_react_fixture_has_its_own_motion_setting() -> None:
    assert '"full" | "reduced"' in read(FIXTURES / "react-app" / "src" / "settings" / "motion.ts")


# ---------------------------------------------------------------- graders vs known answers

SHIPPED_SVGS = sorted((ROOT / "examples").glob("*.svg")) + sorted(
    (ROOT / "skills" / "animated-svg" / "assets" / "templates").glob("*.svg")
)
CARD = read(FIXTURES / "audit-card" / "card.svg")
LOGO = read(FIXTURES / "static-logo" / "logo.svg")
FIXED_CARD = (
    CARD.replace(
        'role="img">',
        'role="img" aria-labelledby="card-title">\n'
        '<title id="card-title">Project stats: 1,204 commits, 87% test coverage</title>',
    )
    .replace(
        '<image href="https://img.shields.io/badge/build-passing-22c55e" x="352" y="18" '
        'width="104" height="20"/>',
        '<rect x="352" y="18" width="104" height="20" rx="10" fill="#22c55e"/>',
    )
    .replace('calcmod="spline"', 'calcMode="spline"')
    .replace(' vector-effect="non-scaling-stroke"', "")
)
ANIMATED_LOGO = LOGO.replace(
    '<circle cx="32" cy="32" r="4" fill="#60a5fa"/>',
    '<circle cx="32" cy="32" r="4" fill="#60a5fa"><animate attributeName="r" values="4;6;4" '
    'keyTimes="0;0.5;1" dur="3s" repeatCount="indefinite"/></circle>',
)
SCENE_KIT = read(ROOT / "skills" / "motion-scene" / "assets" / "kit" / "ExampleScene.tsx")
HERO_TSX = """import { motion } from "motion/react";

const SERVICES = ["AUTH", "BILLING", "SEARCH"] as const;
const EASE = ["easeOut", "easeIn"];

type Props = Readonly<{ tint: string; frozen?: boolean }>;

export default function GatewayHero({ tint, frozen = false }: Props) {
  return (
    <div aria-hidden="true">
      {SERVICES.map((name, i) => (
        <motion.span
          key={name}
          animate={frozen ? undefined : { x: [0, 120], opacity: [0, 1, 0] }}
          transition={{ duration: 4, delay: i * 0.4, repeat: Infinity, ease: EASE }}
          style={{ color: tint }}
        >
          {name}
        </motion.span>
      ))}
    </div>
  );
}
"""
TILES = [
    {"label": "commits", "value": "1,284"},
    {"label": "pull requests", "value": "312"},
    {"label": "stars", "value": "4.9k"},
    {"label": "test coverage", "value": "98%"},
]
PIPELINE = {
    "title": "CI/CD pipeline",
    "nodes": ["push", "build", "test", "deploy"],
    "edges": [["push", "build"], ["build", "test"], ["test", "deploy"]],
}


@functools.cache
def answers(case: str) -> dict[str, str]:
    """A known-good result for each case: the staged workspace plus what a good run writes."""
    made = {
        "animated-svg-readme-header": {
            "assets/header.svg": forge.render("hero", title="tidewatch")
        },
        "animated-svg-dots-loader": {"loading.svg": forge.render("loader", variant="dots")},
        "animated-svg-pipeline-diagram": {"docs/pipeline.svg": forge.render("flow", data=PIPELINE)},
        "animated-svg-stat-tiles": {"assets/stats.svg": forge.render("tiles", data=TILES)},
        "animated-svg-dark-light-pair": {
            f"assets/banner-{t}.svg": forge.render("hero", theme=t, title="orbitdb-lite")
            for t in ("dark", "light")
        },
        "animated-svg-animate-static": {"logo-animated.svg": ANIMATED_LOGO},
        "svg-audit-fix": {"card.svg": FIXED_CARD},
        "motion-scene-cache-cover": {"src/scenes/CacheScene.tsx": SCENE_KIT},
        "routing-readme-badge": {
            "badge.svg": forge.render("badge", data={"label": "build", "value": "passing"})
        },
        "routing-react-hero": {"app/components/GatewayHero.tsx": HERO_TSX},
    }
    return staged(case) | made.get(case, {})


FILE_GRADERS = [i for i in GRADER_IDS if file_target(grader(*i))]


@pytest.mark.parametrize("svg", SHIPPED_SVGS, ids=lambda p: p.name)
@pytest.mark.parametrize("name", SHARED)
def test_shared_svg_grader_passes_every_shipped_svg(name: str, svg: Path) -> None:
    assert passes(shared(name), read(svg))


@pytest.mark.parametrize(("case", "name"), FILE_GRADERS)
def test_file_grader_passes_a_known_good_answer(case: str, name: str) -> None:
    g = grader(case, name)
    assert passes(g, answers(case)[file_target(g) or ""])


@pytest.mark.parametrize(
    "case", sorted({c for c, _ in FILE_GRADERS if any(p.endswith(".svg") for p in answers(c))})
)
def test_known_good_svg_answers_pass_the_validator(case: str) -> None:
    for path, text in answers(case).items():
        if path.endswith(".svg") and not (case == "svg-audit-report-only" and path == "card.svg"):
            report = validate_svg.validate_text(text.encode("utf-8"), path)
            assert report.errors == 0, (path, report.findings)


def test_fixed_card_clears_the_warnings_too() -> None:
    assert validate_svg.validate_text(FIXED_CARD.encode("utf-8")).findings == []


DASH = chr(0x2014)
BAD_SVG = {
    "svg-root": '<svg viewBox="0 0 10 10" role="img"><title>x</title></svg>',
    "accessible-name": CARD,
    "self-contained": CARD,
    "animates": LOGO,
    "under-50kb": FIXED_CARD.replace("</svg>", "<!--" + "x" * 52000 + "--></svg>"),
    "no-dashes": LOGO.replace("Hexwire logo", f"Hexwire {DASH} logo"),
}
HOSTILE = {
    "script": "<svg><script>alert(1)</script></svg>",
    "handler": '<svg><rect onclick="x()"/></svg>',
    "remote font": "<svg><style>@font-face{src:url(https://fonts.example/a.woff2)}</style></svg>",
    "import": "<svg><style>@import 'theme.css';</style></svg>",
    "quoted url": "<svg><rect fill=\"url('https://example.com/p.svg#g')\"/></svg>",
    "xlink": '<svg><use xlink:href="sprite.svg#icon"/></svg>',
    "foreignObject": "<svg><foreignObject/></svg>",
}


@pytest.mark.parametrize("name", SHARED)
def test_shared_svg_grader_rejects_a_bad_file(name: str) -> None:
    assert not passes(shared(name), BAD_SVG[name])


@pytest.mark.parametrize("text", list(HOSTILE.values()), ids=list(HOSTILE))
def test_self_contained_rejects_each_blocked_construct(text: str) -> None:
    assert not passes(shared("self-contained"), text)


def test_self_contained_allows_local_and_data_references() -> None:
    ok = (
        '<svg><rect fill="url(#g)"/><rect fill="url(\'#g\')"/><use href="#a"/>'
        '<image href="data:image/png;base64,AAAA"/></svg>'
    )
    assert passes(shared("self-contained"), ok)


# (case, grader) -> a wrong answer it must reject
BAD_ANSWERS: dict[tuple[str, str], str] = {
    ("animated-svg-readme-header", "names-the-tool"): forge.render("hero", title="logwatch"),
    ("animated-svg-dots-loader", "loops"): forge.render("loader", variant="dots", loop=False),
    ("animated-svg-dots-loader", "three-dots"): '<svg><circle r="4"/><circle r="4"/></svg>',
    ("animated-svg-dots-loader", "under-10kb"): "<svg>" + " " * 10240 + "</svg>",
    ("animated-svg-pipeline-diagram", "four-stages"): forge.render(
        "flow", data={"nodes": ["push", "build", "deploy"], "edges": [["push", "build"]]}
    ),
    ("animated-svg-pipeline-diagram", "something-travels"): (
        '<svg><text>push</text><text>build</text><animate attributeName="opacity"/></svg>'
    ),
    ("animated-svg-stat-tiles", "all-values"): forge.render(
        "tiles", data=[{**t, "value": t["value"].replace(",", "")} for t in TILES]
    ),
    ("animated-svg-stat-tiles", "desc-carries-numbers"): forge.render(
        "tiles", data=TILES, desc="Project stats"
    ),
    ("animated-svg-dark-light-pair", "dark-no-theme-query"): forge.render("hero").replace(
        "<style>", "<style>@media (prefers-color-scheme: light){svg{display:none}}"
    ),
    ("animated-svg-animate-static", "geometry-kept"): ANIMATED_LOGO.replace(
        "M32 8 L53 20 V44", "M32 6 L54 19 V45"
    ),
    ("animated-svg-animate-static", "original-untouched"): ANIMATED_LOGO,
    ("animated-svg-animate-static", "loops"): ANIMATED_LOGO.replace(
        ' repeatCount="indefinite"', ""
    ),
    ("svg-audit-report-only", "card-unchanged"): FIXED_CARD,
    ("svg-audit-fix", "no-typo-left"): CARD,
    ("svg-audit-fix", "splines-take-effect"): CARD,
    ("svg-audit-fix", "draw-not-cut-short"): CARD,
    ("svg-audit-fix", "content-kept"): FIXED_CARD.replace(">1,204<", "><"),
    ("svg-audit-fix", "animates"): re.sub(r"<animate\b[^>]*/>", "", FIXED_CARD),
    ("motion-scene-cache-cover", "uses-motion"): 'import { motion } from "framer-motion";',
    ("motion-scene-cache-cover", "decorative-root"): "<div><motion.div /></div>",
    ("motion-scene-cache-cover", "per-segment-ease"): (
        'transition={{ duration: 6, times: [0, 0.4, 1], ease: "easeInOut", repeat: Infinity }}'
    ),
    ("motion-scene-cache-cover", "transform-opacity-only"): "animate={{ width: [0, 40] }}",
    ("motion-scene-cache-cover", "follows-app-motion-setting"): "export default function S() {}",
    ("motion-scene-cache-cover", "no-os-motion-gate"): "const reduce = useReducedMotion();",
    ("motion-scene-cache-cover", "tint-prop"): "export default function S() {}",
    ("motion-scene-cache-cover", "mechanism-vocabulary"): "<Label>BARS</Label><Label>CHART</Label>",
    ("routing-readme-badge", "self-contained"): "<svg><script>alert(1)</script></svg>",
    ("routing-react-hero", "names-the-services"): HERO_TSX.replace('"SEARCH"', '"QUEUE"'),
    ("routing-react-hero", "uses-motion"): HERO_TSX.replace("motion/react", "framer-motion"),
    ("routing-react-hero", "decorative-root"): HERO_TSX.replace(' aria-hidden="true"', ""),
    ("animated-svg-dark-light-pair", "light-no-theme-query"): forge.render(
        "hero", theme="light"
    ).replace("<style>", "<style>@media (prefers-color-scheme: dark){svg{display:none}}"),
}


def test_every_file_grader_has_a_bad_answer() -> None:
    unshared = {
        i for i in FILE_GRADERS if i[1].removeprefix("dark-").removeprefix("light-") not in SHARED
    }
    assert unshared - set(BAD_ANSWERS) == set()


@pytest.mark.parametrize(("case", "name"), list(BAD_ANSWERS))
def test_file_grader_rejects_a_bad_answer(case: str, name: str) -> None:
    assert not passes(grader(case, name), BAD_ANSWERS[(case, name)])


@pytest.mark.parametrize(
    ("case", "name", "reply"),
    [
        (
            "animated-svg-readme-header",
            "readme-line",
            '<img src="assets/header.svg" alt="tidewatch: tails logs and flags anomalies">',
        ),
        ("animated-svg-readme-header", "readme-line", "![tidewatch](./assets/header.svg)"),
        (
            "animated-svg-stat-tiles",
            "alt-has-numbers",
            "![1,284 commits, 312 PRs](assets/stats.svg)",
        ),
        (
            "animated-svg-dark-light-pair",
            "picture-snippet",
            forge.picture("assets/banner-dark.svg", "assets/banner-light.svg", "orbitdb-lite"),
        ),
        (
            "svg-audit-report-only",
            "quotes-rule-ids",
            "| 1 | error | SV008 |\n| 2 | error | SV010 |\n"
            "| 3 | warn | SV018 |\n| 4 | warn | SV019 |",
        ),
        ("svg-audit-report-only", "finds-calcmode-typo", 'line 7: `calcmod="spline"` is a typo'),
        ("svg-audit-report-only", "finds-external-image", "The external badge image is blocked."),
        ("routing-no-trigger", "answers", "Use SVG: it is vector, so it scales crisply."),
    ],
)
def test_reply_grader_accepts_a_good_reply(case: str, name: str, reply: str) -> None:
    assert passes(grader(case, name), reply)


@pytest.mark.parametrize(
    ("case", "name", "reply"),
    [
        ("animated-svg-readme-header", "readme-line", "Paste <svg>...</svg> into the README."),
        ("animated-svg-stat-tiles", "alt-has-numbers", '<img src="assets/stats.svg" alt="Stats">'),
        (
            "animated-svg-dark-light-pair",
            "picture-snippet",
            '<img src="assets/banner-dark.svg" alt="orbitdb-lite">',
        ),
        ("svg-audit-report-only", "quotes-rule-ids", "SV008 and SV010 are errors."),
        ("svg-audit-report-only", "finds-calcmode-typo", 'calcMode="spline" is set correctly.'),
    ],
)
def test_reply_grader_rejects_a_bad_reply(case: str, name: str, reply: str) -> None:
    assert not passes(grader(case, name), reply)
