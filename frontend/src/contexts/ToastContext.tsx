import { createContext, useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { ToastViewport } from "../components/ui/Toast";

export type ToastTone = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastItem, "id">) => void;
  dismissToast: (id: string) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const ToastContext = createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 4500;

/**
 * Minimal in-house toast system — there was no notification system
 * anywhere in the app before this. Renders a fixed-corner stack via
 * `ToastViewport`, animated in/out with framer-motion. Kept deliberately
 * small: no queueing limits, no promise helpers, no toast library — just a
 * context, a hook (`useToast`), and a container, which is all the two real
 * call sites (scan cancellation, admin role/status changes) need.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const showToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { ...toast, id }]);
      const timer = setTimeout(() => dismissToast(id), AUTO_DISMISS_MS);
      timers.current.set(id, timer);
    },
    [dismissToast],
  );

  const value = useMemo(() => ({ showToast, dismissToast }), [showToast, dismissToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}
