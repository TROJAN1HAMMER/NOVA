import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  // "Blue glass" — translucent primary fill + backdrop blur + a rim-light
  // border, so it reads as frosted rather than a flat solid fill.
  primary:
    "border border-white/15 bg-primary/85 text-primary-foreground backdrop-blur-sm shadow-[0_4px_16px_-4px_rgba(59,130,246,0.5)] hover:-translate-y-0.5 hover:bg-primary/95 hover:shadow-[0_6px_22px_-2px_rgba(59,130,246,0.65)]",
  // "Dark glass" — translucent secondary fill, same blur/lift language.
  secondary:
    "border border-border/70 bg-secondary/70 text-secondary-foreground backdrop-blur-sm hover:-translate-y-0.5 hover:bg-secondary/90 hover:shadow-[0_6px_20px_-4px_rgba(0,0,0,0.25)]",
  outline: "border border-border bg-transparent hover:bg-muted text-foreground",
  ghost: "bg-transparent hover:bg-muted text-foreground",
  danger: "bg-danger text-white hover:opacity-90 shadow-sm",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-base gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", isLoading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex items-center justify-center rounded-lg font-medium transition-[color,background-color,border-color,transform,box-shadow] duration-[250ms] ease-out active:scale-[0.98]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
          "disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100",
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...props}
      >
        {isLoading && <Loader2 className="size-4 animate-spin" />}
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
