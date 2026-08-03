import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartTheme } from "../../hooks/useChartTheme";
import { useChartEntryAnimation } from "../../hooks/useChartEntryAnimation";
import { CATEGORICAL_PALETTE } from "../../lib/severity";
import { ChartGradientDefs } from "./ChartGradientDefs";
import { useChartGradientIds } from "../../hooks/useChartGradientIds";
import { ChartTooltip, ChartTooltipRow } from "./ChartTooltip";

export interface ComplianceBarPoint {
  shortCode: string;
  frameworkName: string;
  compliancePercentage: number;
}

export function ComplianceBarChart({ points, height = 240 }: { points: ComplianceBarPoint[]; height?: number }) {
  const chartTheme = useChartTheme();
  const isAnimationActive = useChartEntryAnimation(700);
  const ids = useChartGradientIds();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={points} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
        <ChartGradientDefs ids={ids} mode={chartTheme.mode} />
        <CartesianGrid horizontal={false} stroke={chartTheme.gridColor} />
        <XAxis
          type="number"
          domain={[0, 100]}
          tick={{ fill: chartTheme.axisColor, fontSize: 12 }}
          tickLine={false}
          axisLine={{ stroke: chartTheme.gridColor }}
          unit="%"
        />
        <YAxis
          type="category"
          dataKey="shortCode"
          tick={{ fill: chartTheme.axisColor, fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          width={72}
        />
        <Tooltip
          cursor={{ fill: chartTheme.cursorFill }}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as ComplianceBarPoint | undefined;
            if (!point) return null;
            return (
              <ChartTooltip active={active} title={point.frameworkName}>
                <ChartTooltipRow label="Compliance" value={`${point.compliancePercentage.toFixed(0)}%`} />
              </ChartTooltip>
            );
          }}
        />
        <Bar
          dataKey="compliancePercentage"
          radius={[0, 4, 4, 0]}
          maxBarSize={24}
          isAnimationActive={isAnimationActive}
          animationDuration={700}
          animationEasing="ease-out"
          onMouseEnter={(_, index) => setActiveIndex(index)}
          onMouseLeave={() => setActiveIndex(null)}
        >
          {points.map((entry, index) => {
            const paletteIndex = index % CATEGORICAL_PALETTE.length;
            const isDimmed = activeIndex !== null && activeIndex !== index;
            const isGlowing = activeIndex === index;
            return (
              <Cell
                key={entry.shortCode}
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
