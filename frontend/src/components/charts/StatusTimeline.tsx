import { Fragment } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Check, X } from "lucide-react";
import { cn } from "../../lib/utils";

export interface TimelineStep {
  key: string;
  label: string;
  description?: string;
  status: "complete" | "current" | "pending" | "error";
}

/** Horizontal stepper — completed steps get a green check, the active step
 *  pulses blue (reusing the existing `.animate-pulse-slow` "in progress"
 *  treatment), future steps stay a hollow grey ring. Connector fill
 *  animates in as progress advances rather than snapping to full width. */
export function StatusTimeline({ steps, className }: { steps: TimelineStep[]; className?: string }) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className={cn("flex w-full items-start", className)}>
      {steps.map((step, index) => (
        <Fragment key={step.key}>
          <div className="flex flex-col items-center gap-2" style={{ minWidth: 88 }}>
            <StepDot status={step.status} />
            <div className="text-center">
              <div className={cn("text-xs font-medium", step.status === "pending" ? "text-muted-foreground" : "text-foreground")}>{step.label}</div>
              {step.description && <div className="mt-0.5 text-[11px] text-muted-foreground">{step.description}</div>}
            </div>
          </div>

          {index < steps.length - 1 && (
            <div className="relative mt-3 h-0.5 flex-1 shrink overflow-hidden rounded-full bg-muted" style={{ minWidth: 24 }}>
              <motion.div
                className="absolute inset-y-0 left-0 rounded-full bg-success"
                initial={false}
                animate={{ width: step.status === "complete" ? "100%" : "0%" }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.5, ease: "easeOut" }}
              />
            </div>
          )}
        </Fragment>
      ))}
    </div>
  );
}

function StepDot({ status }: { status: TimelineStep["status"] }) {
  if (status === "complete") {
    return (
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-success text-white">
        <Check className="size-3.5" />
      </span>
    );
  }
  if (status === "current") {
    return (
      <span className="relative flex size-6 shrink-0 items-center justify-center rounded-full bg-primary">
        <span className="absolute inset-0 animate-pulse-slow rounded-full bg-primary" />
        <span className="relative size-2 rounded-full bg-primary-foreground" />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-danger text-white">
        <X className="size-3.5" />
      </span>
    );
  }
  return <span className="size-6 shrink-0 rounded-full border-2 border-border bg-card" />;
}
