import { useEffect, useRef } from "react";
import { useReducedMotion } from "framer-motion";

// Same ease-toward-cursor approach as `components/landing/Hero.tsx`'s
// spotlight — refs + rAF, never React state, so hovering never re-renders.
// Cards are much smaller than the hero section, so the diameter/opacity are
// tuned down: a hint of reflected light, not a floodlight.
const SPOTLIGHT_EASE = 0.14;
export const CARD_SPOTLIGHT_DIAMETER_PX = 240;

/**
 * Attach `containerRef` to the element the light should track the cursor
 * within, and `glowRef` to an absolutely-positioned, `pointer-events-none`
 * child sized `CARD_SPOTLIGHT_DIAMETER_PX` square. Fades in on
 * `mouseenter`/out on `mouseleave` (both handled here, so callers don't
 * need their own opacity transition); a no-op entirely under
 * `prefers-reduced-motion`. The rAF loop only runs while actually hovered —
 * idle cards cost nothing.
 */
export function useCardSpotlight() {
  const containerRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const shouldReduceMotion = useReducedMotion();

  const targetRef = useRef({ x: 0, y: 0 });
  const currentRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (shouldReduceMotion) return;
    const container = containerRef.current;
    const glow = glowRef.current;
    if (!container || !glow) return;

    const tick = () => {
      const target = targetRef.current;
      const current = currentRef.current;
      current.x += (target.x - current.x) * SPOTLIGHT_EASE;
      current.y += (target.y - current.y) * SPOTLIGHT_EASE;

      glow.style.transform = `translate3d(${current.x - CARD_SPOTLIGHT_DIAMETER_PX / 2}px, ${
        current.y - CARD_SPOTLIGHT_DIAMETER_PX / 2
      }px, 0)`;

      rafRef.current = requestAnimationFrame(tick);
    };

    const handleMouseMove = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      targetRef.current = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };

    const handleMouseEnter = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const pos = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      targetRef.current = pos;
      currentRef.current = pos;
      glow.style.opacity = "1";
      if (rafRef.current === null) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    const handleMouseLeave = () => {
      glow.style.opacity = "0";
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    container.addEventListener("mouseenter", handleMouseEnter);
    container.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      container.removeEventListener("mouseenter", handleMouseEnter);
      container.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("mouseleave", handleMouseLeave);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [shouldReduceMotion]);

  return { containerRef, glowRef, shouldReduceMotion };
}
