import { memo, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Network, ShieldCheck, Sparkles } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "../ui/Button";

// Lower = the glow takes longer to "catch up" to the cursor — the weighty,
// never-jumps feel comes entirely from this factor being small, not from a
// CSS transition (a per-frame lerp toward the raw cursor position, driven by
// rAF).
const SPOTLIGHT_EASE = 0.09;
const SPOTLIGHT_DIAMETER_PX = 640;
// How far the grid/blobs backdrop drifts opposite the glow — deliberately
// tiny; this is the "almost imperceptible" bonus parallax, not the main effect.
const PARALLAX_MAX_PX = 4;

/**
 * Landing-page hero. The animated backdrop (grid + drifting gradient blobs)
 * is pure CSS — defined in the scoped <style> below rather than the global
 * stylesheet, so it stays local to this component. It's disabled entirely
 * under `prefers-reduced-motion: reduce`.
 */
export const Hero = memo(function Hero() {
  const navigate = useNavigate();
  const shouldReduceMotion = useReducedMotion();

  const sectionRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  // Refs, not state: a spotlight that re-rendered React on every mousemove
  // would defeat the point of a 60fps cursor-follow effect. Position data
  // never touches the component's render output.
  const targetRef = useRef({ x: 0, y: 0 });
  const currentRef = useRef({ x: 0, y: 0 });
  const rectRef = useRef({ width: 0, height: 0 });
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // No spotlight/parallax at all under reduced-motion — not just a faster
    // version of it, since the whole point is motion.
    if (shouldReduceMotion) return;
    const section = sectionRef.current;
    const glow = glowRef.current;
    const backdrop = backdropRef.current;
    if (!section || !glow || !backdrop) return;

    const tick = () => {
      const target = targetRef.current;
      const current = currentRef.current;
      current.x += (target.x - current.x) * SPOTLIGHT_EASE;
      current.y += (target.y - current.y) * SPOTLIGHT_EASE;

      // translate3d, not left/top: stays on the GPU compositor, never
      // touches layout.
      glow.style.transform = `translate3d(${current.x - SPOTLIGHT_DIAMETER_PX / 2}px, ${
        current.y - SPOTLIGHT_DIAMETER_PX / 2
      }px, 0)`;

      const { width, height } = rectRef.current;
      if (width > 0 && height > 0) {
        const parallaxX = (current.x / width - 0.5) * 2 * PARALLAX_MAX_PX;
        const parallaxY = (current.y / height - 0.5) * 2 * PARALLAX_MAX_PX;
        backdrop.style.transform = `translate3d(${parallaxX}px, ${parallaxY}px, 0)`;
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    const handleMouseMove = (event: MouseEvent) => {
      const rect = section.getBoundingClientRect();
      targetRef.current = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };

    const handleMouseEnter = (event: MouseEvent) => {
      const rect = section.getBoundingClientRect();
      rectRef.current = { width: rect.width, height: rect.height };
      const pos = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      // Snap the starting point straight to the entry position — only the
      // *ongoing* motion eases, so there's no glow sliding in from a stale
      // last-known spot.
      targetRef.current = pos;
      currentRef.current = pos;
      glow.style.opacity = "1";
      if (rafRef.current === null) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    const handleMouseLeave = () => {
      glow.style.opacity = "0";
      backdrop.style.transform = "translate3d(0, 0, 0)";
      // Stop rendering entirely while idle — no rAF loop running with
      // nothing visible to show for it.
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    section.addEventListener("mouseenter", handleMouseEnter);
    section.addEventListener("mousemove", handleMouseMove);
    section.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      section.removeEventListener("mouseenter", handleMouseEnter);
      section.removeEventListener("mousemove", handleMouseMove);
      section.removeEventListener("mouseleave", handleMouseLeave);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [shouldReduceMotion]);

  return (
    <div ref={sectionRef} className="relative overflow-hidden rounded-2xl border border-border bg-card">
      <style>{`
        @keyframes NOVA-hero-grid-fade {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 0.8; }
        }
        @keyframes NOVA-hero-blob-a {
          0%, 100% { transform: translate3d(-4%, -6%, 0) scale(1); }
          50% { transform: translate3d(4%, 4%, 0) scale(1.12); }
        }
        @keyframes NOVA-hero-blob-b {
          0%, 100% { transform: translate3d(6%, 4%, 0) scale(1.05); }
          50% { transform: translate3d(-6%, -3%, 0) scale(0.95); }
        }
        @keyframes NOVA-hero-blob-c {
          0%, 100% { transform: translate3d(-3%, 5%, 0) scale(0.98); }
          50% { transform: translate3d(5%, -5%, 0) scale(1.08); }
        }
        .NOVA-hero-blob-a { animation: NOVA-hero-blob-a 22s ease-in-out infinite; }
        .NOVA-hero-blob-b { animation: NOVA-hero-blob-b 26s ease-in-out infinite; }
        .NOVA-hero-blob-c { animation: NOVA-hero-blob-c 30s ease-in-out infinite; }
        .NOVA-hero-grid { animation: NOVA-hero-grid-fade 12s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .NOVA-hero-blob-a, .NOVA-hero-blob-b, .NOVA-hero-blob-c, .NOVA-hero-grid {
            animation: none;
          }
        }
      `}</style>

      {/* Backdrop — grid pattern + soft gradient blobs, purely decorative.
          `willChange: transform` primes the compositor layer since the
          cursor-parallax effect below repaints this via `transform` on
          every animation frame while hovered. */}
      <div
        ref={backdropRef}
        className="pointer-events-none absolute inset-0 z-0"
        style={{ willChange: "transform" }}
        aria-hidden
      >
        <div
          className="NOVA-hero-grid absolute inset-0 opacity-60 dark:opacity-40"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, var(--color-border) 0, var(--color-border) 1px, transparent 1px, transparent 40px), repeating-linear-gradient(90deg, var(--color-border) 0, var(--color-border) 1px, transparent 1px, transparent 40px)",
          }}
        />
        <div className="NOVA-hero-blob-a absolute -left-24 -top-24 size-96 rounded-full bg-primary/20 blur-3xl dark:bg-primary/25" />
        <div className="NOVA-hero-blob-b absolute -right-16 top-8 size-80 rounded-full bg-accent/40 blur-3xl dark:bg-accent/30" />
        <div className="NOVA-hero-blob-c absolute bottom-[-6rem] left-1/3 size-96 rounded-full bg-success/10 blur-3xl dark:bg-success/10" />
      </div>

      {/* Cursor-following spotlight — a soft radial gradient, not a blurred
          solid, so the falloff is exact and cheap (no `filter: blur()` on a
          large, per-frame-repainted element). Sits above the backdrop but
          below the actual hero content, and is entirely inert to pointer
          events so it never interferes with the buttons above it. */}
      {!shouldReduceMotion && (
        <div
          ref={glowRef}
          aria-hidden
          className="pointer-events-none absolute left-0 top-0 z-[1] opacity-0 transition-opacity duration-500 ease-out"
          style={{
            width: SPOTLIGHT_DIAMETER_PX,
            height: SPOTLIGHT_DIAMETER_PX,
            background:
              "radial-gradient(circle, rgba(59,130,246,0.15) 0%, rgba(59,130,246,0.08) 45%, transparent 75%)",
            willChange: "transform",
          }}
        />
      )}

      <motion.div
        className="relative z-10 mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 py-16 text-center sm:px-10 sm:py-20"
        initial={shouldReduceMotion ? undefined : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" />
          AI-Powered DevSecOps for Banking
        </div>

        <div className="flex items-center gap-2">
          <ShieldCheck className="size-8 text-primary" />
          <span className="text-2xl font-semibold tracking-tight text-foreground">NOVA</span>
        </div>

        <h1 className="text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
          AI-Powered DevSecOps Platform for Banking &amp; Financial Institutions
        </h1>

        <p className="max-w-2xl text-balance text-base text-muted-foreground sm:text-lg">
          NOVA runs every repository through a 9-stage scan pipeline, fans out across 6 parallel scanner engines,
          and turns raw findings into AI-explained remediation, a single Banking Risk Score, and mapped compliance
          evidence for RBI, PCI-DSS, and SWIFT CSP.
        </p>

        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Button size="lg" onClick={() => navigate("/repositories")}>
            Start Scan
          </Button>
          <Button size="lg" variant="outline" onClick={() => navigate("/architecture")}>
            <Network className="size-4" />
            Explore Architecture
          </Button>
          <Button size="lg" variant="ghost" onClick={() => navigate("/risk")}>
            <BarChart3 className="size-4" />
            View Dashboard
          </Button>
        </div>
      </motion.div>
    </div>
  );
});
