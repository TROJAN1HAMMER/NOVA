import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartTheme } from "../../hooks/useChartTheme";
import { useChartEntryAnimation } from "../../hooks/useChartEntryAnimation";
import { ChartGradientDefs } from "./ChartGradientDefs";
import { useChartGradientIds } from "../../hooks/useChartGradientIds";
import { ChartTooltip, ChartTooltipRow } from "./ChartTooltip";

export interface RepositoryScorePoint {
  name: string;
  score: number;
}

/** Highest Banking Risk Score per repository — extracted out of
 *  `RiskDashboardPage.tsx`'s previously inline `BarChart` so it shares the
 *  same gradient/hover/tooltip treatment as every other chart instead of
 *  duplicating the boilerplate a third time. */
export function RepositoryComparisonChart({ repositories, height = 280 }: { repositories: RepositoryScorePoint[]; height?: number }) {
  const chartTheme = useChartTheme();
  const isAnimationActive = useChartEntryAnimation(700);
  const ids = useChartGradientIds();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={repositories} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
        <ChartGradientDefs ids={ids} mode={chartTheme.mode} />
        <CartesianGrid horizontal={false} stroke={chartTheme.gridColor} />
        <XAxis type="number" domain={[0, 100]} tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={{ stroke: chartTheme.gridColor }} />
        <YAxis type="category" dataKey="name" tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={false} width={110} />
        <Tooltip
          cursor={{ fill: chartTheme.cursorFill }}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as RepositoryScorePoint | undefined;
            if (!point) return null;
            return (
              <ChartTooltip active={active} title={point.name}>
                <ChartTooltipRow colorHex={chartTheme.blue} label="BRS score" value={point.score.toFixed(1)} />
              </ChartTooltip>
            );
          }}
        />
        <Bar
          dataKey="score"
          radius={[0, 4, 4, 0]}
          maxBarSize={20}
          isAnimationActive={isAnimationActive}
          animationDuration={700}
          animationEasing="ease-out"
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {repositories.map((repo, index) => {
            const isDimmed = activeIndex !== null && activeIndex !== index;
            const isGlowing = activeIndex === index;
            return (
              <Cell
                key={repo.name}
                fill={`url(#${ids.blue})`}
                stroke={chartTheme.blue}
                strokeWidth={isGlowing ? 1 : 0}
                opacity={isDimmed ? 0.4 : 1}
                style={{
                  transition: "opacity 200ms ease, filter 200ms ease",
                  filter: isGlowing ? `drop-shadow(0 0 6px ${chartTheme.blue}80)` : undefined,
                }}
              />
            );
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
