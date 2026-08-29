import { lazy, Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { FullPageSpinner } from "../ui/Spinner";
import { useCommandPaletteShortcut } from "../command-palette/useCommandPaletteShortcut";

// Lazy-loaded so its bundle (Fuse.js + the palette UI) only ships once a
// user actually opens it (Ctrl/Cmd+K or the topbar search icon) — never as
// part of the initial authenticated-shell bundle.
const CommandPalette = lazy(() => import("../command-palette/CommandPalette").then((m) => ({ default: m.CommandPalette })));

export function AppShell() {
  // Icon-only rail is the resting state everywhere (desktop included) —
  // expanding it pushes `<main>` over via normal flex reflow (the sidebar
  // is a plain flex sibling, not an overlay), rather than floating on top
  // of the page.
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const location = useLocation();

  // Command palette — state lives here (not in a context) so it follows
  // the same pattern as `sidebarExpanded` below: local state in AppShell,
  // passed down to whichever child needs to read/toggle it.
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteEverOpened, setPaletteEverOpened] = useState(false);
  const openPalette = () => {
    setPaletteEverOpened(true);
    setPaletteOpen(true);
  };
  useCommandPaletteShortcut(openPalette);

  // Collapse back to the icon rail on navigation — adjusting state during
  // render (React's documented alternative to an effect for "reset when a
  // value changes": https://react.dev/learn/you-might-not-need-an-effect)
  // rather than a `useEffect`, so it can't cascade an extra render.
  const [lastPathname, setLastPathname] = useState(location.pathname);
  if (location.pathname !== lastPathname) {
    setLastPathname(location.pathname);
  }

  // Escape collapses the expanded rail, same as clicking its own toggle.
  useEffect(() => {
    if (!sidebarExpanded) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSidebarExpanded(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [sidebarExpanded]);

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        expanded={sidebarExpanded}
        onToggle={() => setSidebarExpanded((current) => !current)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenPalette={openPalette} sidebarExpanded={sidebarExpanded} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 pb-20 sm:pb-24 lg:pb-28">
          <Suspense fallback={<FullPageSpinner />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      {paletteEverOpened && (
        <Suspense fallback={null}>
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
        </Suspense>
      )}
    </div>
  );
}
