import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Layers,
  Clock,
  UserCheck,
  ShieldCheck,
  Trash2,
  ArrowRight,
  Activity,
  Database,
  CheckCircle2,
  Sparkles,
  Zap,
  Play,
  HelpCircle,
  AlertCircle,
  RotateCcw,
  Sliders,
  Search,
  Check,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../hooks/useToast";
import { usePermissions } from "../hooks/usePermissions";

interface MemoryItem {
  id: string;
  layer: string;
  title: string;
  content: string;
  role?: string;
  turn_number?: number;
  in_sliding_window?: boolean;
  session_id?: string;
  provenance: {
    source_type: string;
    source_id: string;
    session_id?: string;
    origin: string;
    owner_scope: string;
    verification_state: string;
  };
  lifecycle: string;
  why_remembered: string;
  can_delete: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export default function MemoryPage() {
  const toast = useToast();
  const { role, roleDisplayName } = usePermissions();
  const [selectedLayer, setSelectedLayer] = useState<string>("Layer 1");
  const [sessionTurnCount, setSessionTurnCount] = useState<number>(0);
  const [memoryState, setMemoryState] = useState<any>(null);
  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulatingStep, setSimulatingStep] = useState<number | null>(null);

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [layerItems, setLayerItems] = useState<MemoryItem[]>([]);
  const [isLoadingItems, setIsLoadingItems] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Why Does NOVA Remember This Modal
  const [selectedWhyItem, setSelectedWhyItem] = useState<MemoryItem | null>(null);

  // Reset Buffer Confirmation Modal
  const [showResetConfirmModal, setShowResetConfirmModal] = useState<boolean>(false);

  // Preference editor state
  const [showPrefModal, setShowPrefModal] = useState<boolean>(false);
  const [preferences, setPreferences] = useState<any>({
    department: "Security Architecture & Engineering",
    language: "English (US)",
    tone: "Executive Technical Synthesis",
    context_scope: "Full Enterprise Knowledge",
  });
  const [isSavingPref, setIsSavingPref] = useState<boolean>(false);

  const fetchSessionMemory = async () => {
    try {
      const token = localStorage.getItem("nova_access_token");
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      // Fetch active sessions
      const res = await fetch("/api/v1/assistant/sessions", { headers: authHeaders });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setActiveSessionId(data[0].id);
          setSessionTurnCount(data[0].turn_count ?? Math.floor((data[0].message_count || 0) / 2));
        } else {
          setActiveSessionId(null);
          setSessionTurnCount(0);
        }
      }

      // Fetch live 5-layer memory state
      const stateRes = await fetch("/api/v1/assistant/memory/state", { headers: authHeaders });
      if (stateRes.ok) {
        const stateData = await stateRes.json();
        setMemoryState(stateData);
        if (stateData?.layers?.short_term?.session_turn_count !== undefined) {
          setSessionTurnCount(stateData.layers.short_term.session_turn_count);
        }
      } else {
        setMemoryState(null);
      }

      // Fetch user preferences
      const prefRes = await fetch("/api/v1/memory/preferences", { headers: authHeaders });
      if (prefRes.ok) {
        const prefData = await prefRes.json();
        setPreferences(prefData);
      }
    } catch {
      setMemoryState(null);
    }
  };

  const fetchLayerItems = async (layerLevel: string, customSessionId?: string | null) => {
    setIsLoadingItems(true);
    try {
      const token = localStorage.getItem("nova_access_token");
      const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      const layerIdMap: Record<string, string> = {
        "Layer 1": "short_term",
        "Layer 2": "long_term",
        "Layer 3": "preferences",
        "Layer 4": "task_execution",
        "Layer 5": "organizational",
      };
      const apiLayerId = layerIdMap[layerLevel] || "short_term";
      const targetSession = customSessionId !== undefined ? customSessionId : activeSessionId;
      const sessionQuery = (layerLevel === "Layer 1" && targetSession) ? `?session_id=${targetSession}` : "";

      const res = await fetch(`/api/v1/memory/layers/${apiLayerId}/items${sessionQuery}`, { headers: authHeaders });
      if (res.ok) {
        const items = await res.json();
        setLayerItems(items);
      } else {
        setLayerItems([]);
      }
    } catch {
      setLayerItems([]);
    } finally {
      setIsLoadingItems(false);
    }
  };

  useEffect(() => {
    fetchSessionMemory();
  }, []);

  useEffect(() => {
    if (selectedLayer) {
      fetchLayerItems(selectedLayer);
    }
  }, [selectedLayer, activeSessionId]);

  const handleClearShortTerm = async () => {
    setIsClearing(true);
    try {
      const token = localStorage.getItem("nova_access_token");
      const url = activeSessionId
        ? `/api/v1/memory/sessions/${activeSessionId}/reset`
        : `/api/v1/memory/sessions/reset`;

      const res = await fetch(url, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        setSessionTurnCount(0);
        toast.success("Buffer Cleared", "Active conversation 10-turn sliding window reset to 0 turns.");
        await fetchSessionMemory();
        await fetchLayerItems("Layer 1");
      } else {
        toast.error("Clear Failed", "Could not clear active session turn buffer.");
      }
    } catch {
      toast.error("Error", "Network or server error resetting buffer.");
    } finally {
      setIsClearing(false);
    }
  };

  const handleConfirmResetSession = async () => {
    setIsClearing(true);
    try {
      const token = localStorage.getItem("nova_access_token");
      const url = activeSessionId
        ? `/api/v1/memory/sessions/${activeSessionId}/reset`
        : `/api/v1/memory/sessions/reset`;

      const res = await fetch(url, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        setShowResetConfirmModal(false);
        setSessionTurnCount(0);
        toast.success("Active Session Reset", "Active conversational session turns cleared and buffer reset to 0.");
        await fetchSessionMemory();
        await fetchLayerItems(selectedLayer);
      } else {
        toast.error("Reset Failed", "Could not reset the active session.");
      }
    } catch {
      toast.error("Reset Error", "Failed to communicate with the memory service.");
    } finally {
      setIsClearing(false);
    }
  };

  const handleForgetItem = async (item: MemoryItem) => {
    try {
      const token = localStorage.getItem("nova_access_token");
      const layerIdMap: Record<string, string> = {
        "Layer 1": "short_term",
        "Layer 2": "long_term",
        "Layer 3": "preferences",
        "Layer 4": "task_execution",
        "Layer 5": "organizational",
      };
      const apiLayerId = layerIdMap[selectedLayer] || "short_term";

      const res = await fetch(`/api/v1/memory/${apiLayerId}/${encodeURIComponent(item.id)}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        toast.success("Memory Forgotten", `Safely removed: ${item.title}`);
        await fetchLayerItems(selectedLayer);
        await fetchSessionMemory();
      } else {
        const err = await res.json();
        toast.error("Deletion Prevented", err.detail || "Cannot delete this memory item.");
      }
    } catch {
      toast.error("Forget Failed", "Network or authorization error.");
    }
  };

  const handleSavePreferences = async () => {
    setIsSavingPref(true);
    try {
      const token = localStorage.getItem("nova_access_token");
      const res = await fetch("/api/v1/memory/preferences", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(preferences),
      });

      if (res.ok) {
        const updated = await res.json();
        setPreferences(updated);
        toast.success("Preferences Synchronized", "Persistent user preference memory updated in PostgreSQL.");
        setShowPrefModal(false);
        if (selectedLayer === "Layer 3") {
          await fetchLayerItems("Layer 3");
        }
        await fetchSessionMemory();
      } else {
        toast.error("Save Failed", "Could not save user preferences.");
      }
    } catch {
      toast.error("Error", "Network error updating preferences.");
    } finally {
      setIsSavingPref(false);
    }
  };

  const handleDemonstrateFlow = async () => {
    if (isSimulating) return;
    setIsSimulating(true);
    toast.info("Demonstration Started", "Simulating context traversal through all 5 layers (client demonstration only)...");

    for (let step = 1; step <= 5; step++) {
      setSimulatingStep(step);
      setSelectedLayer(`Layer ${step}`);
      await new Promise((resolve) => setTimeout(resolve, 800));
    }

    setIsSimulating(false);
    setSimulatingStep(null);
    toast.success("Demonstration Complete", "Simulated 5-layer traversal finished. Production memory remains untouched.");
  };

  const memoryLayers = [
    {
      level: "Layer 1",
      stepNum: 1,
      title: "Short-Term Conversational Memory",
      icon: Clock,
      description: "Active 10-turn conversation sliding window buffer per user session.",
      status: sessionTurnCount > 0 ? `Active (${sessionTurnCount}/10 turns)` : "0 / 10 Turns",
      tone: (sessionTurnCount > 0 ? "success" : "neutral") as "success" | "neutral",
      color: "from-blue-500/20 to-cyan-500/10 border-blue-500/40",
      details: [
        "Sliding Window Size: 10 Turns (20 messages)",
        "Storage Engine: PostgreSQL (chat_messages, chat_sessions)",
        `Active Session Turns: ${sessionTurnCount} / 10 turns`,
        "Scope & Isolation: Strictly authenticated user & session",
      ],
    },
    {
      level: "Layer 2",
      stepNum: 2,
      title: "Long-Term Semantic Memory",
      icon: Brain,
      description: "Older conversational context compressed & indexed for long-term retrieval.",
      status: (memoryState?.layers?.long_term?.compressed_summaries ?? 0) > 0
        ? `${memoryState.layers.long_term.compressed_summaries} Compressed Contexts`
        : "No Compressed Summaries",
      tone: ((memoryState?.layers?.long_term?.compressed_summaries ?? 0) > 0 ? "primary" : "neutral") as "primary" | "neutral",
      color: "from-indigo-500/20 to-purple-500/10 border-indigo-500/40",
      details: [
        "Embedding Dimension: 384-dim FastEmbed (BAAI/bge-small-en-v1.5)",
        `Vector Engine: PostgreSQL pgvector (${memoryState?.layers?.long_term?.vector_count ?? 0} vectors)`,
        `Compressed Summaries: ${memoryState?.layers?.long_term?.compressed_summaries ?? 0} user session contexts`,
        "Scope: Older multi-turn conversation synthesis",
      ],
    },
    {
      level: "Layer 3",
      stepNum: 3,
      title: "User Preference Memory",
      icon: UserCheck,
      description: "User role, department parameters, and language preference settings.",
      status: `Synchronized (${(roleDisplayName || role || "DEVELOPER").toUpperCase()})`,
      tone: "neutral" as const,
      color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/40",
      details: [
        `Designated Role: ${(memoryState?.layers?.preferences?.user_role || roleDisplayName || role || "DEVELOPER").toUpperCase()}`,
        `Department Context: ${preferences.department || "Not specified"}`,
        `Language: ${preferences.language || "English (US)"}`,
        `Tone Calibration: ${preferences.tone || "Executive Technical Synthesis"}`,
      ],
    },
    {
      level: "Layer 4",
      stepNum: 4,
      title: "Task Execution Memory",
      icon: Layers,
      description: "Multi-step task execution state, reasoning checkpoints, and scan jobs.",
      status: (memoryState?.layers?.task_execution?.checkpoints_count ?? 0) > 0
        ? `${memoryState.layers.task_execution.checkpoints_count} Checkpoints`
        : "Idle",
      tone: "neutral" as const,
      color: "from-amber-500/20 to-orange-500/10 border-amber-500/40",
      details: [
        "Execution Engine: Reasoning trace & security intel pipeline",
        `Last Active Stage: ${memoryState?.layers?.task_execution?.last_active_plan || "STAGE_2_SAFETY_GATE_PASS"}`,
        `Verified Checkpoints: ${memoryState?.layers?.task_execution?.checkpoints_count ?? 0} traces in PostgreSQL`,
        "Scope: Multi-turn workflow state tracking",
      ],
    },
    {
      level: "Layer 5",
      stepNum: 5,
      title: "Organizational Axiom Memory",
      icon: ShieldCheck,
      description: "High-confidence organizational rules and verified Stage-0 FAQ rules.",
      status: `${memoryState?.layers?.organizational?.active_rules ?? 0} Verified Axioms`,
      tone: "success" as const,
      color: "from-emerald-500/25 to-lime-500/10 border-emerald-500/50",
      details: [
        `Active Stage-0 Axioms: ${memoryState?.layers?.organizational?.active_rules ?? 0} verified rules`,
        `Draft Gap Candidates: ${memoryState?.layers?.organizational?.pending_gap_candidates ?? 0} in evolution inbox`,
        "Execution Gate: Pre-vector deterministic match",
        "Governance: RBAC-restricted modification (FAQ_WRITE)",
      ],
    },
  ];

  const activeDetail = memoryLayers.find((m) => m.level === selectedLayer) || memoryLayers[0];
  const DetailIcon = activeDetail.icon;

  const getLifecycleTone = (lifecycle: string) => {
    switch (lifecycle) {
      case "NEW":
      case "DRAFT":
        return "warning";
      case "ACTIVE":
      case "VERIFIED":
      case "COMPLETED":
        return "success";
      case "STALE":
      case "PAUSED":
        return "warning";
      case "ARCHIVED":
      case "IDLE":
        return "neutral";
      case "FAILED":
        return "danger";
      default:
        return "neutral";
    }
  };

  const filteredItems = layerItems.filter((item) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      item.content.toLowerCase().includes(q) ||
      (item.provenance?.origin && item.provenance.origin.toLowerCase().includes(q)) ||
      (item.role && item.role.toLowerCase().includes(q)) ||
      item.id.toLowerCase().includes(q)
    );
  });

  const getEmptyStateMessage = () => {
    switch (selectedLayer) {
      case "Layer 1":
        return {
          title: "0 / 10 Turns",
          description: "No conversational memory has been recorded for this session.",
        };
      case "Layer 2":
        return {
          title: "No Long-Term Semantic Memories Available",
          description: "No long-term semantic memories available for this user account. Older turns are automatically compressed once sessions exceed the sliding window.",
        };
      case "Layer 3":
        return {
          title: "No Preferences Configured",
          description: "No user preferences configured. Use 'Configure Preferences' to configure department and tone.",
        };
      case "Layer 4":
        return {
          title: "No Active Task Execution State",
          description: "No active task execution state found for this session.",
        };
      case "Layer 5":
        return {
          title: "No Verified Organizational Axioms Available",
          description: "No verified organizational axioms available. Draft evolution candidates require domain expert promotion.",
        };
      default:
        return {
          title: "No Records Found",
          description: `No stored memory records found in ${activeDetail.title}.`,
        };
    }
  };

  const emptyState = getEmptyStateMessage();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hierarchical 5-Layer Enterprise Memory Engine"
        description="Inspectable, isolated memory management backed by PostgreSQL persistence and authoritative lifecycle tracking."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => setShowPrefModal(true)}
              className="gap-2 border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400"
            >
              <Sliders className="size-4" />
              Configure Preferences
            </Button>
            <Button
              variant="outline"
              onClick={handleDemonstrateFlow}
              disabled={isSimulating}
              className="gap-2 border-primary/40 bg-primary/10 hover:bg-primary/20"
            >
              <Play className={`size-4 text-primary ${isSimulating ? "animate-spin" : ""}`} />
              {isSimulating ? `Demonstrating Layer ${simulatingStep}...` : "Demonstrate Memory Flow"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setShowResetConfirmModal(true)}
              isLoading={isClearing}
              className="gap-2 hover:border-danger hover:text-danger"
            >
              <Trash2 className="size-4 text-danger" />
              Reset Buffer
            </Button>
          </div>
        }
      />

      {/* Simulation Notice Banner */}
      {isSimulating && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between p-3 rounded-lg bg-primary/15 border border-primary/40 text-xs text-primary"
        >
          <div className="flex items-center gap-2 font-medium">
            <Activity className="size-4 animate-spin" />
            <span>CLIENT SIMULATION ACTIVE · DOES NOT MODIFY PRODUCTION MEMORY</span>
          </div>
          <span className="text-[11px] text-muted-foreground">
            Demonstrating context traversal through Layer {simulatingStep}
          </span>
        </motion.div>
      )}

      {/* Live Health Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      >
        {/* Metric 1: Active Session Context */}
        <Card className="relative overflow-hidden p-4 bg-card/60 backdrop-blur-md border-border/60 hover:border-primary/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-2">
              <Activity className="size-4 text-primary animate-pulse" /> Active Session Context
            </span>
            <Zap className="size-3.5 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-foreground flex items-center justify-between">
            <span>
              {sessionTurnCount} <span className="text-xs text-muted-foreground font-normal">/ 10 Turns</span>
            </span>
            <Badge tone={sessionTurnCount > 0 ? "success" : "neutral"} className={sessionTurnCount > 0 ? "animate-pulse" : ""}>
              {sessionTurnCount > 0 ? "LIVE" : "EMPTY"}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1 truncate">
            {activeSessionId ? `Session: ${activeSessionId.slice(0, 8)}...` : "No active session"}
          </p>
        </Card>

        {/* Metric 2: Truthful Vector Memory Health */}
        <Card className="relative overflow-hidden p-4 bg-card/60 backdrop-blur-md border-border/60 hover:border-emerald-500/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-2">
              <Database className="size-4 text-emerald-500" /> Vector Memory Health
            </span>
            <Sparkles className="size-3.5 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-foreground flex items-center gap-2">
            {memoryState?.health?.status === "ONLINE" ? (
              <>
                <span className="text-emerald-500">ONLINE</span>
                <Badge tone="success">READY</Badge>
              </>
            ) : memoryState?.health?.status === "DEGRADED" ? (
              <>
                <span className="text-amber-400">DEGRADED</span>
                <Badge tone="warning">ATTENTION</Badge>
              </>
            ) : (
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                HEALTH STATUS UNAVAILABLE
              </span>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            {memoryState?.health?.storage_engine || "PostgreSQL 16 + pgvector"}
          </p>
        </Card>

        {/* Metric 3: Stage 0 Axiom Cache (Truthful, No Fake 0ms) */}
        <Card className="relative overflow-hidden p-4 bg-card/60 backdrop-blur-md border-border/60 hover:border-amber-500/50 transition-colors">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-amber-500" /> Stage 0 Axiom Cache
            </span>
            <Badge tone="neutral" className="text-[10px]">STAGE 0 GATE</Badge>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {memoryState?.layers?.organizational?.active_rules ?? 0} <span className="text-xs text-muted-foreground font-normal">Verified Rules</span>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Pre-Vector Cache · Latency: <span className="font-mono text-muted-foreground">Not measured</span>
          </p>
        </Card>
      </motion.div>

      {/* Signal Stream Visualizer */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="rounded-xl border border-border/60 bg-gradient-to-r from-card via-background to-card p-4 relative overflow-hidden"
      >
        <div className="flex items-center justify-between mb-3 text-xs">
          <span className="font-semibold text-foreground flex items-center gap-2">
            <Zap className="size-4 text-primary animate-bounce" /> 5-Layer Hierarchical Retrieval Flow
          </span>
          <span className="text-muted-foreground text-[11px]">
            {isSimulating ? `Active Simulation Step: Layer ${simulatingStep}` : "Click any layer to inspect live database records"}
          </span>
        </div>

        <div className="grid grid-cols-5 gap-2 relative z-10">
          {memoryLayers.map((layer) => {
            const isSelected = selectedLayer === layer.level;
            const isCurrentSim = simulatingStep === layer.stepNum;
            return (
              <button
                key={layer.level}
                onClick={() => setSelectedLayer(layer.level)}
                className={`relative flex flex-col items-center gap-1.5 p-2.5 rounded-lg border text-center transition-all duration-300 ${
                  isCurrentSim
                    ? "border-primary bg-primary/20 scale-105 shadow-lg shadow-primary/30 ring-2 ring-primary"
                    : isSelected
                    ? "border-primary/80 bg-primary/10 shadow-sm"
                    : "border-border/40 bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
                }`}
              >
                <div className={`p-1.5 rounded-full ${isSelected ? "bg-primary/30 text-primary" : "bg-muted text-muted-foreground"}`}>
                  <layer.icon className="size-4" />
                </div>
                <span className="text-[11px] font-semibold text-foreground truncate w-full">{layer.level}</span>
                {isCurrentSim && (
                  <span className="absolute -top-1 -right-1 size-3 rounded-full bg-primary animate-ping" />
                )}
              </button>
            );
          })}
        </div>
      </motion.div>

      {/* Layer Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
        {memoryLayers.map((layer, index) => {
          const Icon = layer.icon;
          const isSelected = selectedLayer === layer.level;
          const isCurrentSim = simulatingStep === layer.stepNum;
          return (
            <motion.div
              key={layer.level}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.05 }}
            >
              <Card
                onClick={() => setSelectedLayer(layer.level)}
                className={`relative overflow-hidden cursor-pointer transition-all duration-300 bg-gradient-to-br ${layer.color} h-full ${
                  isCurrentSim
                    ? "border-primary shadow-xl shadow-primary/20 scale-[1.02] ring-2 ring-primary"
                    : isSelected
                    ? "border-primary bg-primary/10 shadow-md shadow-primary/10 ring-1 ring-primary/40"
                    : "border-border/60 hover:border-primary/40 hover:scale-[1.01]"
                }`}
              >
                <CardHeader
                  title={layer.level}
                  action={<Badge tone={layer.tone}>{layer.status}</Badge>}
                />
                <CardContent className="pt-0">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`p-1.5 rounded-md ${isSelected ? "bg-primary/30 text-primary" : "bg-muted text-muted-foreground"}`}>
                      <Icon className="size-4" />
                    </div>
                    <span className="text-xs font-semibold text-foreground truncate">{layer.title}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">{layer.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Layer Inspection & Real Records Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Architecture Specifications */}
        <div className="space-y-4 lg:col-span-1">
          <Card className="border-border/60 h-full">
            <CardHeader
              title={`${activeDetail.level} Specification`}
              description="Persistence contract & scope"
              action={<Badge tone={activeDetail.tone}>{activeDetail.status}</Badge>}
            />
            <CardContent className="space-y-4 pt-2">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/40">
                <div className="p-2.5 rounded-lg bg-primary/20 text-primary shrink-0">
                  <DetailIcon className="size-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground">{activeDetail.title}</h4>
                  <p className="text-xs text-muted-foreground">{activeDetail.description}</p>
                </div>
              </div>

              <div>
                <h5 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-3 flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-primary" /> Architecture Parameters
                </h5>
                <div className="space-y-2">
                  {activeDetail.details.map((detail, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: 10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2, delay: idx * 0.05 }}
                      className="flex items-center gap-2 text-xs bg-muted/20 p-2.5 rounded-md border border-border/40 text-foreground hover:bg-muted/40 transition-colors"
                    >
                      <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0" />
                      <span>{detail}</span>
                    </motion.div>
                  ))}
                </div>
              </div>

              {activeDetail.level === "Layer 1" && (
                <div className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearShortTerm}
                    isLoading={isClearing}
                    className="w-full gap-2 hover:border-danger hover:text-danger"
                  >
                    <Trash2 className="size-3.5 text-danger" /> Clear Layer 1 Turn Buffer
                  </Button>
                </div>
              )}

              {activeDetail.level === "Layer 3" && (
                <div className="pt-2">
                  <Button variant="outline" size="sm" onClick={() => setShowPrefModal(true)} className="w-full gap-2">
                    <Sliders className="size-3.5 text-emerald-400" /> Edit User Preferences
                  </Button>
                </div>
              )}

              {activeDetail.level === "Layer 5" && (
                <div className="pt-2">
                  <Button variant="outline" size="sm" onClick={() => (window.location.href = "/knowledge")} className="w-full gap-2">
                    <ArrowRight className="size-3.5 text-primary" /> Manage Stage 0 Axiom Rules
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Live Inspectable Items List */}
        <div className="lg:col-span-2">
          <Card className="border-primary/30 h-full shadow-lg">
            <CardHeader
              title={`Inspected Records: ${activeDetail.title}`}
              description={`Authoritative persistent state in PostgreSQL (${filteredItems.length} records shown)`}
              action={
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      await fetchSessionMemory();
                      await fetchLayerItems(selectedLayer);
                      toast.info("Refreshed", "Retrieved fresh memory records from PostgreSQL.");
                    }}
                    isLoading={isLoadingItems}
                    className="gap-1.5"
                  >
                    <RotateCcw className="size-3.5" /> Refresh Records
                  </Button>
                </div>
              }
            />
            <CardContent className="pt-2 space-y-3">
              {/* Search Memory Filter */}
              <div className="relative">
                <Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={`Search memory records in ${activeDetail.title}...`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md bg-muted/30 border border-border/60 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary transition-colors"
                />
              </div>

              {isLoadingItems ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  <Activity className="size-6 text-primary animate-spin mx-auto mb-2" />
                  Inspecting live database records for {selectedLayer}...
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="py-12 text-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-lg p-6">
                  <AlertCircle className="size-6 text-muted-foreground mx-auto mb-2 opacity-60" />
                  <p className="font-semibold text-foreground text-sm mb-1">{emptyState.title}</p>
                  <p className="text-muted-foreground max-w-md mx-auto">{emptyState.description}</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
                  {filteredItems.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-3.5 rounded-lg border border-border/60 bg-muted/20 hover:border-primary/40 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3 mb-1.5">
                        <div className="space-y-0.5 flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <h4 className="text-xs font-semibold text-foreground truncate">{item.title}</h4>
                            <Badge tone={getLifecycleTone(item.lifecycle)}>{item.lifecycle}</Badge>

                            {/* Layer 1 Sliding Window Status */}
                            {item.in_sliding_window !== undefined && (
                              <Badge tone={item.in_sliding_window ? "success" : "neutral"} className="text-[10px]">
                                {item.in_sliding_window ? "IN SLIDING WINDOW" : "ARCHIVED POSTGRESQL"}
                              </Badge>
                            )}

                            {/* Verification State */}
                            {item.provenance?.verification_state && (
                              <Badge tone="neutral" className="text-[10px] font-mono">
                                {item.provenance.verification_state}
                              </Badge>
                            )}
                          </div>

                          <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1">
                            {item.content}
                          </p>
                        </div>

                        <div className="flex items-center gap-1.5 shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedWhyItem(item)}
                            title="Why does NOVA remember this?"
                            className="text-xs gap-1 hover:text-primary px-2"
                          >
                            <HelpCircle className="size-3.5 text-primary" />
                            Why?
                          </Button>
                          {item.can_delete && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleForgetItem(item)}
                              title="Safe Forget Memory Item"
                              className="text-xs hover:text-danger px-2 text-muted-foreground"
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Provenance Footer */}
                      <div className="mt-2 pt-2 border-t border-border/30 flex items-center justify-between text-[11px] text-muted-foreground">
                        <span className="truncate max-w-[70%]">
                          Origin: <strong className="text-foreground font-normal">{item.provenance?.origin || "Provenance unavailable"}</strong>
                        </span>
                        <span className="font-mono text-[10px]">
                          {item.created_at ? new Date(item.created_at).toLocaleString() : "Active"}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* "Why Does NOVA Remember This?" Modal */}
      {selectedWhyItem && (
        <Modal
          open={!!selectedWhyItem}
          onClose={() => setSelectedWhyItem(null)}
          title="Why Does NOVA Remember This?"
        >
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg bg-primary/10 border border-primary/30">
              <div className="flex items-center gap-2 text-xs font-semibold text-primary mb-1">
                <Brain className="size-4" /> Memory Record
              </div>
              <p className="text-sm font-medium text-foreground">{selectedWhyItem.title}</p>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{selectedWhyItem.content}</p>
            </div>

            <div className="space-y-2">
              <h5 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
                Authoritative Provenance & Rationale
              </h5>

              <div className="space-y-2 text-xs">
                <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                  <span className="text-muted-foreground block text-[11px]">System Rationale:</span>
                  <span className="text-foreground leading-relaxed">{selectedWhyItem.why_remembered}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                    <span className="text-muted-foreground block text-[11px]">Originating Source:</span>
                    <span className="font-medium text-foreground truncate block">{selectedWhyItem.provenance?.origin || "Provenance unavailable"}</span>
                  </div>
                  <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                    <span className="text-muted-foreground block text-[11px]">Verification State:</span>
                    <span className="font-mono text-emerald-400">{selectedWhyItem.provenance?.verification_state || "UNVERIFIED"}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                    <span className="text-muted-foreground block text-[11px]">Isolation Scope:</span>
                    <span className="text-foreground">{selectedWhyItem.provenance?.owner_scope || "User Scoped"}</span>
                  </div>
                  <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                    <span className="text-muted-foreground block text-[11px]">Lifecycle State:</span>
                    <span className="text-foreground font-semibold">{selectedWhyItem.lifecycle}</span>
                  </div>
                </div>

                {selectedWhyItem.created_at && (
                  <div className="p-2.5 rounded-md bg-muted/30 border border-border/40">
                    <span className="text-muted-foreground block text-[11px]">Timestamp:</span>
                    <span className="font-mono text-foreground">{new Date(selectedWhyItem.created_at).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/40">
              {selectedWhyItem.can_delete && (
                <Button
                  variant="outline"
                  onClick={() => {
                    handleForgetItem(selectedWhyItem);
                    setSelectedWhyItem(null);
                  }}
                  className="gap-2 text-danger hover:border-danger hover:bg-danger/10"
                >
                  <Trash2 className="size-4" /> Forget This Memory
                </Button>
              )}
              <Button variant="outline" onClick={() => setSelectedWhyItem(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Reset Buffer Confirmation Modal */}
      {showResetConfirmModal && (
        <Modal
          open={showResetConfirmModal}
          onClose={() => setShowResetConfirmModal(false)}
          title="Reset Active Conversational Session?"
        >
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg bg-danger/10 border border-danger/30 text-xs text-foreground space-y-2">
              <div className="flex items-center gap-2 font-semibold text-danger">
                <AlertCircle className="size-4" />
                Destructive Session Action
              </div>
              <p className="leading-relaxed">
                This will clear the active conversational session turns and reset the turn buffer to 0.
              </p>
              <div className="text-muted-foreground text-[11px] pt-1">
                <strong>Preservation Guarantee:</strong> This action will <em>NOT</em> delete organizational Stage-0 axioms, global knowledge documents, user preferences, security scans, or other users' sessions.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/40">
              <Button variant="outline" onClick={() => setShowResetConfirmModal(false)} disabled={isClearing}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmResetSession}
                isLoading={isClearing}
                className="gap-1.5 bg-danger hover:bg-danger/90 text-white"
              >
                <Trash2 className="size-4" />
                Confirm Reset Session
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Layer 3 User Preferences Modal */}
      {showPrefModal && (
        <Modal
          open={showPrefModal}
          onClose={() => setShowPrefModal(false)}
          title="Configure Layer 3 User Preferences"
        >
          <div className="space-y-4">
            <p className="text-xs text-muted-foreground">
              These preferences persist independently of conversation turns in PostgreSQL and survive logouts and service restarts.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-foreground mb-1 block">Department / Operational Context</label>
                <input
                  type="text"
                  value={preferences.department || ""}
                  onChange={(e) => setPreferences({ ...preferences, department: e.target.value })}
                  className="w-full text-xs px-3 py-2 rounded-md bg-muted/30 border border-border/60 text-foreground focus:outline-none focus:border-primary"
                  placeholder="e.g. Security Architecture & Engineering"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground mb-1 block">Language Preference</label>
                <input
                  type="text"
                  value={preferences.language || ""}
                  onChange={(e) => setPreferences({ ...preferences, language: e.target.value })}
                  className="w-full text-xs px-3 py-2 rounded-md bg-muted/30 border border-border/60 text-foreground focus:outline-none focus:border-primary"
                  placeholder="e.g. English (US)"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground mb-1 block">Assistant Communication Tone</label>
                <input
                  type="text"
                  value={preferences.tone || ""}
                  onChange={(e) => setPreferences({ ...preferences, tone: e.target.value })}
                  className="w-full text-xs px-3 py-2 rounded-md bg-muted/30 border border-border/60 text-foreground focus:outline-none focus:border-primary"
                  placeholder="e.g. Executive Technical Synthesis"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground mb-1 block">Context Scope</label>
                <input
                  type="text"
                  value={preferences.context_scope || ""}
                  onChange={(e) => setPreferences({ ...preferences, context_scope: e.target.value })}
                  className="w-full text-xs px-3 py-2 rounded-md bg-muted/30 border border-border/60 text-foreground focus:outline-none focus:border-primary"
                  placeholder="e.g. Full Enterprise Knowledge"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/40">
              <Button variant="outline" onClick={() => setShowPrefModal(false)} disabled={isSavingPref}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSavePreferences}
                isLoading={isSavingPref}
                className="gap-1.5"
              >
                <Check className="size-4" /> Save Preferences
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
