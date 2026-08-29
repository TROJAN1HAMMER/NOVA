import { memo } from "react";
import { ArrowRight, CheckCircle2, XCircle } from "lucide-react";

export const ArchitectureShiftSection = memo(function ArchitectureShiftSection() {
  return (
    <section id="architecture-shift" className="relative z-10 mx-auto max-w-7xl px-6 py-20 lg:py-28">
      {/* Section Header */}
      <div className="mx-auto max-w-3xl text-center">
        <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
          THE ARCHITECTURAL PARADIGM SHIFT
        </span>
        <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
          Security intelligence, not just security scanning.
        </h2>
        <p className="mt-4 text-balance text-base text-slate-300">
          Traditional tools dump raw scanner findings into endless dashboards without context. NOVA builds asset-centric security graphs, evaluates control deficits, and fuses verified evidence with enterprise knowledge.
        </p>
      </div>

      {/* Comparison Grid */}
      <div className="mt-14 grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Traditional Approach (De-emphasized/Outdated) */}
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-8 opacity-80 transition-opacity hover:opacity-100">
          <div className="mb-6 flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2 text-slate-400">
              <XCircle className="size-5 text-rose-500/80" />
              <span className="font-mono text-xs font-semibold tracking-wider uppercase">Traditional Static Scanners</span>
            </div>
            <span className="rounded bg-rose-500/10 px-2 py-0.5 font-mono text-[10px] text-rose-400">NO CONTEXT</span>
          </div>

          <div className="flex flex-col items-center justify-center space-y-3 py-6 font-mono text-xs text-slate-400">
            <div className="rounded border border-slate-800 bg-slate-900/80 px-4 py-2 text-center text-slate-300">
              Raw AST Scanner Engine
            </div>
            <ArrowRight className="size-4 rotate-90 text-slate-600" />
            <div className="rounded border border-slate-800 bg-slate-900/80 px-4 py-2 text-center text-slate-300">
              Unverified Raw Finding Alert
            </div>
            <ArrowRight className="size-4 rotate-90 text-slate-600" />
            <div className="rounded border border-slate-800 bg-slate-900/80 px-4 py-2 text-center text-slate-300">
              Static Alert Dashboard (High Noise)
            </div>
          </div>

          <p className="mt-4 text-center text-xs text-slate-300">
            Result: False positives, uncalibrated alerts, and zero grounding for enterprise AI reasoning.
          </p>
        </div>

        {/* NOVA Security Intelligence Pipeline (Highlighted) */}
        <div className="relative rounded-2xl border border-sky-500/40 bg-gradient-to-b from-slate-900/90 to-slate-950/90 p-8 shadow-[0_0_40px_rgba(56,189,248,0.15)]">
          <div className="mb-6 flex items-center justify-between border-b border-sky-900/40 pb-4">
            <div className="flex items-center gap-2 text-sky-300">
              <CheckCircle2 className="size-5 text-sky-400" />
              <span className="font-mono text-xs font-semibold tracking-wider uppercase">NOVA Security Intelligence</span>
            </div>
            <span className="rounded border border-sky-500/30 bg-sky-500/20 px-2 py-0.5 font-mono text-[10px] text-sky-300">
              CONTEXT-AWARE
            </span>
          </div>

          {/* Pipeline Nodes */}
          <div className="grid grid-cols-2 gap-2.5 font-mono text-xs">
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              1. Assets Discovered
            </div>
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              2. AST Observations
            </div>
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              3. Context Graph
            </div>
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              4. Control Analysis
            </div>
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              5. Risk Scenarios
            </div>
            <div className="rounded border border-sky-900/40 bg-slate-900/90 p-2.5 text-center text-slate-200">
              6. Verification Gate
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-sky-500/30 bg-sky-950/30 p-3 text-center">
            <span className="font-mono text-xs font-bold text-sky-300">
              7. Security Evidence &rarr; Dual-Track RAG &rarr; Trusted Decision
            </span>
          </div>

          <p className="mt-4 text-center text-xs text-slate-300">
            Result: Grounded evidence, zero scanner noise, and verified security context.
          </p>
        </div>
      </div>
    </section>
  );
});
