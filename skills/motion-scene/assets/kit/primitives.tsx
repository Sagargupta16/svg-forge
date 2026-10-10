import { createContext, use, useMemo, type CSSProperties, type ReactNode } from "react";
import { motion } from "motion/react";
import {
  STAGE_H,
  STAGE_W,
  VIEWBOX,
  createPalette,
  dotAt,
  layer,
  pctAt,
  pctX,
  pctY,
  texture,
} from "./tokens";
import type { Box, Palette, Pt, Texture } from "./tokens";
import { ambient, loopProps } from "./timing";
import type { Loop } from "./timing";

/*
 * Scene parts in three depth layers: back (base, texture, one tint wash),
 * middle (SVG panels and wires on a uniform stage) and front (HTML packets,
 * pips and labels at stage points with fixed px sizes).
 */

const NON_SCALING = "non-scaling-stroke";

interface SceneState {
  palette: Palette;
  frozen: boolean;
}

const SceneContext = createContext<SceneState>({
  palette: createPalette({ tint: "#60a5fa" }),
  frozen: false,
});

/* Palette and frozen flag of the nearest Shell. */
export const useScene = () => use(SceneContext);

/* Loop props that honor the scene's frozen flag: frozen paints frame 0 and
   starts nothing, so every track (pathLength included) stays still. */
export const useLoop = (loop?: Loop) => {
  const { frozen } = useScene();
  if (!loop) return undefined;
  const props = loopProps(loop);
  return frozen ? { initial: props.initial } : props;
};

/* ---------- stage ---------- */

export type Fit = "contain" | "cover";

const RATIO_W = Math.round((STAGE_W / STAGE_H) * 10000) / 100;
const RATIO_H = Math.round((STAGE_H / STAGE_W) * 10000) / 100;

const stageBox = (fit: Fit): CSSProperties => {
  const pick = fit === "cover" ? "max" : "min";
  return {
    position: "absolute",
    left: "50%",
    top: "50%",
    width: `${pick}(100cqw, ${RATIO_W}cqh)`,
    height: `${pick}(100cqh, ${RATIO_H}cqw)`,
    transform: "translate(-50%, -50%)",
  };
};

const FRAME: CSSProperties = { ...layer, containerType: "size" };
const SVG_FILL: CSSProperties = { ...layer, width: "100%", height: "100%", overflow: "visible" };

interface StageProps {
  /* contain letterboxes the stage, cover fills the slot and crops */
  fit?: Fit | undefined;
  /* middle layer: SVG content in stage units */
  svg?: ReactNode;
  /* front layer: HTML at stage percentages */
  children?: ReactNode;
}

/* The stage at its own ratio inside any slot, so SVG and HTML share one
   coordinate space and the viewBox always scales uniformly. */
export const Stage = ({ fit = "contain", svg, children }: Readonly<StageProps>) => (
  <div style={FRAME}>
    <div style={stageBox(fit)}>
      <svg viewBox={VIEWBOX} style={SVG_FILL}>
        {svg}
      </svg>
      {children}
    </div>
  </div>
);

/* ---------- back layer ---------- */

/* About 0.6 px per second: one lattice cell every 30 s or so. */
const DRIFT_SPEED = 0.6;

const Backdrop = ({
  kind,
  focus,
  drift,
}: Readonly<{ kind: Texture; focus: Pt; drift: boolean }>) => {
  const { palette } = useScene();
  const { cell, style } = texture(kind, palette);
  const move = useLoop(
    drift && cell > 0
      ? {
          duration: ambient(cell, DRIFT_SPEED),
          times: [0, 1],
          ease: "linear",
          transform: ["translate(0px, 0px)", `translate(${cell}px, ${cell}px)`],
        }
      : undefined,
  );
  if (kind === "none") return null;
  /* the mask sits on a static parent, so a drifting lattice never drags its fade */
  const mask = `radial-gradient(ellipse at ${pctAt(focus)}, #000 20%, transparent 80%)`;
  const fill = { position: "absolute", inset: -cell, ...style } satisfies CSSProperties;
  return (
    <div style={{ ...layer, overflow: "hidden", maskImage: mask, WebkitMaskImage: mask }}>
      {move ? <motion.div style={fill} {...move} /> : <div style={fill} />}
    </div>
  );
};

interface ShellProps {
  palette: Palette;
  /* focal point of the tint wash and texture fade, in stage units */
  focus: Pt;
  texture?: Texture;
  /* slow ambient drift of the texture */
  drift?: boolean;
  /* the app's reduced setting: paint frame 0, start no loops */
  frozen?: boolean;
  fit?: Fit;
  svg?: ReactNode;
  children?: ReactNode;
}

/* Root of every scene: decorative, clipped, one palette for all parts. */
export const Shell = ({
  palette,
  focus,
  texture: kind = "dots",
  drift = false,
  frozen = false,
  fit,
  svg,
  children,
}: Readonly<ShellProps>) => {
  const scene = useMemo(() => ({ palette, frozen }), [palette, frozen]);
  const wash = `radial-gradient(circle at ${pctAt(focus)}, ${palette.t[10]}, transparent 60%)`;
  return (
    <SceneContext value={scene}>
      <div aria-hidden="true" style={{ ...layer, overflow: "hidden", background: palette.base }}>
        <Backdrop kind={kind} focus={focus} drift={drift} />
        <div style={{ ...layer, background: wash }} />
        <Stage fit={fit} svg={svg}>
          {children}
        </Stage>
      </div>
    </SceneContext>
  );
};

/* ---------- middle layer (SVG, stage units) ---------- */

interface PanelProps {
  box: Box;
  rx?: number;
  fill?: string;
  stroke?: string;
  loop?: Loop;
}

/* Panel with a 1 px hairline border; with a loop it fades as one node. */
export const Panel = ({ box: [x, y, w, h], rx = 6, fill, stroke, loop }: Readonly<PanelProps>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  const rect = {
    x,
    y,
    width: w,
    height: h,
    rx,
    fill: fill ?? palette.n[3],
    stroke: stroke ?? palette.n[10],
    vectorEffect: NON_SCALING,
  };
  return anim ? <motion.rect {...rect} {...anim} /> : <rect {...rect} />;
};

interface WireProps {
  d: string;
  stroke?: string;
  dash?: string;
}

/* Static hairline, 1 px at any slot width. Never animate its stroke. */
export const Wire = ({ d, stroke, dash }: Readonly<WireProps>) => {
  const { palette } = useScene();
  return (
    <path
      d={d}
      fill="none"
      stroke={stroke ?? palette.n[10]}
      strokeWidth={1}
      strokeDasharray={dash}
      strokeLinecap="round"
      vectorEffect={NON_SCALING}
    />
  );
};

interface TraceProps {
  d: string;
  loop: Loop;
  color?: string;
  /* stroke width in stage units; it scales with the stage on purpose */
  width?: number;
}

/* Animated stroke (pathLength, pathOffset). No vector-effect, so the
   normalised dash lands where the keyframes say. */
export const Trace = ({ d, loop, color, width = 2.4 }: Readonly<TraceProps>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  return (
    <motion.path d={d} fill="none" stroke={color ?? palette.t[55]} strokeWidth={width} {...anim} />
  );
};

/* ---------- front layer (HTML, fixed px) ---------- */

interface PacketProps {
  loop: Loop;
  color?: string;
  size?: number;
}

/* Data in flight. The wrapper is stage sized, so percent translates are
   stage coordinates at any width while the head keeps its px size. */
export const Packet = ({ loop, color, size = 5 }: Readonly<PacketProps>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  return (
    <motion.div style={layer} {...anim}>
      <span style={dotAt([0, 0], size, color ?? palette.tint)} />
    </motion.div>
  );
};

interface PipProps {
  at: Pt;
  color?: string;
  size?: number;
  loop?: Loop;
}

/* Status dot: pulses with a loop, otherwise sits still. */
export const Pip = ({ at, color, size = 4, loop }: Readonly<PipProps>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  const style = dotAt(at, size, color ?? palette.tint);
  return anim ? <motion.span style={style} {...anim} /> : <span style={style} />;
};

interface LabelProps {
  at: Pt;
  children: string;
  color?: string;
  /* centred on the point instead of hanging to its right */
  centered?: boolean;
  loop?: Loop;
}

/* Mono micro label: HTML, so it keeps its px size at every slot width. */
export const Label = ({
  at: [x, y],
  children,
  color,
  centered = false,
  loop,
}: Readonly<LabelProps>) => {
  const { palette } = useScene();
  const anim = useLoop(loop);
  const style = {
    position: "absolute",
    left: pctX(x),
    top: pctY(y),
    fontFamily: palette.mono,
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: "0.08em",
    lineHeight: 1,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
    color: color ?? palette.n[55],
    translate: centered ? "-50% -50%" : "0 -50%",
  } satisfies CSSProperties;
  return anim ? (
    <motion.span style={style} {...anim}>
      {children}
    </motion.span>
  ) : (
    <span style={style}>{children}</span>
  );
};

interface FadeLayerProps {
  loop: Loop;
  children: ReactNode;
}

/* An HTML overlay fading on its own keys: one animated node for a group. */
export const FadeLayer = ({ loop, children }: Readonly<FadeLayerProps>) => {
  const anim = useLoop(loop);
  return (
    <motion.div style={layer} {...anim}>
      {children}
    </motion.div>
  );
};
