import { NavLink } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  Brain,
  Dna,
  FolderPlus,
  Gauge,
  Menu,
  Network,
  Sparkles,
  UserCog,
  X,
  Zap,
  Shield,
  ShieldAlert,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useAuth } from "../../hooks/useAuth";
import { canAccessRoute, type RouteKey } from "../../lib/rbac";
import { NovaLogo } from "../brand/NovaLogo";

const NAV_ITEMS: { to: string; label: string; icon: typeof Sparkles; routeKey?: RouteKey }[] = [
  { to: "/assistant", label: "Assistant", icon: Sparkles, routeKey: "assistant" },
  { to: "/source-studio", label: "Source Studio", icon: FolderPlus, routeKey: "source-studio" },
  { to: "/knowledge", label: "Knowledge Base", icon: BookOpen, routeKey: "knowledge" },
  { to: "/security-intelligence", label: "Security Intelligence", icon: ShieldAlert, routeKey: "security-intelligence" },
  { to: "/graph-explorer", label: "Graph Explorer", icon: Network, routeKey: "graph-explorer" },
  { to: "/memory", label: "Memory", icon: Brain, routeKey: "memory" },
  { to: "/knowledge-evolution", label: "Knowledge Evolution", icon: Dna, routeKey: "knowledge-evolution" },
  { to: "/rag-operations", label: "RAG Studio", icon: Gauge, routeKey: "rag-operations" },
  { to: "/benchmarks", label: "Benchmarks", icon: Zap, routeKey: "benchmarks" },
  { to: "/executive", label: "Executive Radar", icon: BarChart3, routeKey: "executive" },
  { to: "/admin/users", label: "Administration", icon: UserCog, routeKey: "admin/users" },
];

export function Sidebar({
  expanded,
  onToggle,
}: {
  expanded: boolean;
  onToggle: () => void;
}) {
  const { user } = useAuth();
  const visibleNavItems = NAV_ITEMS.filter(
    (item) => !item.routeKey || canAccessRoute(user?.role, item.routeKey),
  );

  return (
    <aside
      id="app-sidebar"
      aria-label="Main navigation"
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col overflow-hidden border-r border-border/60 bg-card/80 backdrop-blur-md transition-[width] duration-300 ease-out",
        expanded ? "w-64" : "w-16",
      )}
    >
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-border/40 px-3">
        {expanded ? (
          <NovaLogo size="sm" />
        ) : (
          <NovaLogo iconOnly size="sm" />
        )}
        <button
          onClick={onToggle}
          className="relative flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors duration-150 hover:bg-muted"
          aria-label={expanded ? "Collapse navigation" : "Expand navigation"}
        >
          {expanded ? <X className="size-4" /> : <Menu className="size-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden p-2.5">
        {visibleNavItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            aria-label={label}
            title={expanded ? undefined : label}
            className={({ isActive }) =>
              cn(
                "sidebar-nav-link flex w-full items-center overflow-hidden rounded-lg py-2 text-sm font-medium whitespace-nowrap transition-all duration-150 ease-out",
                expanded ? "justify-start gap-3 px-3" : "justify-center px-0",
                isActive
                  ? "is-active bg-primary/10 text-primary border border-primary/20 shadow-xs"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )
            }
          >
            <Icon className="sidebar-nav-icon size-4.5 shrink-0" />
            <span
              className={cn(
                "overflow-hidden transition-all duration-200",
                expanded ? "max-w-40 opacity-100 delay-75" : "max-w-0 opacity-0",
              )}
            >
              {label}
            </span>
          </NavLink>
        ))}
      </nav>

      <div
        className={cn(
          "overflow-hidden whitespace-nowrap border-t border-border/40 p-3 text-[11px] font-medium text-muted-foreground transition-opacity duration-200",
          expanded ? "opacity-100 delay-100" : "opacity-0",
        )}
      >
        <span className="block font-semibold text-foreground">AEKOF Research Platform</span>
        Enterprise Intelligence. Evolving.
      </div>
    </aside>
  );
}
