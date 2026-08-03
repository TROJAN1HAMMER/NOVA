import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

/**
 * Recharts replays its enter animation on every data-reference change by
 * default (`isAnimationActive` defaults to `true` for the life of the
 * component), which reads as flashy every time a chart refetches or gets a
 * live update rather than a one-time "draw in" on first load. This returns
 * `isAnimationActive` wired to stay true only through the chart's first
 * paint, then flips permanently false once that initial animation has had
 * time to finish, so later data refreshes (polling, websocket-driven
 * updates) redraw in place instead of re-animating. Always false under
 * reduced motion.
 */
export function useChartEntryAnimation(durationMs = 700): boolean {
  const shouldReduceMotion = useReducedMotion();
  const [firstPaintActive, setFirstPaintActive] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    timer.current = setTimeout(() => setFirstPaintActive(false), durationMs + 50);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return !shouldReduceMotion && firstPaintActive;
}
