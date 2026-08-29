import { memo } from "react";
import { Database, Server, Code2, Cpu, Activity } from "lucide-react";

export const TechnicalFoundationSection = memo(function TechnicalFoundationSection() {
  const stack = [
    { icon: Database, name: "PostgreSQL & pgvector", role: "HNSW vector store & time-series posture snapshot persistence." },
    { icon: Server, name: "FastAPI Async Engine", role: "Asynchronous backend API microservices with Pydantic validation." },
    { icon: Code2, name: "React & TypeScript", role: "Componentized frontend UI with SSE streaming & interactive evidence inspector." },
    { icon: Cpu, name: "NLI & Cross-Encoder", role: "Pairwise contradiction detection and MiniLM semantic reranking." },
    { icon: Activity, name: "Celery & Redis Workers", role: "Background search analytics processing and self-healing gap clustering." },
  ];

  return (
    <section className="relative z-10 mx-auto max-w-7xl px-6 py-20 lg:py-28">
      {/* Section Header */}
      <div className="mx-auto max-w-3xl text-center">
        <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
          VERIFIED TECHNICAL FOUNDATION
        </span>
        <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
          Built on proven enterprise infrastructure.
        </h2>
        <p className="mt-4 text-balance text-base text-slate-300">
          Every layer of NOVA's implementation is grounded in production-tested open-source software and mathematically calibrated models.
        </p>
      </div>

      {/* Stack Grid */}
      <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3 lg:grid-cols-5">
        {stack.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 text-center transition-all hover:border-sky-500/40 hover:bg-slate-900/60"
            >
              <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-lg border border-sky-500/20 bg-sky-500/10 text-sky-400">
                <Icon className="size-5" />
              </div>
              <h4 className="font-mono text-xs font-bold text-slate-200">{item.name}</h4>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{item.role}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
});
