import { memo } from "react";
import { Cpu, Layers, GitBranch, ShieldAlert, Lock, Activity } from "lucide-react";

export const CoreCapabilitiesSection = memo(function CoreCapabilitiesSection() {
  const capabilities = [
    {
      icon: Cpu,
      title: "Security Intelligence",
      tag: "ASSET-CENTRIC",
      desc: "Discovers assets, extracts code AST observations, maps trust boundary crossings, and evaluates control deficits.",
    },
    {
      icon: Layers,
      title: "Evidence Fusion",
      tag: "DUAL-TRACK",
      desc: "Combines enterprise knowledge documents and AST security findings into unified, normalized evidence items.",
    },
    {
      icon: GitBranch,
      title: "NLI Evidence Reasoning",
      tag: "PAIRWISE MATRIX",
      desc: "Evaluates pairwise evidence relationships (SUPPORTS, CONTRADICTS, RELATED, UNRELATED) to detect conflicts.",
    },
    {
      icon: ShieldAlert,
      title: "Dynamic Trust Engine",
      tag: "8D PLATT SCALING",
      desc: "Calculates mathematical trust scores using 8 calibrated vector signals including retrieval, agreement, and freshness.",
    },
    {
      icon: Lock,
      title: "Two-Stage Safety Policy",
      tag: "HARD GATE",
      desc: "Prevents LLM generation when agreement drops below 0.20 or critical evidence contradictions are detected.",
    },
    {
      icon: Activity,
      title: "Temporal Security Posture",
      tag: "TIME-SERIES ΔS",
      desc: "Tracks security posture scores over time, calculating trajectory deltas and classifying new vs resolved risks.",
    },
  ];

  return (
    <section id="core-capabilities" className="relative z-10 mx-auto max-w-7xl px-6 py-20 lg:py-28">
      {/* Section Header */}
      <div className="mx-auto max-w-3xl text-center">
        <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
          CORE SYSTEM CAPABILITIES
        </span>
        <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
          Engineered for mission-critical security decisions.
        </h2>
        <p className="mt-4 text-balance text-base text-slate-300">
          Six tightly coupled engineering subsystems working together to guarantee grounded, explainable, and policy-governed AI output.
        </p>
      </div>

      {/* Grid */}
      <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {capabilities.map((cap, idx) => {
          const Icon = cap.icon;
          return (
            <div
              key={idx}
              className="group relative rounded-2xl border border-slate-800/80 bg-slate-950/60 p-6 transition-all hover:border-sky-500/40 hover:bg-slate-900/60 hover:shadow-[0_0_30px_rgba(56,189,248,0.1)]"
            >
              <div className="mb-4 flex items-center justify-between">
                <div className="flex size-11 items-center justify-center rounded-xl border border-sky-500/20 bg-sky-500/10 text-sky-400 transition-colors group-hover:bg-sky-500/20 group-hover:text-sky-300">
                  <Icon className="size-6" />
                </div>
                <span className="rounded border border-slate-800 bg-slate-900 px-2 py-0.5 font-mono text-[10px] text-sky-400">
                  {cap.tag}
                </span>
              </div>

              <h3 className="text-lg font-bold tracking-tight text-slate-100 group-hover:text-sky-300">
                {cap.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">
                {cap.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
});
