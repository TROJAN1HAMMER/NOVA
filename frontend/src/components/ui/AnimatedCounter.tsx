import { useEffect, useRef, useState } from "react";
import { animate, useReducedMotion } from "framer-motion";

/**
 * Counts a numeric value up (or down) from its previous displayed value to
 * the new one, rather than snapping instantly — used by `StatTile` for any
 * value that's actually numeric. Counts from 0 on first mount only; later
 * value changes animate from whatever was last on screen. Runs exactly once
 * per value change (the effect below is keyed on `value` alone), and shows
 * the final number immediately under reduced motion.
 */
export function AnimatedCounter({
  value,
  decimals = 0,
  duration = 0.7,
  className,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const shouldReduceMotion = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const previousValue = useRef(value);
  const hasMounted = useRef(false);

  useEffect(() => {
    // Reduced-motion renders `value` directly below rather than through
    // `display` state, so there's nothing to animate/subscribe to here.
    if (shouldReduceMotion) return;

    const from = hasMounted.current ? previousValue.current : 0;
    hasMounted.current = true;

    // `animate()` is the "subscribe to an external system" half of the
    // effect — it drives its own rAF loop and calls `onUpdate` (a plain
    // callback, not a synchronous call in the effect body) each frame.
    const controls = animate(from, value, {
      duration,
      ease: "easeOut",
      onUpdate: (latest) => setDisplay(latest),
    });
    previousValue.current = value;

    return () => controls.stop();
    // Only re-run when the target value changes — `duration`/`shouldReduceMotion`
    // are stable per-mount in practice and re-running on them would replay
    // the count needlessly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span className={className}>{(shouldReduceMotion ? value : display).toFixed(decimals)}</span>;
}
