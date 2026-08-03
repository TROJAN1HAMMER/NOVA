import { useState } from "react";
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
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useToast } from "../hooks/useToast";

interface IngestionSource {
  id: string;
  name: string;
  type: "PDF" | "URL" | "GIT" | "DOCX" | "JSON";
  status: "Ingested" | "Processing" | "Queued";
  chunks: number;
  entities: number;
  addedAt: string;
  size: string;
}

const CONNECTOR_TYPES = [
  { id: "pdf", label: "PDF / Office Docs", icon: FileText, desc: "Extract structured text & tables from PDF/DOCX" },
  { id: "url", label: "Web Crawler (Exa)", icon: Globe, desc: "Crawl web domain & ingest clean markdown" },
  { id: "git", label: "Git Repository", icon: GitBranch, desc: "Parse codebases & technical markdown docs" },
  { id: "zip", label: "Folder / ZIP Archive", icon: FolderArchive, desc: "Ingest directory trees & archive packages" },
  { id: "json", label: "CSV / JSON Datasets", icon: Database, desc: "Structure tabular knowledge & records" },
  { id: "notion", label: "Notion / Confluence", icon: FileCode, desc: "Enterprise wiki connector (Future-Ready)", badge: "Connector Ready" },
];

const PROCESSING_STAGES = [
  { id: 1, label: "Uploading", done: true },
  { id: 2, label: "Parsing", done: true },
  { id: 3, label: "Chunking", done: true },
  { id: 4, label: "Embedding Generation", done: true },
  { id: 5, label: "Entity Extraction", done: true },
  { id: 6, label: "Graph Construction", done: true },
  { id: 7, label: "Vector Indexing", done: true },
  { id: 8, label: "FAQ Detection", done: true },
  { id: 9, label: "Memory Sync", done: true },
  { id: 10, label: "Knowledge Ready", done: true },
];

const INITIAL_SOURCES: IngestionSource[] = [
  { id: "src-1", name: "AEKOF_Technical_Design_Specification.pdf", type: "PDF", status: "Ingested", chunks: 42, entities: 18, addedAt: "10 mins ago", size: "2.4 MB" },
  { id: "src-2", name: "https://docs.aekof.ai/framework-guide", type: "URL", status: "Ingested", chunks: 18, entities: 8, addedAt: "1 hour ago", size: "340 KB" },
  { id: "src-3", name: "aekof-core-engine (github.com/aekof/core)", type: "GIT", status: "Ingested", chunks: 156, entities: 64, addedAt: "3 hours ago", size: "14.8 MB" },
];

export default function SourceStudioPage() {
  const toast = useToast();
  const [sources, setSources] = useState<IngestionSource[]>(INITIAL_SOURCES);
  const [selectedConnector, setSelectedConnector] = useState("pdf");
  const [inputValue, setInputValue] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const handleStartProcessing = () => {
    if (!inputValue.trim()) {
      toast.error("Source Required", "Please enter a URL, file name, or repository link.");
      return;
    }
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      const newSrc: IngestionSource = {
        id: `src-${Date.now()}`,
        name: inputValue.trim(),
        type: selectedConnector === "url" ? "URL" : selectedConnector === "git" ? "GIT" : "PDF",
        status: "Ingested",
        chunks: Math.floor(Math.random() * 30) + 10,
        entities: Math.floor(Math.random() * 15) + 5,
        addedAt: "Just now",
        size: "1.2 MB",
      };
      setSources([newSrc, ...sources]);
      setInputValue("");
      toast.success("Knowledge Ingested!", "Source parsed, chunked, and indexed into pgvector & GraphRAG.");
    }, 2500);
  };

  const handleDeleteSource = (id: string) => {
    setSources(sources.filter((s) => s.id !== id));
    toast.info("Source Removed", "Deleted knowledge source and associated vector chunks.");
  };

  const filteredSources = sources.filter((s) => s.name.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Source Studio — Knowledge Ingestion"
        description="Ingest multi-modal documents, web domains, and codebases into NOVA's vector corpus and symbolic knowledge graph."
        action={
          <Button onClick={() => window.scrollTo({ top: 400, behavior: "smooth" })}>
            <Plus className="size-4" />
            Add Knowledge Source
          </Button>
        }
      />

      {/* Realtime Knowledge Processing Metrics Bar */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary/20 text-primary">
              <FileText className="size-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-foreground">{sources.length}</div>
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
              <div className="text-xl font-extrabold text-foreground">
                {sources.reduce((acc, s) => acc + s.chunks, 0)}
              </div>
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
              <div className="text-xl font-extrabold text-foreground">
                {sources.reduce((acc, s) => acc + s.entities, 0)}
              </div>
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
              <div className="text-xl font-extrabold text-emerald-400">100%</div>
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
                  onClick={() => setSelectedConnector(connector.id)}
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
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={
                selectedConnector === "url"
                  ? "Enter website URL (e.g. https://docs.aekof.ai)"
                  : selectedConnector === "git"
                  ? "Enter GitHub repo URL (e.g. https://github.com/org/repo)"
                  : "Enter file path or document title…"
              }
              className="flex-1 rounded-lg border border-border/80 bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
            <Button onClick={handleStartProcessing} isLoading={isProcessing} className="px-6">
              <Sparkles className="size-4" />
              Start Processing Pipeline
            </Button>
          </div>

          {/* Live Ingestion Pipeline Visualization */}
          {isProcessing && (
            <div className="space-y-4 rounded-xl border border-primary/30 bg-primary/5 p-4 animate-pulse">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <RefreshCw className="size-4 text-primary animate-spin" />
                  Processing Pipeline Active for: <span className="font-mono text-primary">{inputValue}</span>
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
              {filteredSources.map((source) => (
                <tr key={source.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium text-foreground">
                    <div className="flex items-center gap-2">
                      <FileText className="size-4 text-primary shrink-0" />
                      <span className="truncate max-w-xs">{source.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="neutral">{source.type}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400">
                      <CheckCircle2 className="size-3.5" />
                      {source.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{source.chunks} chunks</td>
                  <td className="px-4 py-3 font-mono text-xs text-primary">{source.entities} triples</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{source.addedAt}</td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-danger hover:bg-danger/10"
                      onClick={() => handleDeleteSource(source.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
