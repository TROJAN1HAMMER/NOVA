import {
  Activity,
  BarChart3,
  BookOpen,
  Brain,
  Dna,
  Gauge,
  Moon,
  Network,
  Sparkles,
  Sun,
  UserCog,
  Zap,
} from "lucide-react";
import { canAccessRoute, type RouteKey } from "../../lib/rbac";
import type { UserRole } from "../../types/api";
import type { CommandItem, CommandPerformContext } from "./types";

function buildNavigationItems(role: UserRole | undefined | null): CommandItem[] {
  const defs: {
    routeKey: RouteKey;
    to: string;
    title: string;
    subtitle: string;
    icon: CommandItem["icon"];
    keywords: string[];
  }[] = [
    { routeKey: "assistant", to: "/assistant", title: "Assistant", subtitle: "Intelligence chat workspace", icon: Sparkles, keywords: ["assistant", "chat", "ai"] },
    { routeKey: "knowledge", to: "/knowledge", title: "Knowledge Base", subtitle: "Corpus documents & instant FAQ rules", icon: BookOpen, keywords: ["knowledge base", "docs", "upload", "rag"] },
    { routeKey: "graph-explorer", to: "/graph-explorer", title: "Graph Explorer", subtitle: "GraphRAG entity-relation visualization", icon: Network, keywords: ["graph", "entities", "triples"] },
    { routeKey: "memory", to: "/memory", title: "Memory", subtitle: "5-layer enterprise memory engine", icon: Brain, keywords: ["memory", "context", "history"] },
    { routeKey: "knowledge-evolution", to: "/knowledge-evolution", title: "Knowledge Evolution", subtitle: "Outer-loop self-healing gap inbox", icon: Dna, keywords: ["evolution", "gaps", "self-healing"] },
    { routeKey: "rag-operations", to: "/rag-operations", title: "RAG Studio", subtitle: "Prompt & hyperparameter simulator", icon: Gauge, keywords: ["rag", "studio", "simulator"] },
    { routeKey: "benchmarks", to: "/benchmarks", title: "Benchmarks", subtitle: "11-baseline comparison evaluation", icon: Zap, keywords: ["benchmarks", "ablation", "eval"] },
    { routeKey: "executive", to: "/executive", title: "Executive Radar", subtitle: "High-level intelligence rollup", icon: BarChart3, keywords: ["summary", "executive", "radar"] },
    { routeKey: "my-activity", to: "/my-activity", title: "My Activity", subtitle: "Your activity history", icon: Activity, keywords: ["activity", "history"] },
    { routeKey: "admin/users", to: "/admin/users", title: "Administration", subtitle: "User roles & platform audit log", icon: UserCog, keywords: ["users", "admin", "audit log"] },
  ];

  return defs
    .filter((d) => canAccessRoute(role, d.routeKey))
    .map((d) => ({
      id: `nav:${d.routeKey}`,
      section: "navigation" as const,
      title: d.title,
      subtitle: d.subtitle,
      icon: d.icon,
      badge: "Nav",
      badgeTone: "neutral" as const,
      keywords: d.keywords,
      perform: ({ navigate, close }: CommandPerformContext) => {
        navigate(d.to);
        close();
      },
    }));
}

interface QuickActionContext {
  role: UserRole | undefined | null;
  hasPermission: (permission: string) => boolean;
  theme: "light" | "dark";
  toggleTheme: () => void;
  mostRecentCompletedScanId: string | undefined;
  mostRecentCompletedScanLabel: string | undefined;
  downloadReport: (scanJobId: string, label: string, ctx: CommandPerformContext) => Promise<void>;
}

function buildQuickActions(ctx: QuickActionContext): CommandItem[] {
  const items: CommandItem[] = [];

  if (canAccessRoute(ctx.role, "assistant")) {
    items.push({
      id: "action:ai-assistant",
      section: "quickActions",
      title: "Assistant Chat",
      subtitle: "Ask questions grounded in knowledge base documents",
      icon: Sparkles,
      badge: "Action",
      badgeTone: "primary",
      keywords: ["assistant", "chat", "ai", "ask"],
      perform: ({ navigate, close }) => {
        navigate("/assistant");
        close();
      },
    });
  }

  if (canAccessRoute(ctx.role, "knowledge")) {
    items.push({
      id: "action:knowledge-base",
      section: "quickActions",
      title: "Knowledge Base & FAQ Rules",
      subtitle: "Upload documents & configure instant FAQ rules",
      icon: BookOpen,
      badge: "Action",
      badgeTone: "primary",
      keywords: ["knowledge", "docs", "upload", "rag", "faq"],
      perform: ({ navigate, close }) => {
        navigate("/knowledge");
        close();
      },
    });
  }

  if (canAccessRoute(ctx.role, "admin/users")) {
    items.push({
      id: "action:manage-users",
      section: "quickActions",
      title: "Manage Users",
      subtitle: "Roles, access, and audit log",
      icon: UserCog,
      badge: "Action",
      badgeTone: "primary",
      keywords: ["users", "admin", "audit log"],
      perform: ({ navigate, close }) => {
        navigate("/admin/users");
        close();
      },
    });
  }

  items.push({
    id: "action:toggle-theme",
    section: "quickActions",
    title: ctx.theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode",
    subtitle: "Toggle appearance",
    icon: ctx.theme === "dark" ? Sun : Moon,
    badge: "Action",
    badgeTone: "neutral",
    keywords: ["theme", "dark mode", "light mode", "appearance"],
    keepOpenByDefault: true,
    perform: ({ close }) => {
      ctx.toggleTheme();
      close();
    },
  });

  return items;
}

export { buildNavigationItems, buildQuickActions };
