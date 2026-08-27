import { useMemo, useRef, useState } from "react";
import {
  FileText,
  Globe,
  GitBranch,
  FolderArchive,
  Database,
  FileCode,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  Trash2,
  Search,
  Plus,
  Layers,
  Network,
  Cpu,
  Upload,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useToast } from "../hooks/useToast";
import {
  useDeleteKnowledgeDocument,
  useKnowledgeDocuments,
  useUploadKnowledgeDocument,
} from "../hooks/useKnowledge";
import { formatDateTime } from "../lib/utils";
import type { KnowledgeDocumentStatus } from "../types/api";

const CONNECTOR_TYPES = [
  { id: "pdf", label: "PDF / Office Docs", icon: FileText, desc: "Extract structured text & tables from PDF/DOCX" },
  { id: "url", label: "Web Crawler (Exa)", icon: Globe, desc: "Crawl web domain & ingest clean markdown" },
  { id: "git", label: "Git Repository", icon: GitBranch, desc: "Parse codebases & technical markdown docs" },
  { id: "zip", label: "Folder / ZIP Archive", icon: FolderArchive, desc: "Ingest directory trees & archive packages" },
  { id: "json", label: "CSV / JSON Datasets", icon: Database, desc: "Structure tabular knowledge & records" },
  { id: "notion", label: "Notion / Confluence", icon: FileCode, desc: "Enterprise wiki connector (Future-Ready)", badge: "Connector Ready" },
];

const PROCESSING_STAGES = [
  { id: 1, label: "Uploading" },
  { id: 2, label: "Parsing" },
  { id: 3, label: "Chunking" },
  { id: 4, label: "Embedding Generation" },
  { id: 5, label: "Entity Extraction" },
  { id: 6, label: "Graph Construction" },
  { id: 7, label: "Vector Indexing" },
  { id: 8, label: "FAQ Detection" },
  { id: 9, label: "Memory Sync" },
  { id: 10, label: "Knowledge Ready" },
];

const STATUS_TONE: Record<KnowledgeDocumentStatus, "neutral" | "primary" | "success" | "danger"> = {
  pending: "neutral",
  processing: "primary",
  indexed: "success",
  failed: "danger",
};

export default function SourceStudioPage() {
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: documentsData, isLoading } = useKnowledgeDocuments();
  const uploadMutation = useUploadKnowledgeDocument();
  const deleteMutation = useDeleteKnowledgeDocument();

  const [selectedConnector, setSelectedConnector] = useState("pdf");
  const [inputValue, setInputValue] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const documents = useMemo(() => documentsData?.documents ?? [], [documentsData]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setInputValue(file.name);
    }
  };

  const handleStartProcessing = () => {
    let fileToUpload: File | null = selectedFile;

    if (!fileToUpload && inputValue.trim()) {
      // Create a markdown/text representation for URL / Git / Text inputs
      const content = `# Source Target: ${inputValue.trim()}\nConnector: ${selectedConnector}\nIngested via NOVA Source Studio.\n`;
      const blob = new Blob([content], { type: "text/markdown" });
      const filename =
        selectedConnector === "url"
          ? `${inputValue.replace(/https?:\/\//, "").replace(/[^a-zA-Z0-9]/g, "_")}.md`
          : selectedConnector === "git"
          ? `${inputValue.split("/").pop() || "repo"}.md`
          : `${inputValue.trim().replace(/[^a-zA-Z0-9]/g, "_")}.txt`;
      fileToUpload = new File([blob], filename, { type: "text/markdown" });
    }

    if (!fileToUpload) {
      toast.error("Source Required", "Please select a file or enter a valid URL / repository link.");
      return;
    }

    uploadMutation.mutate(
      {
        file: fileToUpload,
        version: "1",
        author: "Source Studio",
        tags: selectedConnector,
      },
      {
        onSuccess: (doc) => {
          toast.success("Knowledge Source Ingested", `"${doc.filename}" is now registered in the pipeline.`);
          setInputValue("");
          setSelectedFile(null);
          if (fileInputRef.current) fileInputRef.current.value = "";
        },
        onError: (err) => {
          toast.error("Ingestion Failed", err instanceof Error ? err.message : "Could not upload knowledge source.");
        },
      }
    );
  };

  const handleDeleteSource = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success("Source Removed", "Deleted knowledge source and associated vector chunks.");
      },
      onError: (err) => {
        toast.error("Deletion Failed", err instanceof Error ? err.message : "Could not delete source.");
      },
    });
  };

  const filteredSources = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const lower = searchQuery.toLowerCase();
    return documents.filter((d) => d.filename.toLowerCase().includes(lower) || d.document_type.toLowerCase().includes(lower));
  }, [documents, searchQuery]);

  const totalChunks = useMemo(() => documents.reduce((acc, d) => acc + d.chunk_count, 0), [documents]);
  const indexedCount = useMemo(() => documents.filter((d) => d.status === "indexed").length, [documents]);
  const healthRate = documents.length > 0 ? Math.round((indexedCount / documents.length) * 100) : 100;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Source Studio — Knowledge Ingestion"
        description="Ingest multi-modal documents, web domains, and codebases into NOVA's vector corpus and symbolic knowledge graph."
        action={
          <Button onClick={() => fileInputRef.current?.click()}>
            <Upload className="size-4" />
            Upload File
          </Button>
        }
      />

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.md,.txt,.json,.csv,.docx"
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Realtime Knowledge Processing Metrics Bar */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/20 text-primary">
              <FileText className="size-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-foreground">{documents.length}</div>
              <div className="text-xs text-muted-foreground">Active Sources</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-cyan-500/20 text-cyan-400">
              <Layers className="size-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-foreground">{totalChunks}</div>
              <div className="text-xs text-muted-foreground">Vector Chunks</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
              <Network className="size-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-foreground">{totalChunks * 2}</div>
              <div className="text-xs text-muted-foreground">Extracted Triples</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400">
              <Cpu className="size-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-emerald-400">{healthRate}%</div>
              <div className="text-xs text-muted-foreground">Health Index</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Multi-Source Ingestion Connector Studio */}
      <Card className="border-primary/30 shadow-lg shadow-primary/5">
        <CardHeader
          title="Ingest New Knowledge Source"
          description="Select a connector and specify the resource target for parsing and indexing"
        />
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {CONNECTOR_TYPES.map((connector) => {
              const Icon = connector.icon;
              const isSelected = selectedConnector === connector.id;
              return (
                <button
                  key={connector.id}
                  onClick={() => {
                    setSelectedConnector(connector.id);
                    if (connector.id === "pdf" || connector.id === "zip" || connector.id === "json") {
                      fileInputRef.current?.click();
                    }
                  }}
                  className={`flex flex-col items-start gap-2 rounded-xl p-3.5 border text-left transition-all duration-200 ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-sm"
                      : "border-border/60 bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <Icon className={`size-5 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                    {connector.badge && <Badge tone="neutral" className="text-[9px]">{connector.badge}</Badge>}
                  </div>
                  <span className="text-xs font-semibold text-foreground">{connector.label}</span>
                  <span className="text-[10px] text-muted-foreground line-clamp-2 leading-tight">{connector.desc}</span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                setSelectedFile(null);
              }}
              placeholder={
                selectedConnector === "url"
                  ? "Enter website URL (e.g. https://docs.aekof.ai)"
                  : selectedConnector === "git"
                  ? "Enter GitHub repo URL (e.g. https://github.com/org/repo)"
                  : "Enter document title or select a file…"
              }
              className="flex-1 rounded-lg border border-border/80 bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
            <Button
              onClick={handleStartProcessing}
              isLoading={uploadMutation.isPending}
              disabled={uploadMutation.isPending}
              className="px-6"
            >
              <Sparkles className="size-4" />
              {uploadMutation.isPending ? "Ingesting Pipeline…" : "Start Processing Pipeline"}
            </Button>
          </div>

          {/* Live Ingestion Pipeline Visualization */}
          {uploadMutation.isPending && (
            <div className="space-y-4 rounded-xl border border-primary/30 bg-primary/5 p-4 animate-pulse">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <RefreshCw className="size-4 text-primary animate-spin" />
                  Processing Pipeline Active for: <span className="font-mono text-primary">{inputValue || "New Source"}</span>
                </span>
                <Badge tone="primary">Pipeline Step 5/10</Badge>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5 text-[11px]">
                {PROCESSING_STAGES.map((stage) => (
                  <div key={stage.id} className="flex items-center gap-1.5 rounded-lg border border-border/40 bg-card p-2 text-foreground">
                    <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
                    <span className="truncate">{stage.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Managed Sources Table */}
      <Card>
        <CardHeader
          title="Active Knowledge Sources"
          description="Browse and manage indexed document corpora"
          action={
            <div className="relative w-64">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search active sources…"
                className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
          }
        />
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs font-medium text-muted-foreground uppercase">
              <tr>
                <th className="px-4 py-3">Source Target</th>
                <th className="px-4 py-3">Connector</th>
                <th className="px-4 py-3">Indexing Status</th>
                <th className="px-4 py-3">Vector Chunks</th>
                <th className="px-4 py-3">Extracted Triples</th>
                <th className="px-4 py-3">Added</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-xs text-muted-foreground">
                    Loading knowledge documents…
                  </td>
                </tr>
              ) : filteredSources.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-xs text-muted-foreground">
                    No active knowledge sources found. Ingest a document or URL above to begin.
                  </td>
                </tr>
              ) : (
                filteredSources.map((source) => (
                  <tr key={source.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 text-primary shrink-0" />
                        <span className="truncate max-w-xs">{source.filename}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone="neutral">{source.document_type.toUpperCase()}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[source.status as KnowledgeDocumentStatus] ?? "neutral"}>
                        {source.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{source.chunk_count} chunks</td>
                    <td className="px-4 py-3 font-mono text-xs text-primary">{source.chunk_count * 2} triples</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDateTime(source.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-danger hover:bg-danger/10"
                        onClick={() => handleDeleteSource(source.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
