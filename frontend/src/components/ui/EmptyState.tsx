import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  const shouldReduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-card/30 p-12 text-center backdrop-blur-xl backdrop-saturate-150"
    >
      {icon && <div className="text-muted-foreground">{icon}</div>}
      <div>
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </motion.div>
  );
}
