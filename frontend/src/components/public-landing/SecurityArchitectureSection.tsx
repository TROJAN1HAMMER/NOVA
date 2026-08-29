import { memo } from "react";
import { ArrowRight } from "lucide-react";

export const SecurityArchitectureSection = memo(function SecurityArchitectureSection() {
  const steps = [
    { title: "Asset Discovery", desc: "Maps repositories, endpoints, databases, and microservices." },
    { title: "AST Observations", desc: "Extracts facts, public routes, unsanitized inputs, and secret usages." },
    { title: "Context Graph", desc: "Constructs in-memory data flow graph and trust boundary crossings." },
    { title: "Control Analysis", desc: "Evaluates PRESENT, ABSENT, PARTIAL, BYPASSED security controls." },
    { title: "Risk Scenarios", desc: "Infers threat paths when trust boundaries cross missing controls." },
    { title: "Scenario Verifier", desc: "Validates candidate scenarios into verified security assessments." },
    { title: "Security Assessment", desc: "Persists evidence chains, attack paths, and remediation guidance." },
    { title: "Temporal Posture", desc: "Records time-series posture snapshots and calculates trajectory deltas." },
  ];

  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6 py-20 lg:py-28">
      {/* Section Header */}
      <div className="mx-auto max-w-3xl text-center">
        <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
          FULL PIPELINE ARCHITECTURE
        </span>
        <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
          From source code AST to grounded AI evidence.
        </h2>
        <p className="mt-4 text-balance text-base text-slate-300">
          The 8-stage Security Intelligence Subsystem that transforms static code repositories into structured, verifiable evidence for NOVA's Assistant RAG.
        </p>
      </div>

      {/* 8-Stage Flow */}
      <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((s, idx) => (
          <div
            key={idx}
            className="group relative rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition-all hover:border-sky-500/40 hover:bg-slate-900/60"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="flex size-7 items-center justify-center rounded-lg border border-sky-500/30 bg-sky-500/10 font-mono text-xs font-bold text-sky-400">
                0{idx + 1}
              </span>
              {idx < steps.length - 1 && (
                <ArrowRight className="hidden size-4 text-slate-600 lg:block" />
              )}
            </div>
            <h4 className="font-mono text-sm font-bold text-slate-200 group-hover:text-sky-300">
              {s.title}
            </h4>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
              {s.desc}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
});
