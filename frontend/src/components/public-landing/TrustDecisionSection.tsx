import { memo } from "react";
import { ShieldCheck, ShieldAlert, Lock, CheckCircle2, AlertTriangle } from "lucide-react";

export const TrustDecisionSection = memo(function TrustDecisionSection() {
  return (
    <section id="trust-decision" className="relative z-10 border-y border-sky-900/30 bg-slate-950/80 py-20 lg:py-28 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
            TWO-STAGE POLICY GOVERNANCE
          </span>
          <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
            Confidence is not permission.
          </h2>
          <p className="mt-4 text-balance text-base text-slate-300">
            A high statistical confidence score alone should never grant an AI model permission to answer when evidence directly contradicts itself. NOVA separates statistical probability scaling from hard safety policy enforcement.
          </p>
        </div>

        {/* Visual Governance Diagram */}
        <div className="mt-14 rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-[0_0_50px_rgba(14,165,233,0.1)]">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12">
            {/* Stage 1: Statistical Calibration */}
            <div className="space-y-4 rounded-xl border border-sky-500/20 bg-slate-950/60 p-6">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <ShieldCheck className="size-5 text-sky-400" />
                <span className="font-mono text-sm font-bold text-sky-300">STAGE 1: Statistical Platt Calibration</span>
              </div>
              <p className="text-xs leading-relaxed text-slate-300">
                Calculates an 8-dimensional Platt-scaled TrustScore based on vector similarity, citation coverage, source reliability, and hallucination risk metrics.
              </p>
              <div className="rounded border border-slate-800 bg-slate-900/80 p-3 font-mono text-xs text-slate-200">
                <span className="text-sky-400">TrustScore = 0.942</span> (High Statistical Confidence)
              </div>
            </div>

            {/* Stage 2: Hard Safety Policy Gate */}
            <div className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-6">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <Lock className="size-5 text-emerald-400" />
                <span className="font-mono text-sm font-bold text-emerald-300">STAGE 2: Hard Safety Policy Constraint</span>
              </div>
              <p className="text-xs leading-relaxed text-slate-300">
                Enforces strict policy rules. If NLI agreement C_agreement &le; 0.20 or critical security evidence conflicts, the policy overrules Stage 1 regardless of score.
              </p>
              <div className="rounded border border-emerald-500/30 bg-slate-900/80 p-3 font-mono text-xs text-emerald-300">
                <span>Contradiction Check: CLEAN &rarr; </span>
                <span className="font-bold text-emerald-400">GENERATE</span>
              </div>
            </div>
          </div>

          {/* Decision Outcomes Strip */}
          <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="flex items-center gap-3 rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3">
              <CheckCircle2 className="size-5 text-emerald-400 shrink-0" />
              <div>
                <div className="font-mono text-xs font-bold text-emerald-300">TRUSTED $\to$ GENERATE</div>
                <div className="text-[10px] text-slate-400">High trust, zero contradiction</div>
              </div>
            </div>

            <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-950/20 p-3">
              <AlertTriangle className="size-5 text-amber-400 shrink-0" />
              <div>
                <div className="font-mono text-xs font-bold text-amber-300">LOW TRUST $\to$ FALLBACK</div>
                <div className="text-[10px] text-slate-400">Triggers web fallback search</div>
              </div>
            </div>

            <div className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-950/20 p-3">
              <ShieldAlert className="size-5 text-rose-400 shrink-0" />
              <div>
                <div className="font-mono text-xs font-bold text-rose-300">CONTRADICTION $\to$ ABSTAIN</div>
                <div className="text-[10px] text-slate-400">Hard refusal + explanation banner</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
});
