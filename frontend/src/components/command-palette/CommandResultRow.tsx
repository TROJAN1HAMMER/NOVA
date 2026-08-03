import { ChevronRight } from "lucide-react";
import { Badge } from "../ui/Badge";
import { cn } from "../../lib/utils";
import type { CommandItem } from "./types";

export function CommandResultRow({
  item,
  active,
  optionId,
  onSelect,
  onHover,
}: {
  item: CommandItem;
  active: boolean;
  optionId: string;
  onSelect: () => void;
  onHover: () => void;
}) {
  const Icon = item.icon;

  return (
    <div
      id={optionId}
      role="option"
      aria-selected={active}
      onMouseEnter={onHover}
      onMouseDown={(e) => {
        // Prevent the input from losing focus (which would otherwise fire
        // right before the click handler and briefly flash the empty state).
        e.preventDefault();
      }}
      onClick={onSelect}
      className={cn(
        "group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 transition-colors duration-100",
        active ? "bg-accent" : "hover:bg-muted",
      )}
      style={active ? { boxShadow: "0 0 0 1px rgba(59,130,246,0.35), 0 0 14px rgba(59,130,246,0.18)" } : undefined}
    >
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-card transition-transform duration-150",
          active && "scale-105 border-primary/40",
        )}
      >
        <Icon className={cn("size-4 text-muted-foreground", active && "text-primary")} />
      </div>

      <div className="min-w-0 flex-1">
        <p className={cn("truncate text-sm font-medium", active ? "text-accent-foreground" : "text-foreground")}>
          {item.title}
        </p>
        {item.subtitle && (
          <p className="truncate text-xs text-muted-foreground">{item.subtitle}</p>
        )}
      </div>

      {item.badge && (
        <Badge tone={item.badgeTone ?? "neutral"} className="shrink-0 capitalize">
          {item.badge}
        </Badge>
      )}

      <ChevronRight
        className={cn(
          "size-4 shrink-0 text-muted-foreground/50 transition-transform duration-150",
          active && "translate-x-0.5 text-primary",
        )}
      />
    </div>
  );
}
