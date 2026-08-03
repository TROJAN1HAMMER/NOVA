import { cn } from "../../lib/utils";

interface NovaLogoProps {
  className?: string;
  iconOnly?: boolean;
  size?: "sm" | "md" | "lg";
}

export function NovaLogo({ className, iconOnly = false, size = "md" }: NovaLogoProps) {
  const iconSizes = {
    sm: "size-6",
    md: "size-8",
    lg: "size-10",
  };

  const textSizes = {
    sm: "text-base",
    md: "text-lg",
    lg: "text-2xl",
  };

  return (
    <div className={cn("inline-flex items-center gap-2.5 font-semibold tracking-tight", className)}>
      <div className={cn("relative flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-blue-600 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20", iconSizes[size])}>
        <div className="flex size-full items-center justify-center rounded-[10px] bg-background/90 backdrop-blur-xs">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="size-3/4 text-indigo-400 animate-pulse"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M12 3v3" />
            <path d="M12 18v3" />
            <path d="M3 12h3" />
            <path d="M18 12h3" />
            <path d="M5.6 5.6l2.1 2.1" />
            <path d="M16.3 16.3l2.1 2.1" />
            <path d="M5.6 18.4l2.1-2.1" />
            <path d="M16.3 7.7l2.1-2.1" />
          </svg>
        </div>
      </div>

      {!iconOnly && (
        <div className="flex flex-col leading-none">
          <span className={cn("font-extrabold tracking-wider bg-gradient-to-r from-foreground via-indigo-200 to-cyan-300 bg-clip-text text-transparent", textSizes[size])}>
            NOVA
          </span>
          <span className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase mt-0.5">
            Neural Vector Assistant
          </span>
        </div>
      )}
    </div>
  );
}
