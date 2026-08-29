import { memo } from "react";
import { AlertTriangle, ShieldAlert, XCircle, CheckCircle2 } from "lucide-react";

export const ContradictionDemoSection = memo(function ContradictionDemoSection() {
  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6 py-20 lg:py-28">
      {/* Header */}
      <div className="mx-auto max-w-3xl text-center">
        <span className="font-mono text-xs font-semibold tracking-widest text-amber-400 uppercase">
          CONTRADICTION EXPLAINABILITY DEMONSTRATION
        </span>
        <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
          Visualizing contradictory security evidence.
        </h2>
        <p className="mt-4 text-balance text-base text-slate-300">
          When two enterprise sources assert incompatible security states for the same location, NOVA detects the contradiction and withholding the ungrounded answer.
        </p>
      </div>

      {/* Illustrative Container */}
      <div className="mt-14 rounded-2xl border border-amber-500/30 bg-slate-950/80 p-8 shadow-[0_0_50px_rgba(245,158,11,0.1)]">
        <div className="mb-4 flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-400" />
            <span className="font-mono text-xs font-semibold text-slate-200">
              SAFETY GATE TRIGGER: CRITICAL_CONTRADICTION
            </span>
          </div>
          <span className="rounded bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-400">
            Illustrative NOVA reasoning flow
          </span>
        </div>

        {/* Evidence Pair Comparison Grid */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Evidence A */}
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold text-rose-300">EVIDENCE A (Security Intel)</span>
              <span className="font-mono text-[10px] text-slate-400">app/auth.py:42</span>
            </div>
            <p className="font-mono text-xs leading-relaxed text-slate-300">
              "Critical unpatched SQL injection vulnerability detected on auth.py line 42 allowing database bypass."
            </p>
            <div className="mt-3 flex items-center gap-2 text-[10px] text-rose-400">
              <XCircle className="size-3.5" />
              <span>Security Property: INPUT_VALIDATION_SQLI (VULNERABLE)</span>
            </div>
          </div>

          {/* Evidence B */}
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold text-emerald-300">EVIDENCE B (Knowledge Doc)</span>
              <span className="font-mono text-[10px] text-slate-400">app/auth.py:42</span>
            </div>
            <p className="font-mono text-xs leading-relaxed text-slate-300">
              "auth.py line 42 is secure and not vulnerable to SQL injection after complete parameterization."
            </p>
            <div className="mt-3 flex items-center gap-2 text-[10px] text-emerald-400">
              <CheckCircle2 className="size-3.5" />
              <span>Security Property: INPUT_VALIDATION_SQLI (SAFE)</span>
            </div>
          </div>
        </div>

        {/* NLI & Safety Decision Output */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-amber-500/30 bg-amber-950/30 p-4">
          <div className="flex items-center gap-4">
            <div>
              <span className="text-[10px] text-slate-400 block">NLI RELATIONSHIP</span>
              <span className="font-mono text-xs font-bold text-rose-400">CONTRADICTS (91% Confidence)</span>
            </div>
            <div className="h-6 w-px bg-slate-800" />
            <div>
              <span className="text-[10px] text-slate-400 block">AGREEMENT SCORE</span>
              <span className="font-mono text-xs font-bold text-amber-300">C_agreement = 0.10</span>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded border border-rose-500/40 bg-rose-950/40 px-3 py-1.5 font-mono text-xs font-bold text-rose-200">
            <ShieldAlert className="size-4 text-rose-400" />
            <span>SAFETY GATE DECISION: FALLBACK_WEB (GENERATION WITHHELD)</span>
          </div>
        </div>
      </div>
    </section>
  );
});
