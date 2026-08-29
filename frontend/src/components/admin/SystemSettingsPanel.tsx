import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  RotateCcw,
  Save,
  Sliders,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "../ui/Card";
import { Button } from "../ui/Button";
import { Input, Label } from "../ui/Input";
import { Badge } from "../ui/Badge";
import { Spinner } from "../ui/Spinner";
import { Modal } from "../ui/Modal";
import { RevealItem, RevealSection } from "../landing/RevealSection";
import { useResetSystemSettings, useSystemSettings, useUpdateSystemSettings } from "../../hooks/useSettings";
import { useToast } from "../../hooks/useToast";
import type { SystemSettings } from "../../types/api";

const DEFAULT_FORM_STATE: SystemSettings = {
  "rag.chunk_size": 1000,
  "rag.chunk_overlap": 200,
  "rag.temperature": 0.7,
  "rag.top_k": 5,
  "rag.similarity_threshold": 0.15,
  "rag.enable_web_search": true,
  "rag.enable_faq_router": true,
  "rag.enable_consensus": true,
  "rag.system_prompt": "",
};

export function SystemSettingsPanel() {
  const { data, isLoading, isError } = useSystemSettings();
  const updateSettings = useUpdateSystemSettings();
  const resetSettings = useResetSystemSettings();
  const toast = useToast();

  const [formState, setFormState] = useState<SystemSettings>(DEFAULT_FORM_STATE);
  const [resetModalOpen, setResetModalOpen] = useState(false);

  // Sync server data into formState when loaded
  useEffect(() => {
    if (data?.settings) {
      setFormState(() => ({
        ...DEFAULT_FORM_STATE,
        ...data.settings,
      }));
    }
  }, [data]);

  // Dirty state tracking
  const isDirty = useMemo(() => {
    if (!data?.settings) return false;
    const keys: (keyof SystemSettings)[] = [
      "rag.chunk_size",
      "rag.chunk_overlap",
      "rag.temperature",
      "rag.top_k",
      "rag.similarity_threshold",
      "rag.enable_web_search",
      "rag.enable_faq_router",
      "rag.enable_consensus",
      "rag.system_prompt",
    ];
    return keys.some((k) => formState[k] !== data.settings[k]);
  }, [formState, data]);

  const handleSave = () => {
    updateSettings.mutate(formState, {
      onSuccess: () => {
        toast.success(
          "Settings saved successfully",
          "RAG hyperparameters and system instructions updated.",
        );
      },
      onError: (err: any) => {
        toast.error(
          "Failed to save settings",
          err?.message || "Please check your network and admin permissions.",
        );
      },
    });
  };

  const handleReset = () => {
    resetSettings.mutate(undefined, {
      onSuccess: (res) => {
        setFormState(() => ({
          ...DEFAULT_FORM_STATE,
          ...res.settings,
        }));
        setResetModalOpen(false);
        toast.success(
          "Settings reset",
          "All RAG hyperparameters restored to factory defaults.",
        );
      },
      onError: (err: any) => {
        toast.error(
          "Failed to reset settings",
          err?.message || "Please check your admin permissions.",
        );
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <Spinner className="size-8 text-primary" />
        <p className="text-sm text-muted-foreground">Loading system settings…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="border-danger/30 bg-danger/5 p-6 text-sm text-danger">
        Failed to load platform settings. Please ensure you are logged in as an Administrator.
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header / Actions Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card/60 p-4 backdrop-blur-xs">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sliders className="size-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">RAG & AI Configuration</h2>
            <p className="text-xs text-muted-foreground">
              Dynamic hyperparameter tuning, retrieval thresholds, and enterprise prompt orchestration.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isDirty && (
            <Badge tone="warning" className="animate-pulse">
              Unsaved changes
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setResetModalOpen(true)}
            disabled={updateSettings.isPending || resetSettings.isPending}
          >
            <RotateCcw className="size-3.5" />
            Reset to Defaults
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!isDirty || updateSettings.isPending}
            isLoading={updateSettings.isPending}
          >
            <Save className="size-3.5" />
            Save Changes
          </Button>
        </div>
      </div>

      <RevealSection className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Section 1: Chunking & Ingestion */}
        <RevealItem>
          <Card className="h-full">
            <CardHeader
              title="Chunking & Ingestion"
              description="Document splitting boundaries for the vector embedding pipeline."
            />
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="chunk-size">Chunk Size (chars)</Label>
                  <span className="text-xs font-mono text-muted-foreground">
                    {formState["rag.chunk_size"]} chars
                  </span>
                </div>
                <Input
                  id="chunk-size"
                  type="number"
                  min={128}
                  max={8192}
                  step={64}
                  value={formState["rag.chunk_size"] ?? 1000}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      "rag.chunk_size": parseInt(e.target.value, 10) || 1000,
                    }))
                  }
                  className="mt-1"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Target character count per text segment ingested into the knowledge index.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="chunk-overlap">Chunk Overlap (chars)</Label>
                  <span className="text-xs font-mono text-muted-foreground">
                    {formState["rag.chunk_overlap"]} chars
                  </span>
                </div>
                <Input
                  id="chunk-overlap"
                  type="number"
                  min={0}
                  max={2048}
                  step={32}
                  value={formState["rag.chunk_overlap"] ?? 200}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      "rag.chunk_overlap": parseInt(e.target.value, 10) || 0,
                    }))
                  }
                  className="mt-1"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Shared character window between adjacent chunks to maintain context across boundaries.
                </p>
              </div>
            </CardContent>
          </Card>
        </RevealItem>

        {/* Section 2: Retrieval & Scoring */}
        <RevealItem>
          <Card className="h-full">
            <CardHeader
              title="Retrieval & Model Generation"
              description="Vector search limits, semantic similarity cutoff, and LLM temperature."
            />
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="top-k">Top K Retrieval Limit</Label>
                  <span className="text-xs font-mono text-muted-foreground">
                    {formState["rag.top_k"]} chunks
                  </span>
                </div>
                <Input
                  id="top-k"
                  type="number"
                  min={1}
                  max={25}
                  step={1}
                  value={formState["rag.top_k"] ?? 5}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      "rag.top_k": parseInt(e.target.value, 10) || 5,
                    }))
                  }
                  className="mt-1"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Maximum number of relevant knowledge passages passed into the model prompt.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="similarity-threshold">Similarity Cutoff (0.00 – 1.00)</Label>
                  <span className="text-xs font-mono text-muted-foreground">
                    {formState["rag.similarity_threshold"]}
                  </span>
                </div>
                <Input
                  id="similarity-threshold"
                  type="number"
                  min={0.0}
                  max={1.0}
                  step={0.01}
                  value={formState["rag.similarity_threshold"] ?? 0.15}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      "rag.similarity_threshold": parseFloat(e.target.value) || 0.0,
                    }))
                  }
                  className="mt-1"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Minimum cosine similarity score required for a chunk to be considered relevant.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <Label htmlFor="temperature">LLM Temperature (0.00 – 1.00)</Label>
                  <span className="text-xs font-mono text-muted-foreground">
                    {formState["rag.temperature"]}
                  </span>
                </div>
                <Input
                  id="temperature"
                  type="number"
                  min={0.0}
                  max={1.0}
                  step={0.05}
                  value={formState["rag.temperature"] ?? 0.7}
                  onChange={(e) =>
                    setFormState((prev) => ({
                      ...prev,
                      "rag.temperature": parseFloat(e.target.value) || 0.0,
                    }))
                  }
                  className="mt-1"
                />
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Controls output randomness. Lower values are more deterministic; higher values are more creative.
                </p>
              </div>
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Section 3: Feature Flags */}
      <RevealSection>
        <RevealItem>
          <Card>
            <CardHeader
              title="Feature Flags & Self-Healing Pipeline"
              description="Toggle outer-loop self-healing, web synthesis, and consensus modules."
            />
            <CardContent>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-card/40 p-4 transition-colors hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={formState["rag.enable_web_search"] ?? true}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        "rag.enable_web_search": e.target.checked,
                      }))
                    }
                    className="mt-1 size-4 rounded border-border text-primary focus:ring-primary/40"
                  />
                  <div>
                    <span className="text-sm font-medium text-foreground">Web Search Integration</span>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Allows fallback to curated web search when internal knowledge similarity is low.
                    </p>
                  </div>
                </label>

                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-card/40 p-4 transition-colors hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={formState["rag.enable_faq_router"] ?? true}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        "rag.enable_faq_router": e.target.checked,
                      }))
                    }
                    className="mt-1 size-4 rounded border-border text-primary focus:ring-primary/40"
                  />
                  <div>
                    <span className="text-sm font-medium text-foreground">FAQ Rule Router</span>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Checks exact and fuzzy FAQ keywords before triggering dense vector search.
                    </p>
                  </div>
                </label>

                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-card/40 p-4 transition-colors hover:bg-muted/40">
                  <input
                    type="checkbox"
                    checked={formState["rag.enable_consensus"] ?? true}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        "rag.enable_consensus": e.target.checked,
                      }))
                    }
                    className="mt-1 size-4 rounded border-border text-primary focus:ring-primary/40"
                  />
                  <div>
                    <span className="text-sm font-medium text-foreground">Multi-Source Consensus</span>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Cross-validates factual statements across multiple retrieved documents.
                    </p>
                  </div>
                </label>
              </div>
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Section 4: AI System Prompt Editor */}
      <RevealSection>
        <RevealItem>
          <Card>
            <CardHeader
              title="System Prompt Template"
              description="Master system prompt injected into all assistant chats, executive analyses, and synthesis operations."
            />
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Available Template Variables:</span>
                <div className="flex gap-2">
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-primary">
                    {"{context}"}
                  </code>
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-primary">
                    {"{question}"}
                  </code>
                </div>
              </div>

              <textarea
                value={formState["rag.system_prompt"] ?? ""}
                onChange={(e) =>
                  setFormState((prev) => ({
                    ...prev,
                    "rag.system_prompt": e.target.value,
                  }))
                }
                rows={10}
                className="w-full rounded-lg border border-input bg-card/80 p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                placeholder="Enter system prompt template..."
              />
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Reset Confirmation Modal */}
      <Modal
        open={resetModalOpen}
        onClose={() => setResetModalOpen(false)}
        title={
          <div className="flex items-center gap-2 text-danger">
            <AlertTriangle className="size-5" />
            <span>Reset System Settings to Defaults</span>
          </div>
        }
      >
        <div className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            Are you sure you want to reset all dynamic system settings and RAG hyperparameters to their factory default values?
          </p>
          <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            This will discard all custom chunk sizes, temperature settings, and customized system prompt templates in the database.
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setResetModalOpen(false)}
              disabled={resetSettings.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleReset}
              isLoading={resetSettings.isPending}
            >
              Confirm Reset
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
