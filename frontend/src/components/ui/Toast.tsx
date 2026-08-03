import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import type { ToastItem } from "../../contexts/ToastContext";

const TONE_ICON = { success: CheckCircle2, error: XCircle, info: Info } as const;

const TONE_CLASSES: Record<ToastItem["tone"], string> = {
  success: "border-success/30 text-foreground [&_.toast-icon]:text-success",
  error: "border-danger/30 text-foreground [&_.toast-icon]:text-danger",
  info: "border-border text-foreground [&_.toast-icon]:text-muted-foreground",
};

export function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-stretch gap-2 p-4 sm:inset-x-auto sm:right-0 sm:items-end">
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const Icon = TONE_ICON[t.tone];
          return (
            <motion.div
              key={t.id}
              layout
              initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: shouldReduceMotion ? 0.1 : 0.2, ease: "easeOut" }}
              role="status"
              className={cn(
                "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border bg-card p-3.5 shadow-lg",
                TONE_CLASSES[t.tone],
              )}
            >
              <Icon className="toast-icon mt-0.5 size-4 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{t.title}</p>
                {t.description && <p className="mt-0.5 text-xs text-muted-foreground">{t.description}</p>}
              </div>
              <button
                onClick={() => onDismiss(t.id)}
                className="shrink-0 rounded-md p-0.5 text-muted-foreground/70 hover:text-foreground"
                aria-label="Dismiss notification"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
