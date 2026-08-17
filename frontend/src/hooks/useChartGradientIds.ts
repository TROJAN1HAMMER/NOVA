import { useId } from "react";


export interface ChartGradientIds {
  blue: string;
  /** Renamed from `severity` — now maps confidence tiers to gradient IDs. */
  severity: (tier: string) => string;
  categorical: (index: number) => string;
}

/** Every gradient-consuming chart mounts its own `<defs>`, so ids are
 *  namespaced per chart instance (via `useId`) — safe even when the same
 *  chart component renders more than once on a page. */
export function useChartGradientIds(): ChartGradientIds {
  const raw = useId().replace(/[:]/g, "");
  return {
    blue: `${raw}-blue`,
    severity: (tier: string) => `${raw}-tier-${tier}`,
    categorical: (index) => `${raw}-cat-${index}`,
  };
}
