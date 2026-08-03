import { useMemo } from "react";
import { useTheme } from "./useTheme";

export interface ChartTheme {
  mode: "light" | "dark";
  gridColor: string;
  axisColor: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipText: string;
  cursorFill: string;
  surface: string;
  blue: string;
}

const LIGHT: ChartTheme = {
  mode: "light",
  gridColor: "#e1e0d9",
  axisColor: "#52514e",
  tooltipBg: "#fcfcfb",
  tooltipBorder: "rgba(11,11,11,0.1)",
  tooltipText: "#0b0b0b",
  cursorFill: "rgba(11,11,11,0.03)",
  surface: "#fcfcfb",
  blue: "#2a78d6",
};

const DARK: ChartTheme = {
  mode: "dark",
  gridColor: "#2c2c2a",
  axisColor: "#c3c2b7",
  tooltipBg: "#1a1a19",
  tooltipBorder: "rgba(255,255,255,0.1)",
  tooltipText: "#ffffff",
  cursorFill: "rgba(255,255,255,0.04)",
  surface: "#1a1a19",
  blue: "#3987e5",
};

/** Extracts the gridColor/axisColor/tooltip-color boilerplate that used to be
 *  copy-pasted at every chart call site into one hook, and adds the surface/
 *  blue tokens the new gradient defs and gauges reference. */
export function useChartTheme(): ChartTheme {
  const { theme } = useTheme();
  return useMemo(() => (theme === "dark" ? DARK : LIGHT), [theme]);
}
