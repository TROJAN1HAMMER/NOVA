import { useEffect, useRef, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  FileText,
  Search,
  Sparkles,
  Trash2,
  Upload,
  MessageSquare,
  Layers,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { SkeletonTable } from "../components/ui/Skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell } from "../components/ui/Table";
import { FaqManager } from "../components/knowledge/FaqManager";
import { KnowledgeGapInbox } from "../components/knowledge/KnowledgeGapInbox";
import { usePermissions } from "../hooks/usePermissions";
import { useToast } from "../hooks/useToast";
import {
  useDeleteKnowledgeDocument,
  useKnowledgeDocuments,
  useSearchKnowledge,
  useUploadKnowledgeDocument,
} from "../hooks/useKnowledge";
import {
  fetchFaqRules,
  createFaqRule,
  deleteFaqRule,
  fetchGapInbox,
  promoteGapRule,
  type FAQRuleItem,
} from "../lib/api/faq";
import { cn, formatDateTime } from "../lib/utils";
import type { KnowledgeDocumentStatus } from "../types/api";

const STATUS_TONE: Record<KnowledgeDocumentStatus, "neutral" | "primary" | "success" | "danger"> = {
  pending: "neutral",
  processing: "primary",
  indexed: "success",
  failed: "danger",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeBasePage() {
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("knowledge:write");
  const toast = useToast();

  const [activeTab, setActiveTab] = useState<"documents" | "faq" | "gap-inbox">("documents");
  const [faqRules, setFaqRules] = useState<FAQRuleItem[]>([]);
  const [gapRules, setGapRules] = useState<FAQRuleItem[]>([]);

  const { data, isLoading } = useKnowledgeDocuments();
  const uploadMutation = useUploadKnowledgeDocument();
  const deleteMutation = useDeleteKnowledgeDocument();
  const searchMutation = useSearchKnowledge();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tags, setTags] = useState("");
  const [author, setAuthor] = useState("");
  const [version, setVersion] = useState("");
  const [query, setQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadFaqData = async () => {
    try {
      const [rules, drafts] = await Promise.all([fetchFaqRules(), fetchGapInbox()]);
      setFaqRules(rules);
      setGapRules(drafts);
    } catch {
      // quiet fail
    }
  };

  useEffect(() => {
    loadFaqData();
  }, []);

  const handleCreateFaq = async (keyword: string, response: string) => {
    try {
      await createFaqRule({ keyword, response });
      toast.success("FAQ Rule Created", `Instant 0ms rule for "${keyword}" added.`);
      await loadFaqData();
    } catch (err) {
      toast.error("Failed to create rule", err instanceof Error ? err.message : "Error creating rule");
    }
  };

  const handleDeleteFaq = async (id: string) => {
    try {
      await deleteFaqRule(id);
      toast.success("FAQ Rule Deleted");
      await loadFaqData();
    } catch {
      toast.error("Failed to delete rule");
    }
  };

  const handlePromoteGap = async (id: string) => {
    try {
      await promoteGapRule(id);
      toast.success("Knowledge Gap Promoted!", "Rule is now active for instant 0ms FAQ match.");
      await loadFaqData();
    } catch {
      toast.error("Failed to promote gap rule");
    }
  };

  const handleUpload = (event: React.FormEvent) => {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      toast.error("Choose a file first", "Select a PDF, Markdown, or text file to upload.");
      return;
    }
    uploadMutation.mutate(
      { file, tags: tags || undefined, author: author || undefined, version: version || undefined },
      {
        onSuccess: (doc) => {
          toast.success("Document uploaded", `"${doc.filename}" is being indexed in real time.`);
          setTags("");
          setAuthor("");
          setVersion("");
          if (fileInputRef.current) fileInputRef.current.value = "";
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Upload failed.";
          toast.error("Upload failed", message);
        },
      },
    );
  };

  const handleDelete = (documentId: string, filename: string) => {
    setDeletingId(documentId);
    deleteMutation.mutate(documentId, {
      onSuccess: () => toast.success("Document deleted", `"${filename}" was removed from the knowledge base.`),
      onError: () => toast.error("Delete failed", "Please try again."),
      onSettled: () => setDeletingId(null),
    });
  };

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate({ query, top_k: 5 });
  };

  const documents = data?.documents ?? [];

  const totalChunks = useMemo(() => {
    return documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
  }, [documents]);

  const indexedCount = useMemo(() => {
    return documents.filter((doc) => doc.status === "indexed").length;
  }, [documents]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Base & Self-Healing Engine"
        description="Upload documents, configure 0ms instant FAQ rules, and promote auto-synthesized failure gap candidates."
      />

      {/* Top Animated Knowledge Metric Cards */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="grid grid-cols-1 gap-4 sm:grid-cols-4"
      >
        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-primary/15 via-card to-card border-primary/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <BookOpen className="size-4 text-primary" /> Document Corpus
            </span>
            <Badge tone="success">{indexedCount} Indexed</Badge>
          </div>
          <div className="text-3xl font-bold text-foreground font-mono">{documents.length}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Active uploaded documents</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-emerald-500/15 via-card to-card border-emerald-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Layers className="size-4 text-emerald-400" /> Vector Chunks
            </span>
            <Badge tone="primary">FastEmbed 384-d</Badge>
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono">{totalChunks}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Indexed semantic passages</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-blue-500/15 via-card to-card border-blue-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <MessageSquare className="size-4 text-blue-400" /> 0ms FAQ Rules
            </span>
            <Badge tone="neutral">Stage 0 Cache</Badge>
          </div>
          <div className="text-3xl font-bold text-blue-400 font-mono">{faqRules.length}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Instant keyword matches</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-amber-500/15 via-card to-card border-amber-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Sparkles className="size-4 text-amber-400" /> Self-Healing Gaps
            </span>
            <Badge tone={gapRules.length > 0 ? "warning" : "success"}>
              {gapRules.length > 0 ? `${gapRules.length} Pending` : "0 Gaps"}
            </Badge>
          </div>
          <div className="text-3xl font-bold text-amber-400 font-mono">{gapRules.length}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Draft rules awaiting promotion</div>
        </Card>
      </motion.div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border gap-2 pb-2">
        <button
          onClick={() => setActiveTab("documents")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all duration-200",
            activeTab === "documents"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          )}
        >
          <BookOpen className="size-4" />
          <span>Document Corpus</span>
          <span className="ml-1 rounded-full bg-primary/30 px-2 py-0.5 text-xs text-primary font-mono font-bold">
            {documents.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("faq")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all duration-200",
            activeTab === "faq"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          )}
        >
          <MessageSquare className="size-4" />
          <span>FAQ Keyword Rules ({faqRules.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("gap-inbox")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all duration-200",
            activeTab === "gap-inbox"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          )}
        >
          <Sparkles className="size-4 text-amber-400 animate-pulse" />
          <span>Knowledge Gap Inbox ({gapRules.length})</span>
        </button>
      </div>

      {activeTab === "faq" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <FaqManager rules={faqRules} onCreateRule={handleCreateFaq} onDeleteRule={handleDeleteFaq} />
          </motion.div>
        </AnimatePresence>
      )}

      {activeTab === "gap-inbox" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <KnowledgeGapInbox draftRules={gapRules} onPromoteRule={handlePromoteGap} />
          </motion.div>
        </AnimatePresence>
      )}

      {activeTab === "documents" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {canWrite && (
                <Card className="h-full border-primary/30">
                  <CardHeader title="Upload a Document" description="PDF, Markdown (.md), or plain text (.txt) for RAG vector search & GraphRAG extraction." />
                  <CardContent>
                    <form onSubmit={handleUpload} className="space-y-3">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.md,.markdown,.txt"
                        className="block w-full text-xs text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary/20 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-primary hover:file:bg-primary/30"
                      />
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <input
                          value={version}
                          onChange={(e) => setVersion(e.target.value)}
                          placeholder="Version (optional)"
                          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                        />
                        <input
                          value={author}
                          onChange={(e) => setAuthor(e.target.value)}
                          placeholder="Author (optional)"
                          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                        />
                        <input
                          value={tags}
                          onChange={(e) => setTags(e.target.value)}
                          placeholder="Tags (comma-separated)"
                          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                        />
                      </div>
                      <Button type="submit" isLoading={uploadMutation.isPending} className="gap-2">
                        <Upload className="size-4" />
                        Upload & Index Document
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              )}

              <Card className="h-full border-primary/30">
                <CardHeader title="Knowledge Vector Search" description="Probe the FastEmbed vector store for semantic matches." />
                <CardContent>
                  <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="e.g. what is FAPI-03?"
                      className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                    <Button type="submit" isLoading={searchMutation.isPending} className="gap-1.5">
                      <Search className="size-4" />
                      Search
                    </Button>
                  </form>

                  {searchMutation.data && (
                    <div className="mt-4 space-y-3">
                      {searchMutation.data.results.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No matches found.</p>
                      ) : (
                        <>
                          <p className="text-xs text-muted-foreground flex items-center justify-between">
                            <span>{searchMutation.data.results.length} result(s) retrieved</span>
                            <span className="font-mono text-primary">{searchMutation.data.took_ms}ms</span>
                          </p>
                          {searchMutation.data.results.map((result) => (
                            <div key={result.chunk_id} className="rounded-lg border border-border/60 bg-muted/20 p-3 shadow-xs">
                              <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                                <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                                  <FileText className="size-3.5 text-primary" />
                                  {result.filename}
                                  {result.page_number != null && ` · p.${result.page_number}`}
                                </span>
                                <Badge tone="success">{Math.round(result.similarity_score * 100)}% match</Badge>
                              </div>
                              {result.section_path && (
                                <p className="mb-1 text-[11px] text-muted-foreground italic">{result.section_path}</p>
                              )}
                              <p className="text-xs text-foreground leading-relaxed">{result.content}</p>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader title="Document Repository" description={`${data?.total ?? 0} document(s) registered`} />
              <CardContent className="p-0 overflow-x-auto">
                {isLoading ? (
                  <SkeletonTable rows={4} columns={6} />
                ) : documents.length === 0 ? (
                  <div className="p-6">
                    <EmptyState
                      icon={<BookOpen className="size-10" />}
                      title="No documents yet"
                      description={
                        canWrite
                          ? "Upload a document above to start building the knowledge base."
                          : "No documents have been uploaded to the knowledge base yet."
                      }
                    />
                  </div>
                ) : (
                  <Table>
                    <TableHead>
                      <tr>
                        <TableHeaderCell>Filename</TableHeaderCell>
                        <TableHeaderCell>Type</TableHeaderCell>
                        <TableHeaderCell>Tags</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell>Chunks</TableHeaderCell>
                        <TableHeaderCell>Size</TableHeaderCell>
                        <TableHeaderCell>Uploaded</TableHeaderCell>
                        {canWrite && <TableHeaderCell className="text-right">Actions</TableHeaderCell>}
                      </tr>
                    </TableHead>
                    <TableBody>
                      {documents.map((doc, idx) => (
                        <motion.tr
                          key={doc.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.15, delay: idx * 0.02 }}
                          className="hover:bg-muted/30 transition-colors"
                        >
                          <TableCell className="font-medium text-xs">
                            <div className="flex items-center gap-2">
                              <FileText className="size-4 text-primary shrink-0" />
                              <span className="text-foreground font-semibold">{doc.filename}</span>
                            </div>
                            {doc.status === "failed" && doc.error_message && (
                              <p className="mt-0.5 text-[11px] text-danger">{doc.error_message}</p>
                            )}
                          </TableCell>
                          <TableCell className="uppercase text-[11px] font-mono text-muted-foreground">{doc.document_type}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {doc.tags.map((tag) => (
                                <Badge key={tag} tone="neutral" className="text-[10px]">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge
                              tone={STATUS_TONE[doc.status]}
                              className={`capitalize flex items-center gap-1 w-fit ${
                                doc.status === "indexed" ? "animate-pulse" : ""
                              }`}
                            >
                              {doc.status === "indexed" && <CheckCircle2 className="size-3 text-emerald-400" />}
                              {doc.status === "processing" && <RefreshCw className="size-3 animate-spin text-blue-400" />}
                              {doc.status === "failed" && <AlertCircle className="size-3 text-danger" />}
                              {doc.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="tabular-nums font-mono text-xs font-bold text-foreground">
                            {doc.chunk_count}
                          </TableCell>
                          <TableCell className="text-muted-foreground font-mono text-xs">{formatBytes(doc.file_size_bytes)}</TableCell>
                          <TableCell className="text-muted-foreground font-mono text-xs">{formatDateTime(doc.created_at)}</TableCell>
                          {canWrite && (
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                isLoading={deletingId === doc.id}
                                onClick={() => handleDelete(doc.id, doc.filename)}
                                aria-label={`Delete ${doc.filename}`}
                              >
                                <Trash2 className="size-4 text-danger hover:text-danger/80" />
                              </Button>
                            </TableCell>
                          )}
                        </motion.tr>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}
