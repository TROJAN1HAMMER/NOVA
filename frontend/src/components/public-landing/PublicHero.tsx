import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn, Network, ShieldCheck, Sparkles, UserPlus } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "../ui/Button";
import { HeroShield3DSection } from "./HeroShield3DSection";

/**
 * The entire public landing page at `/` — by design, the landing page is
 * *only* this hero (see pages/LandingPage.tsx). Two-column layout
 * (~55/45): branding/copy/CTAs on the left, the interactive 3D shield on
 * the right. Same for every visitor, authenticated or not — Login/Sign
 * Up/Explore Architecture are the only three actions offered here.
 */
export const PublicHero = memo(function PublicHero() {
  const navigate = useNavigate();
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="relative isolate min-h-[calc(100vh-1px)] overflow-hidden bg-background">
      <style>{`
        @keyframes NOVA-public-hero-grid-fade {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 0.8; }
        }
        @keyframes NOVA-public-hero-blob-a {
          0%, 100% { transform: translate3d(-4%, -6%, 0) scale(1); }
          50% { transform: translate3d(4%, 4%, 0) scale(1.12); }
        }
        @keyframes NOVA-public-hero-blob-b {
          0%, 100% { transform: translate3d(6%, 4%, 0) scale(1.05); }
          50% { transform: translate3d(-6%, -3%, 0) scale(0.95); }
        }
        @keyframes NOVA-public-hero-blob-c {
          0%, 100% { transform: translate3d(-3%, 5%, 0) scale(0.98); }
          50% { transform: translate3d(5%, -5%, 0) scale(1.08); }
        }
        .NOVA-public-hero-blob-a { animation: NOVA-public-hero-blob-a 22s ease-in-out infinite; }
        .NOVA-public-hero-blob-b { animation: NOVA-public-hero-blob-b 26s ease-in-out infinite; }
        .NOVA-public-hero-blob-c { animation: NOVA-public-hero-blob-c 30s ease-in-out infinite; }
        .NOVA-public-hero-grid { animation: NOVA-public-hero-grid-fade 12s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .NOVA-public-hero-blob-a, .NOVA-public-hero-blob-b, .NOVA-public-hero-blob-c, .NOVA-public-hero-grid {
            animation: none;
          }
        }
      `}</style>

      {/* Backdrop — grid pattern + soft gradient blobs, purely decorative. */}
      <div className="pointer-events-none absolute inset-0 z-0" aria-hidden>
        <div
          className="NOVA-public-hero-grid absolute inset-0 opacity-60 dark:opacity-40"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, var(--color-border) 0, var(--color-border) 1px, transparent 1px, transparent 40px), repeating-linear-gradient(90deg, var(--color-border) 0, var(--color-border) 1px, transparent 1px, transparent 40px)",
          }}
        />
        <div className="NOVA-public-hero-blob-a absolute -left-24 -top-24 size-96 rounded-full bg-primary/20 blur-3xl dark:bg-primary/25" />
        <div className="NOVA-public-hero-blob-b absolute -right-16 top-8 size-80 rounded-full bg-accent/40 blur-3xl dark:bg-accent/30" />
        <div className="NOVA-public-hero-blob-c absolute bottom-[-6rem] left-1/3 size-96 rounded-full bg-success/10 blur-3xl dark:bg-success/10" />
      </div>

      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-1px)] max-w-6xl grid-cols-1 items-center gap-10 px-6 py-16 sm:px-10 lg:grid-cols-[55fr_45fr] lg:gap-6 lg:py-0">
        <motion.div
          className="flex flex-col items-center gap-6 text-center lg:items-start lg:text-left"
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

          <p className="max-w-xl text-balance text-base text-muted-foreground sm:text-lg">
            NOVA runs every repository through a 9-stage scan pipeline, fans out across 6 parallel scanner engines,
            and turns raw findings into AI-explained remediation, a single Banking Risk Score, and mapped compliance
            evidence for RBI, PCI-DSS, and SWIFT CSP — before a single line reaches production.
          </p>

          <div className="mt-2 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
            <Button size="lg" onClick={() => navigate("/login")}>
              <LogIn className="size-4" />
              Login
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate("/signup")}>
              <UserPlus className="size-4" />
              Sign Up
            </Button>
            <Button size="lg" variant="ghost" onClick={() => navigate("/architecture")}>
              <Network className="size-4" />
              Explore Architecture
            </Button>
          </div>
        </motion.div>

        <motion.div
          className="flex items-center justify-center"
          initial={shouldReduceMotion ? undefined : { opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
        >
          <HeroShield3DSection />
        </motion.div>
      </div>
    </div>
  );
});
