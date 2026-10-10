import { useRef } from "react";
import { useInView } from "motion/react";

/*
 * Ref plus a flag that is true while the element sits within `margin` px
 * of the viewport. Mount a looping scene only while it is true and paint a
 * placeholder with the same base gradient otherwise, so a grid of 40 cards
 * runs a handful of loops instead of 40.
 */
export function useNearViewport<T extends Element = HTMLDivElement>(margin = 300) {
  const ref = useRef<T>(null);
  const near = useInView(ref, { margin: `${margin}px 0px` });
  return [ref, near] as const;
}
