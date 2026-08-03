import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return "N/A";
  return score.toFixed(1);
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const then = new Date(value).getTime();
  const now = Date.now();
  const diffSeconds = Math.round((now - then) / 1000);

  const divisions: [Intl.RelativeTimeFormatUnit, number][] = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 30],
    ["month", 12],
    ["year", Infinity],
  ];

  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  let duration = diffSeconds;
  for (const [unit, amount] of divisions) {
    if (Math.abs(duration) < amount) {
      return rtf.format(-duration, unit);
    }
    duration = Math.round(duration / amount);
  }
  return rtf.format(-duration, "year");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

export function truncateMiddle(value: string, maxLength = 48): string {
  if (value.length <= maxLength) return value;
  const half = Math.floor((maxLength - 1) / 2);
  return `${value.slice(0, half)}…${value.slice(value.length - half)}`;
}
