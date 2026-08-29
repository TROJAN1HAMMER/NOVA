import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldAlert, LogIn, ArrowRight } from "lucide-react";
import { Button } from "../ui/Button";

interface LandingNavbarProps {
  onScrollToSection: (sectionId: string) => void;
}

export const LandingNavbar = memo(function LandingNavbar({ onScrollToSection }: LandingNavbarProps) {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-sky-900/20 bg-[#07090e]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Brand Logo */}
        <div
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="flex cursor-pointer items-center gap-3 transition-opacity hover:opacity-90"
        >
          <div className="flex size-9 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10 shadow-[0_0_15px_rgba(56,189,248,0.2)]">
            <ShieldAlert className="size-5 text-sky-400" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold tracking-wider text-slate-100">NOVA</span>
            <span className="text-[10px] font-mono tracking-widest text-sky-400/80 uppercase">Security Intelligence</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="hidden items-center gap-8 md:flex">
          <button
            onClick={() => onScrollToSection("architecture-shift")}
            className="text-xs font-mono text-slate-400 transition-colors hover:text-sky-400"
          >
            // ARCHITECTURE
          </button>
          <button
            onClick={() => onScrollToSection("core-capabilities")}
            className="text-xs font-mono text-slate-400 transition-colors hover:text-sky-400"
          >
            // CAPABILITIES
          </button>
          <button
            onClick={() => onScrollToSection("trust-decision")}
            className="text-xs font-mono text-slate-400 transition-colors hover:text-sky-400"
          >
            // TRUST MODEL
          </button>
          <button
            onClick={() => onScrollToSection("temporal-posture")}
            className="text-xs font-mono text-slate-400 transition-colors hover:text-sky-400"
          >
            // TEMPORAL POSTURE
          </button>
        </nav>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/login")}
            className="gap-2 border border-slate-800 text-slate-300 hover:bg-slate-800/60 hover:text-slate-100"
          >
            <LogIn className="size-3.5 text-sky-400" />
            Sign In
          </Button>
          <Button
            size="sm"
            onClick={() => navigate("/assistant")}
            className="gap-2 border border-sky-500/40 bg-sky-500/10 font-semibold text-sky-300 shadow-[0_0_20px_rgba(56,189,248,0.2)] hover:bg-sky-500/20 hover:text-sky-200"
          >
            Explore NOVA
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      </div>
    </header>
  );
});
