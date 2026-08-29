import { memo } from "react";
import { Database, Cpu, Lock, CheckCircle2, Layers, ArrowDown } from "lucide-react";

/**
 * Live Security Intelligence Reasoning Engine Visualization.
 * Shows the flow: Evidence Inputs -> Evidence Fusion -> Pairwise NLI Matrix -> 8D Trust Calibrator -> Safety Gate -> Trusted Decision.
 */
export const NovaReasoningVisual = memo(function NovaReasoningVisual() {
  return (
    <div className="relative w-full rounded-2xl border border-sky-900/40 bg-slate-950/70 p-6 shadow-[0_0_50px_rgba(14,165,233,0.15)] backdrop-blur-xl">
      {/* Header Bar */}
      <div className="mb-6 flex items-center justify-between border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-2">
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
            <span className="relative inline-flex size-2.5 rounded-full bg-sky-500"></span>
          </span>
          <span className="font-mono text-xs font-semibold tracking-wider text-slate-300 uppercase">
            NOVA Core Reasoning Engine
          </span>
        </div>
        <span className="rounded border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 font-mono text-[10px] text-sky-400">
          PLATT CALIBRATED • 8D
        </span>
      </div>

      {/* Pipeline Grid Flow */}
      <div className="space-y-4">
        {/* Stage 1: Tri-Track Evidence Retrieval */}
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-center transition-all hover:border-sky-500/40">
            <Database className="mx-auto mb-1 size-4 text-sky-400" />
            <div className="font-mono text-[11px] font-medium text-slate-200">Knowledge</div>
            <div className="text-[9px] text-slate-400">pgvector HNSW</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-center transition-all hover:border-sky-500/40">
            <Cpu className="mx-auto mb-1 size-4 text-sky-400" />
            <div className="font-mono text-[11px] font-medium text-slate-200">Security Intel</div>
            <div className="text-[9px] text-slate-400">AST Context Graph</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-center transition-all hover:border-sky-500/40">
            <Layers className="mx-auto mb-1 size-4 text-sky-400" />
            <div className="font-mono text-[11px] font-medium text-slate-200">Temporal Posture</div>
            <div className="text-[9px] text-slate-400">Time-Series ΔS</div>
          </div>
        </div>

        <div className="flex justify-center">
          <ArrowDown className="size-4 animate-bounce text-sky-500/60" />
        </div>

        {/* Stage 2: Dual-Track Evidence Fusion */}
        <div className="rounded-lg border border-sky-500/30 bg-slate-900/80 p-3 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <span className="font-mono text-[11px] font-semibold text-sky-300">Unified Evidence Fusion</span>
            <span className="font-mono text-[10px] text-slate-400">Reliability Weight: 0.95</span>
          </div>
          <p className="text-[10px] text-slate-400">Normalizes knowledge chunks and AST security assessments into UnifiedEvidenceItem dicts.</p>
        </div>

        <div className="flex justify-center">
          <ArrowDown className="size-4 animate-bounce text-sky-500/60" />
        </div>

        {/* Stage 3: Pairwise NLI Consensus Matrix */}
        <div className="rounded-lg border border-blue-500/30 bg-slate-900/80 p-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-mono text-[11px] font-semibold text-blue-300">Pairwise NLI Consensus Matrix</span>
            <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[9px] font-medium text-emerald-400">C_agreement: 0.92</span>
          </div>
          <div className="grid grid-cols-4 gap-1 font-mono text-[9px] text-center">
            <div className="rounded bg-slate-800/80 py-1 text-emerald-400">SUPPORTS</div>
            <div className="rounded bg-slate-800/80 py-1 text-emerald-400">SUPPORTS</div>
            <div className="rounded bg-slate-800/80 py-1 text-slate-400">RELATED</div>
            <div className="rounded bg-slate-800/80 py-1 text-slate-400">UNRELATED</div>
          </div>
        </div>

        <div className="flex justify-center">
          <ArrowDown className="size-4 animate-bounce text-sky-500/60" />
        </div>

        {/* Stage 4: 8D Platt Trust & Two-Stage Safety Policy Gate */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-sky-500/30 bg-slate-900/80 p-3">
            <div className="font-mono text-[10px] font-semibold text-sky-400 mb-1">8D TrustScore</div>
            <div className="text-xl font-bold font-mono text-slate-100">0.942</div>
            <div className="text-[9px] text-slate-400 mt-0.5">Platt Calibrated Logit</div>
          </div>
          <div className="rounded-lg border border-emerald-500/40 bg-emerald-950/20 p-3">
            <div className="flex items-center gap-1 font-mono text-[10px] font-semibold text-emerald-400 mb-1">
              <Lock className="size-3" /> Safety Policy Gate
            </div>
            <div className="text-xs font-bold font-mono text-emerald-300">STAGE 2 PASSED</div>
            <div className="text-[9px] text-emerald-400/80 mt-0.5">Zero Contradictions</div>
          </div>
        </div>

        {/* Output Banner */}
        <div className="flex items-center justify-between rounded-lg border border-emerald-500/40 bg-emerald-950/30 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-400" />
            <span className="font-mono text-xs font-semibold text-emerald-200">DECISION: GENERATE (GROUNDED)</span>
          </div>
          <span className="font-mono text-[10px] text-emerald-400/80">Safety Gate Approved</span>
        </div>
      </div>
    </div>
  );
});
