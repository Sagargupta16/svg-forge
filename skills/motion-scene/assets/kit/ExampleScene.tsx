import { useMemo, type CSSProperties } from "react";
import { Label, Packet, Panel, Pip, Shell, Trace, Wire, useScene } from "./primitives";
import { createPalette } from "./tokens";
import type { Box, Pt } from "./tokens";
import { PRESET, clock, shown } from "./timing";
import type { Keys } from "./timing";
import { comet, line, passAt, ride, route } from "./routes";
import type { Stop, Stops } from "./routes";
import { useFreezeAnimations } from "./useFreezeAnimations";
import { useNearViewport } from "./useNearViewport";

/*
 * Read-through cache, one 6 s loop on one clock.
 *   0.04  call 1 leaves CLIENT, misses at CACHE (warn pip), reaches DB
 *   0.21  DB works, the response rides back and fills the cache slot
 *   0.56  call 2 stops at CACHE: hit (ok pip), straight back to CLIENT
 *   0.90  the entry expires while the loop resets
 * 8 animated nodes, 3 labels, built only from the kit.
 */

const beat = clock(PRESET.medium);

const RAIL_Y = 100;
const RAIL_X0 = 70;
const RAIL_X1 = 250;
const CACHE_X = 160;

const CLIENT: Box = [26, 84, 44, 32];
const CACHE: Box = [128, 66, 64, 68];
const DB: Box = [RAIL_X1, 72, 44, 56];
const SLOT: Box = [140, 116, 40, 6];
const ROWS: Box[] = [86, 98, 110].map((y) => [258, y, 28, 4]);
const STATUS: Pt = [182, 76];

const RAIL = route(line([RAIL_X0, RAIL_Y], [RAIL_X1, RAIL_Y]));
/* route fraction at stage x */
const at = (x: number) => (x - RAIL_X0) / (RAIL_X1 - RAIL_X0);

/* call 1: out to DB, hold while it works, back home */
const LEAVE: Stop = [0.04, 0];
const ARRIVE: Stop = [0.22, 1];
const RETURN: Stop = [0.3, 1];
const HOME: Stop = [0.48, 0];
const CALL: Stops = [LEAVE, ARRIVE, RETURN, HOME];

/* call 2: out to the cache only */
const HIT_AT = 0.67;
const CACHED: Stops = [
  [0.56, 0],
  [HIT_AT, at(CACHE_X)],
  [0.72, at(CACHE_X)],
  [0.83, 0],
];

/* derived beats: when a packet crosses the part it changes */
const MISS_AT = passAt(LEAVE, ARRIVE, at(CACHE_X));
const FILL_AT = passAt(RETURN, HOME, at(CACHE_X));

const pop = (t: number): Keys => ({ ...shown(t, t + 0.1, 0.02), scale: [1, 1, 1.5, 1, 1, 1] });

const MISS = beat(pop(MISS_AT));
const HIT = beat(pop(HIT_AT));
const BUSY = beat(shown(0.21, 0.32));
const ENTRY = beat({
  times: [0, FILL_AT, FILL_AT + 0.03, HIT_AT, HIT_AT + 0.02, HIT_AT + 0.07, 0.9, 0.94, 1],
  opacity: [0, 0, 0.6, 0.6, 1, 0.6, 0.6, 0, 0],
});

const FLIGHTS = [CALL, CACHED].map((stops) => ({
  key: stops[0][0],
  dot: beat(ride(RAIL, stops)),
  trail: beat(comet(stops, 0.14)),
}));

const NO_STROKE = "none";

/* Middle layer: wire first, opaque panels over it, trails on top. */
const Board = () => {
  const { palette: p } = useScene();
  return (
    <>
      <Wire d={RAIL.d} />
      <Panel box={CLIENT} fill={p.solid} />
      <Panel box={[34, 94, 20, 4]} rx={2} fill={p.n[16]} stroke={NO_STROKE} />
      <Panel box={[34, 102, 14, 4]} rx={2} fill={p.n[10]} stroke={NO_STROKE} />
      <Panel box={CACHE} fill={p.solid} />
      <Panel box={SLOT} rx={3} fill={p.n[5]} stroke={NO_STROKE} />
      <Panel box={SLOT} rx={3} fill={p.tint} stroke={NO_STROKE} loop={ENTRY} />
      <Panel box={DB} fill={p.solid} />
      {ROWS.map((row) => (
        <Panel key={row[1]} box={row} rx={2} fill={p.n[10]} stroke={NO_STROKE} />
      ))}
      <Panel box={DB} fill={p.t[16]} stroke={p.t[55]} loop={BUSY} />
      {FLIGHTS.map((f) => (
        <Trace key={f.key} d={RAIL.d} loop={f.trail} />
      ))}
    </>
  );
};

interface SceneProps {
  tint: string;
  frozen?: boolean;
}

export default function ExampleScene({ tint, frozen = false }: Readonly<SceneProps>) {
  const palette = useMemo(() => createPalette({ tint }), [tint]);
  return (
    <Shell
      palette={palette}
      focus={[CACHE_X, RAIL_Y]}
      texture="grid"
      frozen={frozen}
      svg={<Board />}
    >
      {FLIGHTS.map((f) => (
        <Packet key={f.key} loop={f.dot} />
      ))}
      <Pip at={STATUS} size={6} color={palette.warn} loop={MISS} />
      <Pip at={STATUS} size={6} color={palette.ok} loop={HIT} />
      <Label at={[26, 76]}>Client</Label>
      <Label at={[128, 58]}>Cache</Label>
      <Label at={[RAIL_X1, 64]}>DB</Label>
    </Shell>
  );
}

const SLOT_STYLE: CSSProperties = {
  position: "relative",
  aspectRatio: "16 / 10",
  overflow: "hidden",
  borderRadius: 12,
};

/* How a host mounts a scene: only near the viewport, frozen by the app's
   own reduced setting, keyed on it so leaving reduced mode restarts it. */
export function SceneSlot({ tint, reduced }: Readonly<{ tint: string; reduced: boolean }>) {
  const [ref, near] = useNearViewport<HTMLDivElement>();
  useFreezeAnimations(ref, reduced);
  const base = useMemo(() => createPalette({ tint }).base, [tint]);
  const media = near ? (
    <ExampleScene key={String(reduced)} tint={tint} frozen={reduced} />
  ) : (
    <div style={{ position: "absolute", inset: 0, background: base }} />
  );
  return (
    <div ref={ref} style={SLOT_STYLE}>
      {media}
    </div>
  );
}
