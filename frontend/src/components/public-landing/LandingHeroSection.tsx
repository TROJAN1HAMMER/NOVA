import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck, LogIn, Sparkles, Terminal } from "lucide-react";
import { Button } from "../ui/Button";
import { NovaReasoningVisual } from "./NovaReasoningVisual";

interface LandingHeroSectionProps {
  onExploreClick: () => void;
}

export const LandingHeroSection = memo(function LandingHeroSection({ onExploreClick }: LandingHeroSectionProps) {
  const navigate = useNavigate();

  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6 pt-12 pb-20 lg:pt-20 lg:pb-28">
      <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12 lg:gap-8">
        {/* Left Column Copy */}
        <div className="flex flex-col items-start text-left lg:col-span-7">
          {/* Eyebrow Badge */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3.5 py-1 text-xs font-mono font-medium text-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.15)]">
            <Sparkles className="size-3.5 text-sky-400" />
            <span>NOVA ENTERPRISE SECURITY INTELLIGENCE</span>
          </div>

          {/* Main Headline */}
          <h1 className="text-balance text-4xl font-bold tracking-tight text-slate-100 sm:text-5xl lg:text-6xl lg:leading-[1.1]">
            Turn Security Evidence <br />
            <span className="bg-gradient-to-r from-sky-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
              Into Trusted Decisions.
            </span>
          </h1>

          {/* Subheadline Paragraph */}
          <p className="mt-6 max-w-2xl text-balance text-base leading-relaxed text-slate-300 sm:text-lg">
            NOVA combines enterprise knowledge, AST security intelligence, evidence reasoning, temporal posture analysis, and policy-controlled AI responses to help financial institutions and enterprise software teams make safer security decisions.
          </p>

          {/* CTA Buttons */}
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button
              size="lg"
              onClick={() => navigate("/assistant")}
              className="gap-2.5 border border-sky-400/40 bg-gradient-to-r from-sky-500 to-blue-600 px-6 font-semibold text-white shadow-[0_0_25px_rgba(56,189,248,0.3)] hover:from-sky-400 hover:to-blue-500"
            >
              Explore NOVA
              <ArrowRight className="size-4" />
            </Button>

            <Button
              size="lg"
              variant="outline"
              onClick={() => navigate("/login")}
              className="gap-2 border-slate-800 bg-slate-950/60 px-6 text-slate-200 hover:border-slate-700 hover:bg-slate-900"
            >
              <LogIn className="size-4 text-sky-400" />
              Sign In
            </Button>

            <Button
              size="lg"
              variant="ghost"
              onClick={onExploreClick}
              className="gap-2 font-mono text-xs text-slate-400 hover:bg-slate-900/50 hover:text-sky-300"
            >
              <Terminal className="size-4 text-slate-500" />
              View Architecture
            </Button>
          </div>

          {/* Mini Assurance Footer */}
          <div className="mt-10 flex flex-wrap items-center gap-6 border-t border-slate-800/80 pt-6 text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-sky-400" />
              <span>Platt-Calibrated 8D Trust</span>
            </div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-emerald-400" />
              <span>Two-Stage Hard Safety Policy</span>
            </div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-indigo-400" />
              <span>Zero Hallucination Contradiction Gate</span>
            </div>
          </div>
        </div>

        {/* Right Column Interactive Visual */}
        <div className="lg:col-span-5">
          <NovaReasoningVisual />
        </div>
      </div>
    </section>
  );
});
