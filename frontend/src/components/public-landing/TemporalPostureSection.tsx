import { memo } from "react";
import { Activity, TrendingDown } from "lucide-react";

export const TemporalPostureSection = memo(function TemporalPostureSection() {
  return (
    <section id="temporal-posture" className="relative z-10 border-t border-sky-900/30 bg-slate-950/60 py-20 lg:py-28 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <span className="font-mono text-xs font-semibold tracking-widest text-sky-400 uppercase">
            TIME-SERIES POSTURE ENGINE
          </span>
          <h2 className="mt-3 text-balance text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
            NOVA remembers how security posture changes.
          </h2>
          <p className="mt-4 text-balance text-base text-slate-300">
            Security is not static. NOVA persists historical posture snapshots, calculates trajectory deltas (&Delta;S = S_current - S_previous), and maps risk evolution over time.
          </p>
        </div>

        {/* Dashboard Preview Card */}
        <div className="mt-14 rounded-2xl border border-slate-800 bg-slate-900/60 p-8 shadow-[0_0_50px_rgba(56,189,248,0.1)]">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-center">
            {/* Left Metrics */}
            <div className="space-y-6 lg:col-span-5">
              <div className="rounded-xl border border-sky-500/30 bg-slate-950/80 p-5">
                <span className="text-xs text-slate-400 block mb-1">Current Security Posture Score</span>
                <div className="flex items-center gap-3">
                  <span className="text-4xl font-bold font-mono text-slate-100">95.0 / 100</span>
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-xs font-semibold text-emerald-400">
                    STRONG
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-2 font-mono text-xs text-amber-400">
                  <TrendingDown className="size-4" />
                  <span>ΔS = -2.4% (DEGRADED since Run #12)</span>
                </div>
              </div>

              {/* Risk Evolution Breakdown */}
              <div className="grid grid-cols-3 gap-3 font-mono text-xs text-center">
                <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3">
                  <span className="text-lg font-bold text-rose-400 block">+1</span>
                  <span className="text-[10px] text-slate-400">NEW RISKS</span>
                </div>
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3">
                  <span className="text-lg font-bold text-emerald-400 block">-2</span>
                  <span className="text-[10px] text-slate-400">RESOLVED</span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-lg font-bold text-slate-300 block">4</span>
                  <span className="text-[10px] text-slate-400">PERSISTENT</span>
                </div>
              </div>
            </div>

            {/* Right Time Series Graph Simulation */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-6 lg:col-span-7">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="size-4 text-sky-400" />
                  <span className="font-mono text-xs font-semibold text-slate-200">Historical Posture Trend (Run History)</span>
                </div>
                <span className="font-mono text-[10px] text-slate-400">Target Scope: . (Repository Root)</span>
              </div>

              {/* SVG Sparkline Graph */}
              <div className="h-40 w-full pt-4">
                <svg className="size-full overflow-visible" viewBox="0 0 400 100">
                  <path
                    d="M 0,20 L 80,15 L 160,25 L 240,10 L 320,30 L 400,28"
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="3"
                  />
                  <circle cx="0" cy="20" r="4" fill="#38bdf8" />
                  <circle cx="80" cy="15" r="4" fill="#38bdf8" />
                  <circle cx="160" cy="25" r="4" fill="#38bdf8" />
                  <circle cx="240" cy="10" r="4" fill="#10b981" />
                  <circle cx="320" cy="30" r="4" fill="#f59e0b" />
                  <circle cx="400" cy="28" r="5" fill="#38bdf8" className="animate-ping" />
                </svg>
              </div>

              <div className="mt-4 flex justify-between font-mono text-[10px] text-slate-400 border-t border-slate-800 pt-3">
                <span>Run #1 (100.0)</span>
                <span>Run #5 (98.2)</span>
                <span>Run #10 (97.4)</span>
                <span>Run #14 (95.0)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
});
