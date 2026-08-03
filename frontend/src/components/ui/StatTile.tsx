import type { ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "../../lib/utils";
import { Card } from "./Card";
import { AnimatedCounter } from "./AnimatedCounter";

/**
 * `value` is typed as `ReactNode` because callers pass everything from raw
 * numbers to formatted strings ("82.3", "N/A") to plain labels (a
 * repository name). Only count up the cases that are actually numeric —
 * a bare number, or a string that's nothing but a number — so a label like
 * a repository name or "N/A" is left exactly as the caller formatted it.
 */
function parseNumericValue(value: ReactNode): { amount: number; decimals: number } | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return { amount: value, decimals: 0 };
  }
  if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value.trim())) {
    const trimmed = value.trim();
    const decimals = trimmed.includes(".") ? trimmed.split(".")[1].length : 0;
    return { amount: parseFloat(trimmed), decimals };
  }
  return null;
}

interface StatTileProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  delta?: {
    value: number;
    label: string;
    isGoodWhenUp?: boolean;
  };
  className?: string;
}

export function StatTile({ label, value, icon, delta, className }: StatTileProps) {
  let deltaColor = "text-muted-foreground";
  if (delta) {
    const goodWhenUp = delta.isGoodWhenUp ?? true;
    const isUp = delta.value >= 0;
    const isGood = isUp === goodWhenUp;
    deltaColor = isGood ? "text-success" : "text-danger";
  }

  const numeric = parseNumericValue(value);

  return (
    <Card className={cn("p-5", className)}>
      <div className="flex items-start justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        {icon && (
          <div
            className={cn(
              "flex size-9 shrink-0 items-center justify-center rounded-full border border-border/70",
              "bg-accent/40 text-accent-foreground backdrop-blur-sm",
              "transition-[box-shadow,color] duration-200 ease-out",
              "group-hover:text-primary group-hover:shadow-[0_0_14px_-2px_rgba(59,130,246,0.55)]",
            )}
          >
            {icon}
          </div>
        )}
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
        {numeric ? <AnimatedCounter value={numeric.amount} decimals={numeric.decimals} /> : value}
      </p>
      {delta && (
        <p className={cn("mt-1.5 flex items-center gap-1 text-xs font-medium", deltaColor)}>
          {delta.value >= 0 ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />}
          {Math.abs(delta.value)}% {delta.label}
        </p>
      )}
    </Card>
  );
}
