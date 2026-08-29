import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

export const LandingFooter = memo(function LandingFooter() {
  const navigate = useNavigate();

  return (
    <footer className="relative z-10 border-t border-slate-800/80 bg-[#05070a] py-12">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 sm:flex-row">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10">
            <ShieldAlert className="size-4 text-sky-400" />
          </div>
          <div>
            <span className="font-mono text-sm font-bold tracking-wider text-slate-200">NOVA</span>
            <span className="ml-2 text-xs font-mono text-slate-500">Enterprise Security Intelligence Platform</span>
          </div>
        </div>

        {/* Links */}
        <div className="flex flex-wrap items-center gap-6 font-mono text-xs text-slate-400">
          <button onClick={() => navigate("/security-intelligence")} className="transition-colors hover:text-sky-400">
            Security Intelligence
          </button>
          <button onClick={() => navigate("/assistant")} className="transition-colors hover:text-sky-400">
            Assistant RAG
          </button>
          <button onClick={() => navigate("/executive")} className="transition-colors hover:text-sky-400">
            Executive Radar
          </button>
          <button onClick={() => navigate("/login")} className="transition-colors hover:text-sky-400">
            Sign In
          </button>
        </div>

        {/* Copyright */}
        <div className="font-mono text-xs text-slate-500">
          © 2026 NOVA. All rights reserved.
        </div>
      </div>
    </footer>
  );
});
