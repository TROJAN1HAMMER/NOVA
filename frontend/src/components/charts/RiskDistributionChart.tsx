import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartTheme } from "../../hooks/useChartTheme";
import { useChartEntryAnimation } from "../../hooks/useChartEntryAnimation";
import { ChartTooltip, ChartTooltipRow } from "./ChartTooltip";

const BUCKETS = [
  { min: 0, max: 20, label: "0-20" },
  { min: 20, max: 40, label: "20-40" },
  { min: 40, max: 60, label: "40-60" },
  { min: 60, max: 80, label: "60-80" },
  { min: 80, max: 100, label: "80-100" },
];

// Same four cutoffs as `RadialGauge`/`ExecutiveDashboardPage.tsx`'s
// `brsTier()` — colors the bucket by its midpoint's risk tier.
function tierColorFor(midpoint: number, dangerHex: string) {
  if (midpoint >= 82) return dangerHex;
  if (midpoint >= 58) return "#ec835a";
  if (midpoint >= 35) return "#fab219";
  return "#0ca30c";
}

/** BRS-score histogram — one point per repository (its latest score), so a
 *  repo scanned several times isn't double-counted across buckets. */
export function RiskDistributionChart({ scores, height = 260 }: { scores: number[]; height?: number }) {
  const chartTheme = useChartTheme();
  const isAnimationActive = useChartEntryAnimation(700);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const dangerHex = chartTheme.mode === "dark" ? "#e66767" : "#d03b3b";

  const data = BUCKETS.map((bucket) => ({
    ...bucket,
    count: scores.filter((score) => (bucket.max === 100 ? score >= bucket.min && score <= bucket.max : score >= bucket.min && score < bucket.max)).length,
    color: tierColorFor((bucket.min + bucket.max) / 2, dangerHex),
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap="20%">
        <CartesianGrid vertical={false} stroke={chartTheme.gridColor} />
        <XAxis dataKey="label" tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={{ stroke: chartTheme.gridColor }} />
        <YAxis allowDecimals={false} tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={false} width={32} />
        <Tooltip
          cursor={false}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as (typeof data)[number] | undefined;
            if (!active || !point) return null;
            return (
              <ChartTooltip active={active} title={`BRS ${point.label}`}>
                <ChartTooltipRow colorHex={point.color} label="Repositories" value={point.count} />
              </ChartTooltip>
            );
          }}
        />
        <Bar
          dataKey="count"
          radius={[4, 4, 0, 0]}
          maxBarSize={48}
          isAnimationActive={isAnimationActive}
          animationDuration={700}
          animationEasing="ease-out"
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {data.map((entry, index) => {
            const isDimmed = activeIndex !== null && activeIndex !== index;
            const isGlowing = activeIndex === index;
            return (
              <Cell
                key={entry.label}
                fill={entry.color}
                opacity={isDimmed ? 0.35 : 1}
                style={{
                  transition: "opacity 200ms ease, filter 200ms ease",
                  filter: isGlowing ? `drop-shadow(0 0 6px ${entry.color}80)` : undefined,
                }}
              />
            );
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
