import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartTheme } from "../../hooks/useChartTheme";
import { useChartEntryAnimation } from "../../hooks/useChartEntryAnimation";
import { CATEGORICAL_PALETTE } from "../../lib/severity";
import { ChartGradientDefs } from "./ChartGradientDefs";
import { useChartGradientIds } from "../../hooks/useChartGradientIds";
import { ChartTooltip, ChartTooltipRow } from "./ChartTooltip";

export interface ScannerContributionPoint {
  source: string;
  count: number;
}

/** Findings logged per scanner engine, portfolio-wide — extracted out of
 *  `RiskDashboardPage.tsx`'s previously inline `BarChart` for the same
 *  reason as `RepositoryComparisonChart`: shared gradient/hover/tooltip
 *  treatment instead of duplicated boilerplate. */
export function ScannerContributionChart({ contributions, height = 260 }: { contributions: ScannerContributionPoint[]; height?: number }) {
  const chartTheme = useChartTheme();
  const isAnimationActive = useChartEntryAnimation(700);
  const ids = useChartGradientIds();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={contributions} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap="30%">
        <ChartGradientDefs ids={ids} mode={chartTheme.mode} />
        <CartesianGrid vertical={false} stroke={chartTheme.gridColor} />
        <XAxis dataKey="source" tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={{ stroke: chartTheme.gridColor }} />
        <YAxis allowDecimals={false} tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={false} width={40} />
        <Tooltip
          cursor={{ fill: chartTheme.cursorFill }}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as ScannerContributionPoint | undefined;
            if (!point) return null;
            return (
              <ChartTooltip active={active} title={point.source}>
                <ChartTooltipRow label="Findings" value={point.count} />
              </ChartTooltip>
            );
          }}
        />
        <Bar
          dataKey="count"
          radius={[4, 4, 0, 0]}
          maxBarSize={40}
          isAnimationActive={isAnimationActive}
          animationDuration={700}
          animationEasing="ease-out"
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {contributions.map((entry, index) => {
            const paletteIndex = index % CATEGORICAL_PALETTE.length;
            const isDimmed = activeIndex !== null && activeIndex !== index;
            const isGlowing = activeIndex === index;
            return (
              <Cell
                key={entry.source}
                fill={`url(#${ids.categorical(paletteIndex)})`}
                opacity={isDimmed ? 0.35 : 1}
                style={{
                  transition: "opacity 200ms ease, filter 200ms ease",
                  filter: isGlowing ? `drop-shadow(0 0 6px ${CATEGORICAL_PALETTE[paletteIndex][chartTheme.mode]}80)` : undefined,
                }}
              />
            );
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
