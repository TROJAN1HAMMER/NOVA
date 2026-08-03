import { useEffect, useRef, useState } from "react";
import { BookOpen, FileText, Search, Sparkles, Trash2, Upload, MessageSquare } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { SkeletonTable } from "../components/ui/Skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
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
          toast.success("Document uploaded", `"${doc.filename}" is being indexed — this usually takes a few seconds.`);
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Base & Self-Healing Engine"
        description="Upload documents, configure 0ms instant FAQ rules, and promote auto-synthesized failure gap candidates."
      />

      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("documents")}
          className={cn(
            "flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            activeTab === "documents"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <BookOpen className="size-4" />
          Document Corpus
        </button>
        <button
          onClick={() => setActiveTab("faq")}
          className={cn(
            "flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            activeTab === "faq"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <MessageSquare className="size-4" />
          FAQ Keyword Rules ({faqRules.length})
        </button>
        <button
          onClick={() => setActiveTab("gap-inbox")}
          className={cn(
            "flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
            activeTab === "gap-inbox"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <Sparkles className="size-4 text-amber-500" />
          Knowledge Gap Inbox ({gapRules.length})
        </button>
      </div>

      {activeTab === "faq" && (
        <FaqManager rules={faqRules} onCreateRule={handleCreateFaq} onDeleteRule={handleDeleteFaq} />
      )}

      {activeTab === "gap-inbox" && (
        <KnowledgeGapInbox draftRules={gapRules} onPromoteRule={handlePromoteGap} />
      )}

      {activeTab === "documents" && (
        <>
          <RevealSection className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {canWrite && (
              <RevealItem>
                <Card className="h-full">
                  <CardHeader title="Upload a document" description="PDF, Markdown (.md), or plain text (.txt)." />
                  <CardContent>
                    <form onSubmit={handleUpload} className="space-y-3">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.md,.markdown,.txt"
                        className="block w-full text-sm text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium file:text-secondary-foreground hover:file:bg-secondary/80"
                      />
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <input
                          value={version}
                          onChange={(e) => setVersion(e.target.value)}
                          placeholder="Version (optional)"
                          className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                        />
                        <input
                          value={author}
                          onChange={(e) => setAuthor(e.target.value)}
                          placeholder="Author (optional)"
                          className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                        />
                        <input
                          value={tags}
                          onChange={(e) => setTags(e.target.value)}
                          placeholder="Tags (comma-separated)"
                          className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                        />
                      </div>
                      <Button type="submit" isLoading={uploadMutation.isPending}>
                        <Upload className="size-4" />
                        Upload
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </RevealItem>
            )}

            <RevealItem>
              <Card className="h-full">
                <CardHeader title="Search" description="Ask a question or describe what you're looking for." />
                <CardContent>
                  <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="e.g. how often must passwords be rotated?"
                      className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                    />
                    <Button type="submit" isLoading={searchMutation.isPending}>
                      <Search className="size-4" />
                      Search
                    </Button>
                  </form>

                  {searchMutation.data && (
                    <div className="mt-4 space-y-3">
                      {searchMutation.data.results.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No matches found.</p>
                      ) : (
                        <>
                          <p className="text-xs text-muted-foreground">
                            {searchMutation.data.results.length} result(s) in {searchMutation.data.took_ms}ms
                          </p>
                          {searchMutation.data.results.map((result) => (
                            <div key={result.chunk_id} className="rounded-lg border border-border p-3">
                              <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                                <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
                                  <FileText className="size-3.5" />
                                  {result.filename}
                                  {result.page_number != null && ` · p.${result.page_number}`}
                                </span>
                                <Badge tone="neutral">{Math.round(result.similarity_score * 100)}% match</Badge>
                              </div>
                              {result.section_path && (
                                <p className="mb-1 text-xs text-muted-foreground">{result.section_path}</p>
                              )}
                              <p className="text-sm text-foreground">{result.content}</p>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </RevealItem>
          </RevealSection>

          <RevealSection>
            <RevealItem>
              {isLoading ? (
                <SkeletonTable rows={4} columns={6} />
              ) : documents.length === 0 ? (
                <EmptyState
                  icon={<BookOpen className="size-10" />}
                  title="No documents yet"
                  description={
                    canWrite
                      ? "Upload a document above to start building the knowledge base."
                      : "No documents have been uploaded to the knowledge base yet."
                  }
                />
              ) : (
                <Card>
                  <CardHeader title="Documents" description={`${data?.total ?? 0} document(s)`} />
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
                        {canWrite && <TableHeaderCell />}
                      </tr>
                    </TableHead>
                    <TableBody>
                      {documents.map((doc) => (
                        <TableRow key={doc.id}>
                          <TableCell className="font-medium">
                            {doc.filename}
                            {doc.status === "failed" && doc.error_message && (
                              <p className="mt-0.5 text-xs text-danger">{doc.error_message}</p>
                            )}
                          </TableCell>
                          <TableCell className="uppercase text-xs text-muted-foreground">{doc.document_type}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {doc.tags.map((tag) => (
                                <Badge key={tag} tone="neutral">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge tone={STATUS_TONE[doc.status]} className="capitalize">
                              {doc.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="tabular-nums">{doc.chunk_count}</TableCell>
                          <TableCell className="text-muted-foreground">{formatBytes(doc.file_size_bytes)}</TableCell>
                          <TableCell className="text-muted-foreground">{formatDateTime(doc.created_at)}</TableCell>
                          {canWrite && (
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="sm"
                                isLoading={deletingId === doc.id}
                                onClick={() => handleDelete(doc.id, doc.filename)}
                                aria-label={`Delete ${doc.filename}`}
                              >
                                <Trash2 className="size-4 text-danger" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Card>
              )}
            </RevealItem>
          </RevealSection>
        </>
      )}
    </div>
  );
}
