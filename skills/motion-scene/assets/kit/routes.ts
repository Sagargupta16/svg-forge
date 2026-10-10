import { pctX, pctY } from "./tokens";
import type { Pt } from "./tokens";
import type { Keys } from "./timing";

/*
 * Arc-length routes for things in flight. A route is a chain of cubics with
 * one parameter s from 0 to 1 over its whole length, so a packet moving
 * from s 0.2 to 0.6 covers the same distance per second on curves and
 * straights. Keyframes come from stops: [cycle fraction, route fraction].
 */

export type Cubic = readonly [Pt, Pt, Pt, Pt];

const lerp = (a: Pt, b: Pt, f: number): Pt => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];

/* S between two ports, horizontal tangents at both ends. */
export const sCurve = (a: Pt, b: Pt): Cubic => {
  const k = (b[0] - a[0]) / 2;
  return [a, [a[0] + k, a[1]], [b[0] - k, b[1]], b];
};

/* Straight run as a cubic, so routes treat lines and curves alike. */
export const line = (a: Pt, b: Pt): Cubic => [a, lerp(a, b, 1 / 3), lerp(a, b, 2 / 3), b];

const round2 = (v: number) => Math.round(v * 100) / 100;
const fmt = ([x, y]: Pt) => `${round2(x)},${round2(y)}`;

export const curveD = ([a, c1, c2, b]: Cubic) => `M${fmt(a)}C${fmt(c1)} ${fmt(c2)} ${fmt(b)}`;

const bezier = ([a, c1, c2, b]: Cubic, t: number): Pt => {
  const u = 1 - t;
  const w = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t] as const;
  return [
    w[0] * a[0] + w[1] * c1[0] + w[2] * c2[0] + w[3] * b[0],
    w[0] * a[1] + w[1] * c1[1] + w[2] * c2[1] + w[3] * b[1],
  ];
};

const TABLE = 48;

/* Arc-length table for one cubic: its length and a point-at-fraction lookup. */
const measure = (c: Cubic) => {
  const pts = Array.from({ length: TABLE + 1 }, (_, i) => bezier(c, i / TABLE));
  const acc = [0];
  for (let i = 1; i <= TABLE; i++) {
    const [x0, y0] = pts[i - 1] ?? c[0];
    const [x1, y1] = pts[i] ?? c[3];
    acc.push((acc[i - 1] ?? 0) + Math.hypot(x1 - x0, y1 - y0));
  }
  const length = acc[TABLE] ?? 0;
  const at = (f: number): Pt => {
    const target = f * length;
    let i = 1;
    while (i < TABLE && (acc[i] ?? 0) < target) i++;
    const lo = acc[i - 1] ?? 0;
    const span = (acc[i] ?? lo) - lo || 1;
    return lerp(pts[i - 1] ?? c[0], pts[i] ?? c[3], (target - lo) / span);
  };
  return { length, at };
};

export interface Route {
  d: string;
  /* route fraction where each segment ends; the last is 1 */
  ends: number[];
  at: (s: number) => Pt;
}

export const route = (first: Cubic, ...rest: Cubic[]): Route => {
  const segs = [first, ...rest];
  const parts = segs.map(measure);
  const total = parts.reduce((sum, p) => sum + p.length, 0);
  const ends: number[] = [];
  let run = 0;
  for (const p of parts) {
    run += p.length;
    ends.push(run / total);
  }
  const at = (s: number): Pt => {
    /* float drift past the last end means the last segment */
    let i = ends.findIndex((end) => s <= end);
    if (i === -1) i = ends.length - 1;
    const start = i === 0 ? 0 : (ends[i - 1] ?? 0);
    const part = parts[i] ?? parts[0];
    return part ? part.at((s - start) / ((ends[i] ?? 1) - start || 1)) : first[0];
  };
  const tail = rest.map(([, c1, c2, b]) => `C${fmt(c1)} ${fmt(c2)} ${fmt(b)}`).join("");
  return { d: curveD(first) + tail, ends, at };
};

/* [cycle fraction, route fraction]; equal fractions on consecutive stops hold. */
export type Stop = readonly [t: number, s: number];
export type Stops = readonly [Stop, ...Stop[]];

interface Sample {
  t: number;
  s: number;
}

const SAMPLES = 6;
const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2);

/* Ease between stops in route fraction, sampled densely enough that linear
   segments between samples follow the curve. */
const sampleStops = (first: Stop, rest: readonly Stop[]): Sample[] => {
  const out: Sample[] = [{ t: first[0], s: first[1] }];
  let [t0, s0] = first;
  for (const [t1, s1] of rest) {
    const n = s0 === s1 ? 1 : SAMPLES;
    for (let j = 1; j <= n; j++) {
      out.push({ t: t0 + ((t1 - t0) * j) / n, s: s0 + (s1 - s0) * easeInOut(j / n) });
    }
    [t0, s0] = [t1, s1];
  }
  return out;
};

/* When a move from stop a to stop b passes route fraction s. */
export const passAt = ([t0, s0]: Stop, [t1, s1]: Stop, s: number): number => {
  const goal = (s - s0) / (s1 - s0);
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 24; i++) {
    const mid = (lo + hi) / 2;
    if (easeInOut(mid) < goal) lo = mid;
    else hi = mid;
  }
  return t0 + ((t1 - t0) * (lo + hi)) / 2;
};

/* Fade length as a cycle fraction, before the first stop and after the last. */
export const FADE = 0.025;

const before = (t: number) => Math.max(0, t - FADE);
const after = (t: number) => Math.min(1, t + FADE);

const place = (r: Route, s: number) => {
  const [x, y] = r.at(s);
  return `translate(${pctX(x)}, ${pctY(y)})`;
};

/*
 * Keyframes for a fixed px packet riding a route, as transform strings so
 * the browser animates them off the main thread. It fades in on its first
 * stop, travels and holds through the rest, fades out after the last, then
 * slides home while hidden, so the loop closes without a visible jump.
 */
export const ride = (r: Route, [first, ...rest]: Stops): Keys => {
  const path = sampleStops(first, rest);
  const last = path.at(-1) ?? { t: first[0], s: first[1] };
  const frames = [
    { t: 0, s: first[1], o: 0 },
    { t: before(first[0]), s: first[1], o: 0 },
    ...path.map((p) => ({ ...p, o: 1 })),
    { t: after(last.t), s: last.s, o: 0 },
    { t: 1, s: first[1], o: 0 },
  ];
  return {
    times: frames.map((f) => f.t),
    transform: frames.map((f) => place(r, f.s)),
    opacity: frames.map((f) => f.o),
    ease: "linear",
  };
};

/*
 * Short trail behind the same packet: a dash of at most `len` that grows
 * from each departure, follows the head either way and collapses into it on
 * every hold. Draw it with Trace on the route's `d`.
 */
export const comet = ([first, ...rest]: Stops, len = 0.1): Keys => {
  const path = sampleStops(first, rest);
  let from = first[1];
  let prev = first[1];
  const dash = path.map((p) => {
    if (p.s === prev) from = p.s;
    prev = p.s;
    const run = Math.min(len, Math.abs(p.s - from));
    return { t: p.t, length: run, offset: p.s > from ? p.s - run : p.s };
  });
  const last = path.at(-1) ?? { t: first[0], s: first[1] };
  const frames = [
    { t: 0, length: 0, offset: first[1], o: 0 },
    ...dash.map((d) => ({ ...d, o: 1 })),
    { t: after(last.t), length: 0, offset: last.s, o: 0 },
    { t: 1, length: 0, offset: first[1], o: 0 },
  ];
  return {
    times: frames.map((f) => f.t),
    pathLength: frames.map((f) => f.length),
    pathOffset: frames.map((f) => f.offset),
    opacity: frames.map((f) => f.o),
    ease: "linear",
  };
};

/* The route lights up behind the packet and holds until `hold`, then fades
   and resets while hidden. */
export const lit = ([first, ...rest]: Stops, hold: number): Keys => {
  const path = sampleStops(first, rest);
  let reach = 0;
  const grown = path.map((p) => {
    reach = Math.max(reach, p.s);
    return { t: p.t, length: reach };
  });
  const frames = [
    { t: 0, length: 0, o: 0 },
    ...grown.map((g) => ({ ...g, o: 1 })),
    { t: hold, length: reach, o: 1 },
    { t: after(hold), length: reach, o: 0 },
    { t: 1, length: 0, o: 0 },
  ];
  return {
    times: frames.map((f) => f.t),
    pathLength: frames.map((f) => f.length),
    opacity: frames.map((f) => f.o),
    ease: "linear",
  };
};
