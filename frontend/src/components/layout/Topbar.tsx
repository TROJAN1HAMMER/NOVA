import { useState } from "react";
import { LogOut, Search } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { ThemeToggle } from "./ThemeToggle";
import { Button } from "../ui/Button";
import { cn } from "../../lib/utils";

export function Topbar({
  onOpenPalette,
  sidebarExpanded,
}: {
  onOpenPalette: () => void;
  sidebarExpanded: boolean;
}) {
  const { user, logout } = useAuth();
  const [isMac] = useState(() => /mac|iphone|ipad|ipod/i.test(window.navigator.userAgent));

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border/40 bg-card/70 pr-4 backdrop-blur-md sm:pr-6",
        sidebarExpanded ? "pl-4 sm:pl-6" : "pl-3",
      )}
    >
      <div className="flex flex-1 justify-center sm:justify-start">
        <button
          onClick={onOpenPalette}
          aria-label="Open command palette"
          className="flex w-full max-w-sm items-center gap-2 rounded-lg border border-border/60 bg-background/50 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <span className="hidden truncate sm:inline">Search NOVA Intelligence…</span>
          <kbd className="ml-auto hidden shrink-0 items-center gap-0.5 rounded border border-border bg-muted px-1.5 py-0.5 font-sans text-[10px] font-medium sm:inline-flex">
            {isMac ? "⌘" : "Ctrl"}
            <span>K</span>
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user && (
          <div className="hidden items-center gap-2.5 sm:flex">
            <div className="flex size-8 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary border border-primary/30">
              {user.full_name?.[0]?.toUpperCase() ?? user.email[0].toUpperCase()}
            </div>
            <div className="leading-tight">
              <p className="text-sm font-medium text-foreground">{user.full_name || user.email}</p>
              <p className="text-[11px] font-medium text-muted-foreground">{user.role_display_name}</p>
            </div>
          </div>
        )}
        <Button variant="ghost" size="sm" className="h-9 w-9 p-0" onClick={logout} aria-label="Log out">
          <LogOut className="size-4" />
        </Button>
      </div>
    </header>
  );
}
