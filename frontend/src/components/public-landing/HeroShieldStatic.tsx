import { ShieldCheck } from "lucide-react";

/**
 * Non-animated fallback for the 3D hero shield — shown under
 * `prefers-reduced-motion`, while the 3D chunk is still loading, or if the
 * WebGL scene fails to render (no WebGL support, context creation failure,
 * etc). Deliberately simple: a large glowing shield glyph, consistent with
 * the NOVA mark used everywhere else in the app.
 */
export function HeroShieldStatic() {
  return (
    <div className="flex aspect-square w-full max-w-md items-center justify-center">
      <div className="relative flex items-center justify-center">
        <div className="absolute size-48 rounded-full bg-primary/25 blur-3xl sm:size-64" aria-hidden />
        <ShieldCheck className="relative size-40 text-primary drop-shadow-[0_0_30px_var(--color-primary)] sm:size-52" strokeWidth={1.25} />
      </div>
    </div>
  );
}
