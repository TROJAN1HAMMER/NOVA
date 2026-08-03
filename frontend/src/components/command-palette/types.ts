import type { NavigateFunction } from "react-router-dom";
import type { useToast } from "../../hooks/useToast";

// Section identity drives both grouping/order in the results list and the
// visible section header label — see SECTION_LABELS in CommandPalette.tsx.
export type CommandSection =
  | "recentSearches"
  | "recentlyOpened"
  | "quickActions"
  | "navigation"
  | "knowledge"
  | "activity"
  | "reports"
  // Legacy aliases kept for CommandPalette.tsx compatibility
  | "repositories"
  | "scans"
  | "findings"
  | "compliance";

export interface CommandPerformContext {
  navigate: NavigateFunction;
  toast: ReturnType<typeof useToast>;
  /** Closes the palette. Actions call this themselves so `Enter` vs.
   *  `Ctrl+Enter` (keep-open) can decide whether to call it at all — see
   *  CommandPalette.tsx's `runItem`. */
  close: () => void;
}

export interface CommandItem {
  /** Stable, globally-unique id — used for React keys, aria-activedescendant,
   *  and de-duplicating "recently opened" entries. */
  id: string;
  section: CommandSection;
  title: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  /** Small pill shown at the end of the row — e.g. a severity, a scan
   *  status, a provider name, or a framework short code. */
  badge?: string;
  badgeTone?: "neutral" | "primary" | "success" | "warning" | "danger";
  /** Extra terms Fuse.js should match against that aren't shown on the row
   *  itself (a CVE id, a CWE id, a route alias like "rbac" for the
   *  User Management page, etc). */
  keywords?: string[];
  /** Runs the item's action. Receives `close` so it can decide for itself
   *  whether to dismiss the palette (most navigation/actions do; a
   *  Ctrl+Enter "run without closing" download action does not). */
  perform: (ctx: CommandPerformContext) => void | Promise<void>;
  /** When true, a bare `Enter` also keeps the palette open (used for
   *  actions like "download a report" that a user might repeat several
   *  times in a row). Ctrl+Enter always keeps it open regardless of this
   *  flag — see the keyboard shortcuts table in the palette's header. */
  keepOpenByDefault?: boolean;
}

export interface RecentSearchEntry {
  query: string;
  at: number;
}

export interface RecentlyOpenedEntry {
  id: string;
  title: string;
  subtitle?: string;
  section: CommandSection;
  /** Re-derived at render time from `iconKey` (see recentStore.ts) since
   *  React components can't round-trip through JSON/localStorage. */
  iconKey: RecentlyOpenedIconKey;
  at: number;
}

export type RecentlyOpenedIconKey = "repository" | "scan" | "report" | "page";
