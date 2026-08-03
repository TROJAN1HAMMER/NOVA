import type { ReactNode } from "react";

/** Shared glass-style tooltip shell — matches the app's card language
 *  (`bg-card` + blur + border) rather than each chart inventing its own
 *  `contentStyle` object. Values lead (bold, high-contrast); series names
 *  stay secondary/muted per the dataviz tooltip hierarchy. */
export function ChartTooltip({
  active,
  title,
  children,
}: {
  active?: boolean;
  title?: ReactNode;
  children?: ReactNode;
}) {
  if (!active) return null;
  return (
    <div className="min-w-[10rem] rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-lg backdrop-blur-md dark:shadow-black/40">
      {title && <div className="mb-1.5 font-medium text-foreground">{title}</div>}
      <div className="space-y-1">{children}</div>
    </div>
  );
}

export function ChartTooltipRow({
  colorHex,
  label,
  value,
}: {
  colorHex?: string;
  label: ReactNode;
  value: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      {colorHex && <span aria-hidden className="h-0.5 w-3 shrink-0 rounded-full" style={{ backgroundColor: colorHex }} />}
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-auto font-semibold tabular-nums text-foreground">{value}</span>
    </div>
  );
}

/** Shown only where a genuine "previous" comparable value exists (a
 *  time-series point-over-point delta) — never fabricated for categorical
 *  breakdowns where "% change" isn't a meaningful concept. `invert` flips
 *  which direction reads as good/bad — e.g. a rising Banking Risk Score is
 *  worse, not better, so BRS trend passes `invert`. */
export function ChartTooltipDelta({ delta, unit = "", invert = false }: { delta: number; unit?: string; invert?: boolean }) {
  if (!Number.isFinite(delta) || delta === 0) return null;
  const isUp = delta > 0;
  const isGood = invert ? !isUp : isUp;
  return (
    <div className={`flex items-center gap-1 pt-0.5 text-[11px] font-medium ${isGood ? "text-success" : "text-danger"}`}>
      <span aria-hidden>{isUp ? "▲" : "▼"}</span>
      {Math.abs(delta).toFixed(1)}
      {unit} vs previous
    </div>
  );
}
