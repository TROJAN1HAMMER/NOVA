import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "./Button";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  size?: "md" | "lg" | "xl";
}

const sizeClasses = {
  md: "max-w-md",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Modal({ open, onClose, title, children, size = "md" }: ModalProps) {
  const shouldReduceMotion = useReducedMotion();

  // Every caller in this app keeps its <Modal> mounted permanently and only
  // toggles `open` (rather than conditionally rendering <Modal> itself), and
  // several of them derive `title`/`children` from state that goes away in
  // the same tick as `onClose` fires (e.g. `finding?.title` /
  // `{finding && <FindingDetailModal/>}`). Without this cache, the exit
  // animation below would fade out a suddenly-blank dialog instead of the
  // content the user was just looking at. This mirrors `title`/`children`
  // while open and simply stops updating the instant `open` goes false, so
  // the close transition always shows the last real content.
  const [cached, setCached] = useState({ title, children });
  // Deliberately not a useEffect: this mirrors title/children into `cached`
  // *during render* (React's sanctioned "adjust state while rendering"
  // pattern) so the frozen values are already in place for this same
  // render's JSX below — an effect would only catch up a render late,
  // which is exactly the flash this cache exists to prevent.
  if (open && (cached.title !== title || cached.children !== children)) {
    setCached({ title, children });
  }

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={shouldReduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: shouldReduceMotion ? 0 : 0.16, ease: "easeOut" }}
        >
          <motion.div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={shouldReduceMotion ? false : { opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.18, ease: "easeOut" }}
            className={cn(
              "relative w-full overflow-hidden rounded-xl border border-border bg-card/70 text-card-foreground",
              "backdrop-blur-2xl backdrop-saturate-150 shadow-[0_20px_60px_-10px_rgba(0,0,0,0.35)]",
              "dark:shadow-[0_20px_60px_-8px_rgba(0,0,0,0.6)]",
              sizeClasses[size],
            )}
          >
            {cached.title && (
              <div className="flex items-center justify-between border-b border-border p-4">
                <h2 className="text-sm font-semibold">{cached.title}</h2>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onClose} aria-label="Close">
                  <X className="size-4" />
                </Button>
              </div>
            )}
            <div className="max-h-[75vh] overflow-y-auto p-5">{cached.children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
