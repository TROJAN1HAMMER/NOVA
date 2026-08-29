import { memo } from "react";
import { Database, Cpu, Layers, GitBranch, ShieldAlert, Lock } from "lucide-react";

export const TrustStripSection = memo(function TrustStripSection() {
  const pillars = [
    { icon: Database, label: "Knowledge Base", desc: "pgvector HNSW" },
    { icon: Cpu, label: "Security Intelligence", desc: "AST Context Graph" },
    { icon: Layers, label: "Temporal Posture", desc: "Time-Series ΔS" },
    { icon: GitBranch, label: "NLI Reasoning", desc: "Pairwise Matrix" },
    { icon: ShieldAlert, label: "Trust Calibration", desc: "8D Platt Score" },
    { icon: Lock, label: "Safety Policy", desc: "Hard Refusal Gate" },
  ];

  return (
    <section className="relative z-10 border-y border-sky-900/30 bg-slate-950/60 py-10 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mb-6 text-center">
          <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
            ONE SYSTEM. MULTIPLE SOURCES. ONE GROUNDED DECISION.
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          {pillars.map((p, idx) => {
            const Icon = p.icon;
            return (
              <div
                key={idx}
                className="group flex flex-col items-center rounded-xl border border-slate-800/80 bg-slate-900/40 p-4 text-center transition-all hover:border-sky-500/40 hover:bg-slate-900/80 hover:shadow-[0_0_20px_rgba(56,189,248,0.1)]"
              >
                <div className="mb-2 flex size-10 items-center justify-center rounded-lg border border-sky-500/20 bg-sky-500/10 text-sky-400 transition-colors group-hover:bg-sky-500/20 group-hover:text-sky-300">
                  <Icon className="size-5" />
                </div>
                <span className="font-mono text-xs font-semibold text-slate-200">{p.label}</span>
                <span className="mt-0.5 text-[10px] text-slate-400">{p.desc}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
});
