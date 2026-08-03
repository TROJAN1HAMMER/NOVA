import { motion, useReducedMotion } from "framer-motion";
import { cn } from "../../lib/utils";

type Tone = "primary" | "success" | "warning" | "danger";

// Unfilled track is a lighter step of the same ramp (blue-on-blue, etc.) so
// state reads across the whole bar, not just the filled portion; the fill
// itself gets a subtle two-stop gradient toward a lighter tint of the same
// hue rather than a flat block.
const TONE_STYLES: Record<Tone, { track: string; gradient: string }> = {
  primary: {
    track: "bg-primary/15",
    gradient: "linear-gradient(90deg, var(--color-primary) 0%, color-mix(in srgb, var(--color-primary) 60%, white) 100%)",
  },
  success: {
    track: "bg-success/15",
    gradient: "linear-gradient(90deg, var(--color-success) 0%, color-mix(in srgb, var(--color-success) 60%, white) 100%)",
  },
  warning: {
    track: "bg-warning/15",
    gradient: "linear-gradient(90deg, var(--color-warning) 0%, color-mix(in srgb, var(--color-warning) 60%, white) 100%)",
  },
  danger: {
    track: "bg-danger/15",
    gradient: "linear-gradient(90deg, var(--color-danger) 0%, color-mix(in srgb, var(--color-danger) 60%, white) 100%)",
  },
};

export function ProgressBar({
  value,
  className,
  tone = "primary",
}: {
  value: number;
  className?: string;
  tone?: Tone;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const shouldReduceMotion = useReducedMotion();
  const style = TONE_STYLES[tone];

  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full", style.track, className)}>
      <motion.div
        className="h-full rounded-full"
        style={{ background: style.gradient }}
        initial={false}
        animate={{ width: `${clamped}%` }}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.6, ease: "easeOut" }}
      />
    </div>
  );
}
