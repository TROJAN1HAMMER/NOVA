import type { CommandItem, RecentSearchEntry, RecentlyOpenedEntry, RecentlyOpenedIconKey } from "./types";

// Plain localStorage (not IndexedDB/a backend endpoint) — this is
// per-browser convenience state, not data NOVA needs to sync anywhere,
// so it deliberately has no server-side counterpart.
const SEARCHES_KEY = "NOVA.commandPalette.recentSearches";
const OPENED_KEY = "NOVA.commandPalette.recentlyOpened";
const MAX_SEARCHES = 10;
const MAX_OPENED = 10;

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as T;
    return parsed ?? fallback;
  } catch {
    // Storage disabled (private browsing, quota, corrupted JSON) — the
    // palette should still work, it just won't remember anything.
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Fail silently/open — same rationale as readJson above.
  }
}

export function getRecentSearches(): RecentSearchEntry[] {
  return readJson<RecentSearchEntry[]>(SEARCHES_KEY, []);
}

export function addRecentSearch(query: string): void {
  const trimmed = query.trim();
  if (trimmed.length < 2) return; // don't clutter history with "a", "an" etc.
  const existing = getRecentSearches().filter((e) => e.query.toLowerCase() !== trimmed.toLowerCase());
  const next = [{ query: trimmed, at: Date.now() }, ...existing].slice(0, MAX_SEARCHES);
  writeJson(SEARCHES_KEY, next);
}

export function clearRecentSearches(): void {
  writeJson(SEARCHES_KEY, []);
}

export function getRecentlyOpened(): RecentlyOpenedEntry[] {
  return readJson<RecentlyOpenedEntry[]>(OPENED_KEY, []);
}

const ICON_KEY_BY_SECTION: Partial<Record<CommandItem["section"], RecentlyOpenedIconKey>> = {
  repositories: "repository",
  scans: "scan",
  reports: "report",
};

export function recordRecentlyOpened(item: CommandItem): void {
  const iconKey: RecentlyOpenedIconKey = ICON_KEY_BY_SECTION[item.section] ?? "page";
  const existing = getRecentlyOpened().filter((e) => e.id !== item.id);
  const next: RecentlyOpenedEntry[] = [
    { id: item.id, title: item.title, subtitle: item.subtitle, section: item.section, iconKey, at: Date.now() },
    ...existing,
  ].slice(0, MAX_OPENED);
  writeJson(OPENED_KEY, next);
}
