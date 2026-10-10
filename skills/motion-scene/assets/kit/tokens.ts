import type { CSSProperties } from "react";

/*
 * Stage geometry and palette for motion scenes.
 *
 * A scene draws in one stage of STAGE_W x STAGE_H units at the slot's own
 * ratio (16:10 here). SVG uses that viewBox uniformly; HTML packets, pips and
 * labels sit on the same stage points in percent with fixed px sizes, so the
 * mechanism still reads when the slot is only 160 px wide. If your slot has
 * another ratio, change both numbers together.
 */

export const STAGE_W = 320;
export const STAGE_H = 200;
export const VIEWBOX = `0 0 ${STAGE_W} ${STAGE_H}`;

export type Pt = readonly [x: number, y: number];
export type Box = readonly [x: number, y: number, w: number, h: number];

const round2 = (v: number) => Math.round(v * 100) / 100;

/* Stage units to percent of the stage box. */
export const pctX = (x: number) => `${round2((x / STAGE_W) * 100)}%`;
export const pctY = (y: number) => `${round2((y / STAGE_H) * 100)}%`;
/* A stage point as a CSS position, e.g. for gradient centres. */
export const pctAt = ([x, y]: Pt) => `${pctX(x)} ${pctY(y)}`;

export const layer = { position: "absolute", inset: 0 } satisfies CSSProperties;

/* Fixed px dot centred on a stage point. */
export const dotAt = ([x, y]: Pt, size: number, color: string) =>
  ({
    position: "absolute",
    left: pctX(x),
    top: pctY(y),
    width: size,
    height: size,
    marginLeft: -size / 2,
    marginTop: -size / 2,
    borderRadius: "50%",
    background: color,
  }) satisfies CSSProperties;

/* ---------- color ---------- */

const byte = (v: number) => Math.round(v).toString(16).padStart(2, "0");
const channels = (hex: string) => [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16));

/* 6 digit hex plus alpha as 8 digit hex; valid in CSS and SVG attributes. */
export const alpha = (hex: string, a: number) => hex.slice(0, 7) + byte(a * 255);

/* Opaque blend of two 6 digit hex colors: f = 0 is a, f = 1 is b. */
export const mix = (a: string, b: string, f: number) => {
  const cb = channels(b);
  const out = channels(a).map((v, i) => byte(v + ((cb[i] ?? v) - v) * f));
  return `#${out.join("")}`;
};

/* Alpha ladder steps in percent: 3 fills, 10 borders, 55 labels, 88 lit text. */
export const STEPS = [3, 5, 10, 16, 25, 40, 55, 70, 88] as const;
export type Step = (typeof STEPS)[number];
export type Ladder = Readonly<Record<Step, string>>;

const ladder = (hex: string) =>
  Object.fromEntries(STEPS.map((s) => [s, alpha(hex, s / 100)])) as Ladder;

export type Scheme = "dark" | "light";

const SCHEMES: Record<Scheme, { ink: string; neutral: string }> = {
  dark: { ink: "#0c1014", neutral: "#ffffff" },
  light: { ink: "#f6f8fa", neutral: "#0c1014" },
};

export const MONO = 'ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace';

export interface PaletteInput {
  /* the one accent hue, 6 digit hex */
  tint: string;
  scheme?: Scheme;
  /* status only: ok for live or success, warn for warnings */
  ok?: string;
  warn?: string;
  /* canvas under everything, 6 digit hex */
  ink?: string;
  /* label font stack */
  mono?: string;
}

export interface Palette {
  tint: string;
  ok: string;
  warn: string;
  ink: string;
  neutral: string;
  mono: string;
  /* root background: the ink with a faint lift of tint at the top left */
  base: string;
  /* opaque panel fill, for panels that wires pass under */
  solid: string;
  /* tint and neutral alpha ladders, e.g. t[25], n[10] */
  t: Ladder;
  n: Ladder;
}

/* Tint plus neutrals: every color in a scene comes from here. */
export const createPalette = ({
  tint,
  scheme = "dark",
  ok = "#22c55e",
  warn = "#f59e0b",
  ink = SCHEMES[scheme].ink,
  mono = MONO,
}: PaletteInput): Palette => {
  const { neutral } = SCHEMES[scheme];
  const lift = mix(ink, tint, 0.07);
  return {
    tint,
    ok,
    warn,
    ink,
    neutral,
    mono,
    base: `linear-gradient(160deg, ${lift} 0%, ${ink} 60%)`,
    solid: mix(ink, neutral, 0.03),
    t: ladder(tint),
    n: ladder(neutral),
  };
};

/* ---------- back layer textures ---------- */

export type Texture = "dots" | "grid" | "rails" | "columns" | "none";

export interface Pattern {
  /* repeat size in px; a drift moves one cell per loop */
  cell: number;
  style: { backgroundImage: string; backgroundSize: string };
}

const pattern = (cell: number, image: string, size?: string): Pattern => ({
  cell,
  style: { backgroundImage: image, backgroundSize: size ?? `${cell}px ${cell}px` },
});

const rows = (c: string) => `linear-gradient(${c} 1px, transparent 1px)`;
const cols = (c: string) => `linear-gradient(90deg, ${c} 1px, transparent 1px)`;

const PATTERNS: Record<Texture, (c: string) => Pattern> = {
  dots: (c) => pattern(16, `radial-gradient(${c} 1px, transparent 1.4px)`),
  grid: (c) => pattern(20, `${rows(c)}, ${cols(c)}`),
  rails: (c) => pattern(18, rows(c), "100% 18px"),
  columns: (c) => pattern(22, cols(c), "22px 100%"),
  none: () => pattern(0, "none", "auto"),
};

/* Static pattern at 4 to 7 percent neutral, px-sized cells. */
export const texture = (kind: Texture, p: Palette): Pattern =>
  PATTERNS[kind](alpha(p.neutral, kind === "dots" ? 0.07 : 0.045));
