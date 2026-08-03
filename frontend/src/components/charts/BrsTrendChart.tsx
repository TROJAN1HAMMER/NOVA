import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartTheme } from "../../hooks/useChartTheme";
import { useChartEntryAnimation } from "../../hooks/useChartEntryAnimation";
import { ChartGradientDefs } from "./ChartGradientDefs";
import { useChartGradientIds } from "../../hooks/useChartGradientIds";
import { ChartTooltip, ChartTooltipRow, ChartTooltipDelta } from "./ChartTooltip";
import { formatDateTime } from "../../lib/utils";

export interface BrsTrendPoint {
  finishedAt: string;
  brsScore: number;
  repositoryName: string;
}

interface TrendDatum extends BrsTrendPoint {
  label: string;
  delta: number;
}

export function BrsTrendChart({ points, height = 280 }: { points: BrsTrendPoint[]; height?: number }) {
  const chartTheme = useChartTheme();
  const isAnimationActive = useChartEntryAnimation(700);
  const ids = useChartGradientIds();

  const data: TrendDatum[] = points.map((p, index) => ({
    ...p,
    label: new Date(p.finishedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    delta: index > 0 ? p.brsScore - points[index - 1].brsScore : 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
        <ChartGradientDefs ids={ids} mode={chartTheme.mode} />
        <CartesianGrid vertical={false} stroke={chartTheme.gridColor} />
        <XAxis dataKey="label" tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={{ stroke: chartTheme.gridColor }} />
        <YAxis domain={[0, 100]} tick={{ fill: chartTheme.axisColor, fontSize: 12 }} tickLine={false} axisLine={false} width={40} />
        <Tooltip
          cursor={{ stroke: chartTheme.gridColor, strokeWidth: 1 }}
          content={({ active, payload }) => {
            const point = payload?.[0]?.payload as TrendDatum | undefined;
            if (!point) return null;
            return (
              <ChartTooltip active={active} title={formatDateTime(point.finishedAt)}>
                <ChartTooltipRow colorHex={chartTheme.blue} label={point.repositoryName} value={point.brsScore.toFixed(1)} />
                <ChartTooltipDelta delta={point.delta} invert />
              </ChartTooltip>
            );
          }}
        />
        <Area
          type="monotone"
          dataKey="brsScore"
          stroke={chartTheme.blue}
          strokeWidth={2}
          fill={`url(#${ids.blue})`}
          dot={false}
          activeDot={{ r: 5, fill: chartTheme.blue, strokeWidth: 2, stroke: chartTheme.surface }}
          isAnimationActive={isAnimationActive}
          animationDuration={700}
          animationEasing="ease-out"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
