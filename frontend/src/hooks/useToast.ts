import { useContext } from "react";
import { ToastContext } from "../contexts/ToastContext";

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  const { showToast, dismissToast } = ctx;
  return {
    show: showToast,
    dismiss: dismissToast,
    success: (title: string, description?: string) => showToast({ tone: "success", title, description }),
    error: (title: string, description?: string) => showToast({ tone: "error", title, description }),
    info: (title: string, description?: string) => showToast({ tone: "info", title, description }),
  };
}
