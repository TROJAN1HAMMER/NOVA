import { useId, useMemo } from "react";
import { motion } from "framer-motion";
import { useReducedMotion } from "framer-motion";
import { cn } from "../../lib/utils";

// 270° sweep, open 90° at the bottom (a speedometer-style gauge) — 0° in
// this "clock" convention is straight up, increasing clockwise, which lines
// up 1:1 with a CSS `rotate(Ndeg)` transform for the needle.
const GAUGE_START = -135;
const GAUGE_END = 135;
const GAUGE_SWEEP = GAUGE_END - GAUGE_START;

// Same four cutoffs as `ExecutiveDashboardPage.tsx`'s `brsTier()` helper and
// the PDF report generator's risk-tier explanation — kept in sync rather
// than re-derived, since both Banking Risk Score and Attack Surface
// Exposure are scored 0-100 with the same "higher is worse" framing.
function tierFor(value: number, dangerHex: string) {
  if (value >= 82) return { color: dangerHex, label: "Critical" };
  if (value >= 58) return { color: "#ec835a", label: "High" };
  if (value >= 35) return { color: "#fab219", label: "Medium" };
  return { color: "#0ca30c", label: "Low" };
}

// Fixed colors per segment, in low-to-high order — deliberately not derived
// by calling `tierFor` on each bound itself: `tierFor(35, ...)` classifies
// 35 as the start of "Medium," which would wrongly paint the entire 0-35
// segment yellow instead of green.
const TIER_BOUNDS: Array<{ bound: number; color: string }> = [
  { bound: 35, color: "#0ca30c" },
  { bound: 58, color: "#fab219" },
  { bound: 82, color: "#ec835a" },
];

function clockToRad(clockDeg: number) {
  return ((clockDeg - 90) * Math.PI) / 180;
}

function polarPoint(cx: number, cy: number, r: number, clockDeg: number) {
  const rad = clockToRad(clockDeg);
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = polarPoint(cx, cy, r, startDeg);
  const end = polarPoint(cx, cy, r, endDeg);
  const largeArc = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

function angleForValue(value: number) {
  const clamped = Math.max(0, Math.min(100, value));
  return GAUGE_START + (clamped / 100) * GAUGE_SWEEP;
}

export interface RadialGaugeProps {
  label: string;
  value: number | null;
  size?: number;
  mode: "light" | "dark";
  className?: string;
}

/** Segmented-arc gauge used for both Banking Risk Score and Attack Surface
 *  Exposure — same 0-100/"higher is worse" scale, so one component covers
 *  both via the `label` prop. */
export function RadialGauge({ label, value, size = 176, mode, className }: RadialGaugeProps) {
  const gradientId = useId().replace(/:/g, "");
  const shouldReduceMotion = useReducedMotion();
  const dangerHex = mode === "dark" ? "#e66767" : "#d03b3b";
  const trackColor = mode === "dark" ? "#2c2c2a" : "#e1e0d9";
  const hasValue = value !== null && Number.isFinite(value);
  const safeValue = hasValue ? Math.max(0, Math.min(100, value)) : 0;

  const segments = useMemo(() => {
    const allBounds = [...TIER_BOUNDS, { bound: 100, color: dangerHex }];
    return allBounds.map(({ bound, color }, index) => {
      const prevBound = index > 0 ? allBounds[index - 1].bound : 0;
      const startDeg = GAUGE_START + (prevBound / 100) * GAUGE_SWEEP;
      const endDeg = GAUGE_START + (bound / 100) * GAUGE_SWEEP;
      return { key: bound, color, d: describeArc(0, 0, size / 2 - 14, startDeg, endDeg) };
    });
  }, [dangerHex, size]);

  const tier = hasValue ? tierFor(safeValue, dangerHex) : { color: trackColor, label: "No data" };
  const needleAngle = hasValue ? angleForValue(safeValue) : GAUGE_START;
  const r = size / 2 - 14;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`${-size / 2} ${-size / 2} ${size} ${size}`}>
        <defs>
          <filter id={`${gradientId}-glow`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background track (dim, full sweep) */}
        <path d={describeArc(0, 0, r, GAUGE_START, GAUGE_END)} fill="none" stroke={trackColor} strokeWidth={10} strokeLinecap="round" opacity={0.5} />

        {/* Segmented tier bands */}
        {segments.map((segment) => (
          <path key={segment.key} d={segment.d} fill="none" stroke={segment.color} strokeWidth={10} strokeLinecap="butt" opacity={hasValue ? 0.9 : 0.25} />
        ))}

        {/* Needle */}
        {hasValue && (
          <motion.g
            initial={shouldReduceMotion ? false : { rotate: GAUGE_START }}
            animate={{ rotate: needleAngle }}
            transition={shouldReduceMotion ? { duration: 0 } : { type: "spring", stiffness: 60, damping: 14 }}
            style={{ transformOrigin: "0px 0px" }}
          >
            <line x1={0} y1={0} x2={0} y2={-(r - 6)} stroke={tier.color} strokeWidth={2.5} strokeLinecap="round" filter={`url(#${gradientId}-glow)`} />
            <circle r={5} fill={tier.color} />
            <circle r={2} fill={mode === "dark" ? "#0d0d0d" : "#fcfcfb"} />
          </motion.g>
        )}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pt-3">
          <span className="text-[26px] font-semibold tabular-nums text-foreground">{hasValue ? safeValue.toFixed(1) : "—"}</span>
          <span className="text-xs font-medium" style={{ color: tier.color }}>
            {tier.label}
          </span>
          <span className="mt-1 text-xs text-muted-foreground">{label}</span>
        </div>
      </div>
    </div>
  );
}
