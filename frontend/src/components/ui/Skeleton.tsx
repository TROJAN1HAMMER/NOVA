import type { CSSProperties } from "react";
import { useReducedMotion } from "framer-motion";
import { cn } from "../../lib/utils";

/**
 * Base shimmer placeholder. Only the sweep overlay's `transform` animates
 * (see `.animate-skeleton-sweep` in index.css) — the block itself is a
 * static `bg-muted` rectangle, so this is cheap even in long lists and
 * never renders a moving element at all under reduced motion.
 */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  const shouldReduceMotion = useReducedMotion();
  return (
    <div className={cn("relative overflow-hidden rounded-md bg-muted", className)} style={style}>
      {!shouldReduceMotion && (
        <div
          aria-hidden
          className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-foreground/[0.06] to-transparent animate-skeleton-sweep"
        />
      )}
    </div>
  );
}

/** Placeholder grid shaped like a row of `StatTile`s. */
export function SkeletonStatTiles({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card/45 p-5 backdrop-blur-xl backdrop-saturate-150 shadow-[0_8px_32px_-4px_rgba(0,0,0,0.15)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.35)]">
          <div className="flex items-start justify-between">
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="size-5 rounded-full" />
          </div>
          <Skeleton className="mt-3 h-7 w-16" />
          <Skeleton className="mt-2 h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

/** Placeholder shaped like a `Card` wrapping a `Table`. */
export function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-border bg-card/45 p-5 backdrop-blur-xl backdrop-saturate-150 shadow-[0_8px_32px_-4px_rgba(0,0,0,0.15)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.35)]", className)}>
      <div className="space-y-4">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex items-center gap-4">
            {Array.from({ length: columns }).map((_, c) => (
              <Skeleton key={c} className={cn("h-3.5", c === 0 ? "w-1/4 flex-none" : "flex-1")} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Placeholder shaped like a chart card (`CardHeader` + a rectangular plot area). */
export function SkeletonChartCard({ height = 240, className }: { height?: number; className?: string }) {
  return (
    <div className={cn("rounded-xl border border-border bg-card/45 p-5 backdrop-blur-xl backdrop-saturate-150 shadow-[0_8px_32px_-4px_rgba(0,0,0,0.15)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.35)]", className)}>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-2 h-3 w-56" />
      <Skeleton className="mt-4 w-full" style={{ height }} />
    </div>
  );
}
