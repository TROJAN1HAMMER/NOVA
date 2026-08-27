import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Brain,
  Database,
  FileJson,
  FileSpreadsheet,
  FileText,
  Layers,
  Network,
  Search,
  Zap,
} from "lucide-react";
import { knowledgeApi, type KnowledgeDocumentListParams } from "../../lib/api/knowledge";
import { reportsApi } from "../../lib/api/reports";
import { queryKeys } from "../../lib/queryClient";
import { usePermissions } from "../../hooks/usePermissions";
import { useToast } from "../../hooks/useToast";
import { formatRelativeTime } from "../../lib/utils";
import type { ReportType } from "../../types/api";
import type { CommandItem, CommandPerformContext } from "./types";

const REPORT_LABELS: Record<ReportType, string> = {
  pdf: "Knowledge Summary (PDF)",
  json: "Knowledge Export (JSON)",
  csv: "Knowledge Export (CSV)",
  knowledge_summary: "Full Knowledge Report",
};

const REPORT_ICONS: Record<ReportType, CommandItem["icon"]> = {
  pdf: FileText,
  json: FileJson,
  csv: FileSpreadsheet,
  knowledge_summary: Brain,
};

const REPORT_TYPES: ReportType[] = ["pdf", "json", "csv", "knowledge_summary"];

const STATUS_BADGE_TONE: Record<string, CommandItem["badgeTone"]> = {
  queued: "neutral",
  pending: "neutral",
  processing: "primary",
  running: "primary",
  indexed: "success",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

const DOC_TYPE_ICONS: Record<string, CommandItem["icon"]> = {
  pdf: FileText,
  markdown: FileText,
  text: FileText,
  docx: FileText,
  json: FileJson,
  csv: FileSpreadsheet,
  url: Network,
  git: Database,
  zip: Layers,
};

const listParams: KnowledgeDocumentListParams = { limit: 50 };

/**
 * Aggregates NOVA-native command palette data from the knowledge base.
 * Shows recent knowledge documents, indexed sources, and report download
 * commands. Replaces the legacy scan/finding/compliance command data.
 */
export function useCommandPaletteData(enabled: boolean) {
  const { hasPermission } = usePermissions();
  const toast = useToast();
  const canDownloadReports = hasPermission("report:download");

  const documentsQuery = useQuery({
    queryKey: queryKeys.knowledgeDocuments(listParams),
    queryFn: () => knowledgeApi.listDocuments(listParams),
    enabled,
  });

  const recentIndexed = useMemo(
    () =>
      (documentsQuery.data?.documents ?? [])
        .filter((d) => d.status === "indexed")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .slice(0, 10),
    [documentsQuery.data],
  );

  const recentProcessing = useMemo(
    () =>
      (documentsQuery.data?.documents ?? []).filter(
        (d) => d.status === "processing" || d.status === "pending",
      ),
    [documentsQuery.data],
  );

  const downloadReport = async (
    operationId: string,
    label: string,
    type: ReportType,
    perfCtx: CommandPerformContext,
  ) => {
    try {
      await reportsApi.download(operationId, type, `${label}-${type}`);
      toast.success(`${REPORT_LABELS[type]} downloaded`, label);
    } catch (error) {
      toast.error("Download failed", error instanceof Error ? error.message : "Please try again.");
    }
    perfCtx.close();
  };

  // Document items — recently indexed knowledge sources
  const documentItems = useMemo<CommandItem[]>(
    () =>
      recentIndexed.map((doc) => ({
        id: `doc:${doc.id}`,
        section: "knowledge" as const,
        title: doc.filename,
        subtitle: `${doc.document_type.toUpperCase()} · ${doc.chunk_count} chunks · ${formatRelativeTime(doc.created_at)}`,
        icon: DOC_TYPE_ICONS[doc.document_type] ?? FileText,
        badge: doc.status,
        badgeTone: STATUS_BADGE_TONE[doc.status] ?? "neutral",
        keywords: [doc.document_type, ...(doc.tags ?? []), doc.author ?? "", doc.version],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/source-studio");
          close();
        },
      })),
    [recentIndexed],
  );

  // Processing items — in-flight knowledge jobs
  const processingItems = useMemo<CommandItem[]>(
    () =>
      recentProcessing.map((doc) => ({
        id: `processing:${doc.id}`,
        section: "activity" as const,
        title: doc.filename,
        subtitle: `${doc.document_type.toUpperCase()} · Processing…`,
        icon: Zap,
        badge: doc.status,
        badgeTone: STATUS_BADGE_TONE[doc.status] ?? "primary",
        keywords: [doc.document_type, "processing", "ingesting"],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/source-studio");
          close();
        },
      })),
    [recentProcessing],
  );

  // Quick-access NOVA navigation items (always shown)
  const quickNavItems = useMemo<CommandItem[]>(
    () => [
      {
        id: "nav:source-studio",
        section: "navigation" as const,
        title: "Source Studio",
        subtitle: "Ingest new knowledge sources",
        icon: Database,
        keywords: ["source studio", "source", "studio", "upload", "ingest", "import", "knowledge"],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/source-studio");
          close();
        },
      },
      {
        id: "nav:assistant",
        section: "navigation" as const,
        title: "AI Assistant",
        subtitle: "Ask questions from your knowledge base",
        icon: Brain,
        keywords: ["assistant", "chat", "ask", "query", "question"],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/assistant");
          close();
        },
      },
      {
        id: "nav:graph",
        section: "navigation" as const,
        title: "Knowledge Graph",
        subtitle: "Explore entity relationships",
        icon: Network,
        keywords: ["graph", "entities", "relations", "knowledge graph", "graph explorer"],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/graph-explorer");
          close();
        },
      },
      {
        id: "nav:knowledge",
        section: "navigation" as const,
        title: "Knowledge Base",
        subtitle: "Corpus documents, search & instant FAQ rules",
        icon: Search,
        keywords: ["knowledge", "knowledge base", "search", "find", "semantic", "faq", "docs"],
        perform: ({ navigate, close }: CommandPerformContext) => {
          navigate("/knowledge");
          close();
        },
      },
    ],
    [],
  );

  // Report download items
  const reportItems = useMemo<CommandItem[]>(() => {
    if (!canDownloadReports) return [];
    return REPORT_TYPES.map((type) => ({
      id: `report:${type}`,
      section: "reports" as const,
      title: REPORT_LABELS[type],
      subtitle: "Download knowledge report",
      icon: REPORT_ICONS[type],
      badge: "Download",
      badgeTone: "neutral" as const,
      keywords: [type, "report", "download", "export"],
      keepOpenByDefault: true,
      perform: (perfCtx: CommandPerformContext) =>
        downloadReport("latest", "knowledge-base", type, perfCtx),
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDownloadReports]);

  return {
    documentItems,
    processingItems,
    quickNavItems,
    reportItems,
    // Legacy-compatible aliases so CommandPalette.tsx doesn't need touching
    repositoryItems: [] as CommandItem[],
    scanItems: [] as CommandItem[],
    findingItems: [] as CommandItem[],
    complianceItems: [] as CommandItem[],
    isLoadingInitial: enabled && documentsQuery.isLoading,
    isLoadingDeep: false,
    mostRecentCompletedScanId: undefined as string | undefined,
    mostRecentCompletedScanLabel: undefined as string | undefined,
    downloadReport: (_id: string, _label: string, perfCtx: CommandPerformContext) =>
      downloadReport("latest", "knowledge-base", "pdf", perfCtx),
  };
}

export const DEEP_SCAN_WINDOW_SIZE = 0;
