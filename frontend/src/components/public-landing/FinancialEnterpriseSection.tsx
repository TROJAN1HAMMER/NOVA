import { memo } from "react";
import { Landmark, CreditCard, ShieldCheck, Building2, Server } from "lucide-react";

export const FinancialEnterpriseSection = memo(function FinancialEnterpriseSection() {
  const sectors = [
    { icon: Landmark, name: "BANKING", desc: "Evidence-grounded security reasoning for core banking microservices." },
    { icon: CreditCard, name: "PAYMENTS", desc: "Auditability for transaction processing and auth control pipelines." },
    { icon: ShieldCheck, name: "FINTECH", desc: "Policy-governed AI assistant for rapid secure software delivery." },
    { icon: Building2, name: "INSURANCE", desc: "Temporal posture tracking for enterprise risk and compliance management." },
    { icon: Server, name: "ENTERPRISE", desc: "AST context graph analysis across distributed cloud infrastructure." },
  ];

  return (
    <section className="relative z-10 border-t border-sky-900/30 bg-slate-950/80 py-20 lg:py-28 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
            ENTERPRISE DEPLOYMENT DOMAINS
          </span>
          <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
            Engineered for high-stakes environments.
          </h2>
          <p className="mt-4 text-balance text-base text-slate-300">
            NOVA is built for organizations where security decisions require evidence, auditability matters, contradictory information must be handled safely, and AI responses must remain strictly grounded.
          </p>
        </div>

        {/* Sectors Grid */}
        <div className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-5">
          {sectors.map((sec, idx) => {
            const Icon = sec.icon;
            return (
              <div
                key={idx}
                className="group flex flex-col items-center rounded-2xl border border-slate-800/80 bg-slate-900/40 p-6 text-center transition-all hover:border-sky-500/40 hover:bg-slate-900/80"
              >
                <div className="mb-4 flex size-12 items-center justify-center rounded-xl border border-sky-500/20 bg-sky-500/10 text-sky-400 group-hover:bg-sky-500/20 group-hover:text-sky-300">
                  <Icon className="size-6" />
                </div>
                <span className="font-mono text-xs font-bold text-slate-200">{sec.name}</span>
                <p className="mt-2 text-xs leading-relaxed text-slate-400">{sec.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
});
