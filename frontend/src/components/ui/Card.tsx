import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";
import { useCardSpotlight, CARD_SPOTLIGHT_DIAMETER_PX } from "../../hooks/useCardSpotlight";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /**
   * Extra lift/scale on hover for cards that are themselves clickable or
   * link-like — e.g. a callout card that navigates somewhere on click.
   * Every card gets the glass base + a gentle hover reaction regardless
   * (see the module-level styles below); this only adds the *stronger*
   * affordance for genuinely interactive ones, matching this prop's
   * original purpose.
   */
  interactive?: boolean;
}

/**
 * Glassmorphism card — translucent `bg-card` + backdrop blur (so it reads
 * as frosted glass over whatever's behind it, tinted by the active theme's
 * own `--color-card` rather than a hardcoded dark value — this keeps light
 * mode looking intentional instead of muddy). `overflow-hidden` is required
 * for the blur/glow to stay inside the rounded corners; if a future card
 * needs a popover that escapes its bounds, render that popover in a portal
 * rather than removing this.
 */
export function Card({ className, interactive, children, ...props }: CardProps) {
  const { containerRef, glowRef } = useCardSpotlight();

  return (
    <div
      ref={containerRef}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-border bg-card/45 text-card-foreground",
        "backdrop-blur-xl backdrop-saturate-150 shadow-[0_8px_32px_-4px_rgba(0,0,0,0.15)]",
        "transition-[transform,box-shadow,border-color,background-color] duration-[250ms] ease-out",
        "hover:-translate-y-1 hover:border-primary/25 hover:bg-card/60",
        "hover:shadow-[0_10px_40px_-6px_rgba(0,0,0,0.2),0_0_32px_-10px_rgba(59,130,246,0.35)]",
        "dark:shadow-[0_8px_32px_rgba(0,0,0,0.35)]",
        "dark:hover:shadow-[0_10px_40px_rgba(0,0,0,0.45),0_0_32px_-10px_rgba(59,130,246,0.4)]",
        interactive && "hover:scale-[1.01]",
        className,
      )}
      {...props}
    >
      {/* Mouse-follow highlight — a hint of light reflecting off glass, not
          a spotlight. Sits above the blurred backdrop but below `children`
          via z-index/paint order (children render after in the same
          stacking context, so they sit on top by DOM order alone). */}
      <div
        ref={glowRef}
        aria-hidden
        className="pointer-events-none absolute left-0 top-0 z-0 opacity-0 transition-opacity duration-300 ease-out"
        style={{
          width: CARD_SPOTLIGHT_DIAMETER_PX,
          height: CARD_SPOTLIGHT_DIAMETER_PX,
          background:
            "radial-gradient(circle, rgba(255,255,255,0.10) 0%, rgba(59,130,246,0.07) 45%, transparent 75%)",
          willChange: "transform",
        }}
      />
      <div className="relative z-[1]">{children}</div>
    </div>
  );
}

export function CardHeader({
  className,
  title,
  description,
  action,
  ...props
}: HTMLAttributes<HTMLDivElement> & { title?: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 p-5 pb-0", className)} {...props}>
      <div>
        {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}
        {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}
