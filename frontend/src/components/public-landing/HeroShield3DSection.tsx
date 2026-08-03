import { Component, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { useReducedMotion } from "framer-motion";
import { HeroShieldStatic } from "./HeroShieldStatic";

// The only place `three` / `@react-three/fiber` / `@react-three/drei` are
// imported for the hero visual — a React.lazy() dynamic import puts
// HeroShield3D and its dependencies in their own chunk, fetched only when
// this section actually mounts. No dashboard or architecture-page route
// imports this module, so none of it ever reaches those bundles.
const HeroShield3D = lazy(() => import("./HeroShield3D"));

interface BoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
}

/** Swaps in the static shield glyph if the 3D scene throws (e.g. no WebGL). */
class HeroShield3DErrorBoundary extends Component<BoundaryProps, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("HeroShield3D failed to render; falling back to the static glyph.", error);
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

/**
 * Gates the interactive 3D hero shield behind:
 * - `prefers-reduced-motion` (shows the static glyph instead of any
 *   animated/WebGL scene at all)
 * - a render-error boundary (falls back to the same static glyph on older
 *   devices without WebGL, or any other render failure)
 * - visibility, via IntersectionObserver — not to delay the initial mount
 *   (this is the hero, so it's normally in view immediately), but to pass a
 *   `paused` flag down so the animation loop stops burning cycles if the
 *   hero is ever scrolled out of view (e.g. a short viewport).
 */
export function HeroShield3DSection() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(true);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry) setIsVisible(entry.isIntersecting);
      },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const staticFallback = <HeroShieldStatic />;

  return (
    <div ref={containerRef} className="flex w-full items-center justify-center">
      {shouldReduceMotion ? (
        staticFallback
      ) : (
        <HeroShield3DErrorBoundary fallback={staticFallback}>
          <Suspense fallback={staticFallback}>
            <div className="aspect-square w-full max-w-md">
              <HeroShield3D paused={!isVisible} />
            </div>
          </Suspense>
        </HeroShield3DErrorBoundary>
      )}
    </div>
  );
}
