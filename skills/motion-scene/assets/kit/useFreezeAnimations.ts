import { useEffect, type RefObject } from "react";

/*
 * Pauses every Web Animations API animation inside `ref` at time 0 while
 * `frozen` is true (pass the app's own reduced setting).
 *
 * Motion's reducedMotion makes x, y and scale instant but leaves opacity,
 * transform strings and CSS keyframes running on WAAPI, so dots keep
 * blinking in place. Pausing at time 0 shows each loop's rest frame. Kit
 * primitives already stop when their Shell is frozen; this hook is the
 * backstop for anything else in the subtree. Key the scene on the setting
 * so leaving reduced mode restarts it cleanly.
 */
export function useFreezeAnimations(ref: RefObject<Element | null>, frozen: boolean) {
  useEffect(() => {
    const el = ref.current;
    if (!frozen || !el) return;

    const freeze = () => {
      for (const animation of el.getAnimations({ subtree: true })) {
        animation.pause();
        animation.currentTime = 0;
      }
    };

    /* Motion starts animations a frame or two after commit and lazy scenes
       mount later still: sweep now, on the next frames, and on mutations. */
    let frame = 0;
    let timer = 0;
    const sweep = () => {
      freeze();
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        freeze();
        frame = requestAnimationFrame(freeze);
      });
      window.clearTimeout(timer);
      timer = window.setTimeout(freeze, 400);
    };

    sweep();
    const observer = new MutationObserver(sweep);
    observer.observe(el, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [ref, frozen]);
}
