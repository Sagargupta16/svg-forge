import type { Easing } from "motion/react";

/*
 * One clock per scene. Every track of a loop shares `times`, written as
 * fractions of the cycle, so beats stay locked to the storyboard whatever
 * the cycle length is.
 */

/*
 * Default seconds per timing preset. Ranges: micro 0.12 to 0.3 (one-shot
 * feedback), short 0.4 to 1.2 (entrance, total under 1.5 with stagger),
 * medium 3 to 6 (seamless mechanism loop, the default), long 8 to 20
 * (storyboard of 3 to 6 beats), ambient 20 to 60 (drift, set by speed).
 */
export const PRESET = {
  micro: 0.2,
  short: 0.6,
  medium: 6,
  long: 12,
  ambient: 32,
} as const;

/* Seconds for an ambient drift or marquee to cover `distance` px. */
export const ambient = (distance: number, pxPerSecond = 40) => distance / pxPerSecond;

/* Animatable tracks: transform and opacity only, plus SVG stroke draws. */
export interface Tracks {
  x?: (number | string)[];
  y?: (number | string)[];
  scale?: number[];
  scaleX?: number[];
  scaleY?: number[];
  rotate?: number[];
  /* full transform string, e.g. "translate(10%, 40%)"; runs on WAAPI */
  transform?: string[];
  opacity?: number[];
  pathLength?: number[];
  pathOffset?: number[];
}

/* Tracks plus their shared `times` (fractions of the cycle, 0 to 1). */
export interface Keys extends Tracks {
  times: number[];
  ease?: Easing;
}

export interface Loop extends Keys {
  duration: number;
  delay?: number;
}

export type Frame = { [K in keyof Tracks]?: NonNullable<Tracks[K]>[number] };

/*
 * One ease per keyframe segment. Motion hands opacity (and transform
 * strings) to WAAPI, where a single ease string spans the whole iteration
 * and drags keyframes off their `times`, while x, y, scale and stroke props
 * ease per segment on the JS frameloop. An array keeps both on one clock.
 */
export const perSegment = (times: readonly number[], ease: Easing = "easeInOut"): Easing[] =>
  times.slice(1).map(() => ease);

/* First keyframe of every track: the painted frame before a loop starts. */
export const firstFrame = (tracks: Tracks): Frame =>
  Object.fromEntries(Object.entries(tracks).map(([key, values]) => [key, values?.[0]])) as Frame;

/* Spread onto a motion element: starts on frame 0 and repeats forever. */
export const loopProps = ({ duration, times, ease = "easeInOut", delay = 0, ...tracks }: Loop) => ({
  initial: firstFrame(tracks),
  animate: tracks,
  transition: {
    duration,
    times,
    delay,
    ease: perSegment(times, ease),
    repeat: Infinity,
  },
});

/* Bind a scene's cycle length once: const beat = clock(6). */
export const clock =
  (duration: number) =>
  (keys: Keys): Loop => ({ ...keys, duration });

/* Six keys: rest until `on`, rise, hold until `off`, fall, rest to the end. */
export const windowTimes = (on: number, off: number, rise = 0.05, fall = 0.06): number[] => [
  0,
  on,
  on + rise,
  off,
  off + fall,
  1,
];

/* Values for windowTimes: rest, rest, peak, peak, rest, rest. */
export const windowKeys = <T>(rest: T, peak: T): T[] => [rest, rest, peak, peak, rest, rest];

/* Opacity window: fades in at `on`, holds, is gone by `off`. */
export const shown = (on: number, off: number, ramp = 0.03): Keys => ({
  times: [0, on, on + ramp, off - ramp, off, 1],
  opacity: [0, 0, 1, 1, 0, 0],
});
