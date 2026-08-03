import { CONFIDENCE_ORDER, confidenceStyle, CATEGORICAL_PALETTE } from "../../lib/severity";
import type { ChartGradientIds } from "../../hooks/useChartGradientIds";

export function ChartGradientDefs({ ids, mode }: { ids: ChartGradientIds; mode: "light" | "dark" }) {
  const blueHex = mode === "dark" ? "#3987e5" : "#2a78d6";
  return (
    <defs>
      <linearGradient id={ids.blue} x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor={blueHex} stopOpacity={0.32} />
        <stop offset="95%" stopColor={blueHex} stopOpacity={0.02} />
      </linearGradient>
      {CONFIDENCE_ORDER.map((tier) => {
        const hex = confidenceStyle(tier === "VERY_HIGH" ? 0.95 : tier === "HIGH" ? 0.8 : tier === "MEDIUM" ? 0.6 : tier === "LOW" ? 0.3 : 0).hex;
        return (
          <linearGradient key={tier} id={ids.severity(tier)} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={hex} stopOpacity={1} />
            <stop offset="100%" stopColor={hex} stopOpacity={0.7} />
          </linearGradient>
        );
      })}
      {CATEGORICAL_PALETTE.map((entry, index) => (
        <linearGradient key={entry.name} id={ids.categorical(index)} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={entry[mode]} stopOpacity={1} />
          <stop offset="100%" stopColor={entry[mode]} stopOpacity={0.7} />
        </linearGradient>
      ))}
    </defs>
  );
}
