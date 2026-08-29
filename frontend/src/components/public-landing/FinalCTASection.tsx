import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ShieldCheck, LogIn, Cpu } from "lucide-react";
import { Button } from "../ui/Button";

export const FinalCTASection = memo(function FinalCTASection() {
  const navigate = useNavigate();

  return (
    <section className="relative z-10 border-t border-sky-900/30 bg-gradient-to-b from-slate-950 to-[#07090e] py-20 lg:py-28">
      <div className="mx-auto max-w-5xl px-6 text-center">
        <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3.5 py-1 font-mono text-xs font-semibold text-sky-300">
          <ShieldCheck className="size-4 text-sky-400" />
          <span>POLICY-GOVERNED AI DECISION MAKING</span>
        </div>

        <h2 className="text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl lg:text-5xl">
          Build security decisions on evidence.
        </h2>

        <p className="mx-auto mt-4 max-w-2xl text-balance text-base leading-relaxed text-slate-300">
          Explore how NOVA connects security intelligence, enterprise knowledge, 8D trust calibration, and policy-controlled AI reasoning to prevent ungrounded security risks.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          <Button
            size="lg"
            onClick={() => navigate("/assistant")}
            className="gap-2.5 border border-sky-400/40 bg-gradient-to-r from-sky-500 to-blue-600 px-8 font-semibold text-white shadow-[0_0_30px_rgba(56,189,248,0.3)] hover:from-sky-400 hover:to-blue-500"
          >
            Explore Assistant
            <ArrowRight className="size-4" />
          </Button>

          <Button
            size="lg"
            variant="outline"
            onClick={() => navigate("/security-intelligence")}
            className="gap-2 border-slate-800 bg-slate-900/80 px-6 text-slate-200 hover:border-slate-700 hover:bg-slate-800"
          >
            <Cpu className="size-4 text-sky-400" />
            Security Intelligence
          </Button>

          <Button
            size="lg"
            variant="ghost"
            onClick={() => navigate("/login")}
            className="gap-2 font-mono text-xs text-slate-400 hover:bg-slate-900/50 hover:text-sky-300"
          >
            <LogIn className="size-4 text-slate-500" />
            Sign In
          </Button>
        </div>
      </div>
    </section>
  );
});
