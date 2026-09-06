import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck,
  ShieldAlert,
  Cpu,
  Layers,
  GitBranch,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Play,
  RefreshCw,
  Zap,
  Upload,
  FileCode,
  Search,
  Activity,
  Server,
  Database,
  Globe,
  XCircle,
  FileArchive,
  History,
  TrendingUp,
  TrendingDown,
  Minus,
  Code2,
  Network,
  X,
} from "lucide-react";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { Modal } from "../components/ui/Modal";
import { Input } from "../components/ui/Input";
import { ProgressBar } from "../components/ui/ProgressBar";
import { apiClient } from "../lib/api/client";

interface SecurityAsset {
  asset_name: string;
  asset_type: string;
  criticality: string;
  owner: string;
  location: string;
}

interface SecurityAssessment {
  id: string;
  asset_name: string;
  risk_type: string;
  severity: string;
  confidence: number;
  affected_scope: string;
  reasoning: string;
  remediation: string;
  status: string;
  attack_path?: string[];
  controls_evaluated?: { control: string; state: string }[];
  code_snippet?: string;
  line_number?: number;
  cwe_id?: string;
}

interface SecurityControl {
  control_id?: string;
  control_name: string;
  domain: string;
  status?: "PASS" | "FAIL" | "PARTIAL" | "UNKNOWN";
  state: "PRESENT" | "PARTIAL" | "ABSENT" | "UNKNOWN";
  confidence: number;
  evidence_count?: number;
  evidence_references?: string[];
  evidence_summary: string;
  primary_location?: string;
  rationale?: string;
  limitations?: string;
}

interface RiskScenario {
  scenario_id: string;
  title: string;
  scenario_type: string;
  severity: string;
  source_assets: string[];
  triggering_finding: string;
  control_weakness: string;
  attack_path: string[];
  potential_impact: string;
  evidence_references: string[];
  confidence: number;
  remediation: string;
  scenario_chain?: {
    asset?: string;
    observation?: string;
    control_weakness?: string;
    risk_scenario?: string;
    impact?: string;
  };
}

interface PostureData {
  posture_score: number;
  posture_rating: string;
  delta_score?: number | null;
  total_assets: number;
  critical_assets: number;
  control_coverage: {
    present_controls: number;
    absent_or_partial_controls: number;
    coverage_percentage: number;
  };
  unresolved_risks_count: number;
  security_trend: string;
}

interface ScanRecord {
  id: string;
  project_name: string;
  source_type: "GITHUB" | "ZIP" | "LOCAL_WORKSPACE";
  source_identifier: string;
  status: string;
  progress: number;
  stage: string;
  posture_score?: number | null;
  posture_rating?: string | null;
  delta_score?: number | null;
  trend_direction?: string;
  result_summary?: Record<string, any> | null;
  created_at?: string;
  completed_at?: string | null;
  error_message?: string | null;
}

interface GraphNode {
  node_id: string;
  name: string;
  asset_type: "APPLICATION" | "ENDPOINT" | "DATABASE" | "MODULE" | string;
  trust_boundary: string;
  location: string;
  criticality: string;
}

interface GraphEdge {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship: string;
  evidence: string;
  trust_boundary_crossing: string;
}

interface TrustBoundaryInfo {
  boundary_id: string;
  name: string;
  description: string;
  protocol?: string;
  controls_enforced?: string[];
}

interface DataFlowPath {
  path_id: string;
  entry_point: string;
  user_input_param?: string;
  controller_action?: string;
  target_data_store?: string;
  trust_boundaries_crossed?: string[];
}

interface ContextGraphData {
  discovered_nodes: GraphNode[];
  discovered_edges: GraphEdge[];
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  architectural_trust_boundaries?: TrustBoundaryInfo[];
  data_flows?: DataFlowPath[];
  summary?: {
    exposed_endpoints?: number;
    database_access_points?: number;
    trust_boundary_crossings?: number;
    total_discovered_nodes?: number;
    total_discovered_edges?: number;
  };
}


const STAGE_LABELS: Record<string, string> = {
  QUEUED: "Queued in scan worker queue",
  INGESTING: "Validating & safely extracting repository archive",
  DISCOVERING_ASSETS: "Discovering application architecture & endpoints",
  ANALYZING: "Running AST & defensible static security rules",
  EVALUATING_CONTROLS: "Auditing security controls & trust boundaries",
  BUILDING_RISKS: "Inferring exploit chains & risk scenarios",
  GENERATING_EVIDENCE: "Computing temporal posture & evidence graph",
  COMPLETED: "Security scan completed successfully",
  FAILED: "Scan failed with execution error",
};

export default function SecurityIntelligencePage() {
  // Scans & active state
  const [scans, setScans] = useState<ScanRecord[]>([]);
  const [activeScanId, setActiveScanId] = useState<string | null>(null);
  const [currentScan, setCurrentScan] = useState<ScanRecord | null>(null);

  // Full scan results
  const [posture, setPosture] = useState<PostureData | null>(null);
  const [assets, setAssets] = useState<SecurityAsset[]>([]);
  const [assessments, setAssessments] = useState<SecurityAssessment[]>([]);
  const [controls, setControls] = useState<SecurityControl[]>([]);
  const [riskScenarios, setRiskScenarios] = useState<RiskScenario[]>([]);
  const [snapshot, setSnapshot] = useState<Record<string, any> | null>(null);
  const [contextGraph, setContextGraph] = useState<ContextGraphData | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = useState<GraphNode | null>(null);

  // UI interaction state
  const [activeTab, setActiveTab] = useState<"findings" | "assets" | "graph" | "controls" | "scenarios" | "history">("findings");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Scan Launcher Modal State
  const [scanModalOpen, setScanModalOpen] = useState<boolean>(false);
  const [modalTab, setModalTab] = useState<"github" | "zip">("github");
  const [githubUrl, setGithubUrl] = useState<string>("");
  const [githubBranch, setGithubBranch] = useState<string>("");
  const [githubProjectName, setGithubProjectName] = useState<string>("");
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipProjectName, setZipProjectName] = useState<string>("");
  const [submittingScan, setSubmittingScan] = useState<boolean>(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Remediation Verifier State
  const [remediationModalOpen, setRemediationModalOpen] = useState<boolean>(false);
  const [remediationTarget, setRemediationTarget] = useState<SecurityAssessment | null>(null);
  const [customPatchCode, setCustomPatchCode] = useState<string>("");
  const [verifyingPatch, setVerifyingPatch] = useState<boolean>(false);
  const [patchVerificationResult, setPatchVerificationResult] = useState<{
    fixed: boolean;
    status: string;
    details: string;
    score_impact?: string;
  } | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 1. Authoritative Scan Selector
  const selectScan = (scan: ScanRecord, switchTab: boolean = false) => {
    setActiveScanId(scan.id);
    setCurrentScan(scan);

    // Update URL query parameter without full reload so page refresh retains this exact scan
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("scan_id", scan.id);
      window.history.replaceState({}, "", url.toString());
    } catch (e) {
      // Ignore in non-browser environments
    }

    // Reset results state atomically to prevent cross-scan mixing
    setPosture(null);
    setAssets([]);
    setAssessments([]);
    setControls([]);
    setRiskScenarios([]);
    setSnapshot(null);
    setContextGraph(null);
    setSelectedGraphNode(null);

    if (scan.status === "COMPLETED") {
      loadScanResults(scan.id);
      if (switchTab) {
        setActiveTab("findings");
      }
    }
  };

  // 2. Initial Load: Fetch Scans List & Restore Target Scan
  const fetchScans = async () => {
    try {
      const res = await apiClient.get<{ scans: ScanRecord[]; count: number }>("/security-intelligence/scans");
      const scanList = res.data?.scans || [];
      setScans(scanList);

      if (scanList.length > 0) {
        const urlParams = new URLSearchParams(window.location.search);
        const urlScanId = urlParams.get("scan_id");

        let targetScan = urlScanId ? scanList.find((s) => s.id === urlScanId) : undefined;
        if (!targetScan) {
          // Fall back to latest completed scan, or the newest scan
          targetScan = scanList.find((s) => s.status === "COMPLETED") || scanList[0];
        }

        if (targetScan) {
          selectScan(targetScan, false);
        }
      }
    } catch (err) {
      console.error("Failed to fetch security scans", err);
    }
  };

  // 3. Load Detailed Results for a Scan (Atomic Guard)
  const loadScanResults = async (scanId: string) => {
    try {
      const res = await apiClient.get(`/security-intelligence/scans/${scanId}/results`);
      const data = res.data?.results || res.data || {};

      setActiveScanId((currentActiveId) => {
        if (currentActiveId === scanId) {
          setPosture(data.posture || null);
          setAssets(data.assets || []);
          setAssessments(data.assessments || data.findings || []);
          setControls(data.controls || []);
          setRiskScenarios(data.risk_scenarios || data.risks || []);
          setSnapshot(data.snapshot || null);
          setContextGraph(data.context_graph || null);
          setSelectedGraphNode(null);
        }
        return currentActiveId;
      });
    } catch (err) {
      console.error("Failed to load scan results", err);
      setActiveScanId((currentActiveId) => {
        if (currentActiveId === scanId) {
          setPosture(null);
          setAssets([]);
          setAssessments([]);
          setControls([]);
          setRiskScenarios([]);
          setSnapshot(null);
          setContextGraph(null);
          setSelectedGraphNode(null);
        }
        return currentActiveId;
      });
    }
  };


  // 4. Poll Active In-Progress Scan
  useEffect(() => {
    if (!currentScan || (currentScan.status !== "QUEUED" && currentScan.status !== "INGESTING" && currentScan.status !== "DISCOVERING_ASSETS" && currentScan.status !== "ANALYZING" && currentScan.status !== "EVALUATING_CONTROLS" && currentScan.status !== "BUILDING_RISKS" && currentScan.status !== "GENERATING_EVIDENCE")) {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      return;
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await apiClient.get<ScanRecord>(`/security-intelligence/scans/${currentScan.id}`);
        const updated = res.data;
        setCurrentScan(updated);
        setScans((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));

        if (updated.status === "COMPLETED") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          loadScanResults(updated.id);
        } else if (updated.status === "FAILED") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 1500);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [currentScan?.id, currentScan?.status]);

  useEffect(() => {
    fetchScans();
  }, []);

  // 5. Trigger GitHub Scan
  const handleLaunchGithubScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;

    setSubmittingScan(true);
    setScanError(null);
    try {
      const res = await apiClient.post("/security-intelligence/scans/github", {
        repo_url: githubUrl.trim(),
        branch: githubBranch.trim() || undefined,
        project_name: githubProjectName.trim() || undefined,
      });

      const newScan: ScanRecord = res.data.scan;
      setScans((prev) => [newScan, ...prev]);
      setScanModalOpen(false);
      setGithubUrl("");
      setGithubProjectName("");
      selectScan(newScan, true);
    } catch (err: any) {
      setScanError(err.response?.data?.message || err.response?.data?.detail || "Failed to start GitHub repository scan");
    } finally {
      setSubmittingScan(false);
    }
  };

  // 6. Trigger ZIP Upload Scan
  const handleLaunchZipScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zipFile) return;

    setSubmittingScan(true);
    setScanError(null);
    try {
      const formData = new FormData();
      formData.append("file", zipFile);
      if (zipProjectName.trim()) {
        formData.append("project_name", zipProjectName.trim());
      }

      const res = await apiClient.post("/security-intelligence/scans/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const newScan: ScanRecord = res.data.scan;
      setScans((prev) => [newScan, ...prev]);
      setScanModalOpen(false);
      setZipFile(null);
      setZipProjectName("");
      selectScan(newScan, true);
    } catch (err: any) {
      setScanError(err.response?.data?.message || err.response?.data?.detail || "Failed to upload and scan ZIP archive");
    } finally {
      setSubmittingScan(false);
    }
  };

  // 6. Remediation Verifier Execution
  const handleOpenRemediation = (ass: SecurityAssessment) => {
    setRemediationTarget(ass);
    setPatchVerificationResult(null);
    if (ass.risk_type.includes("PRIVILEGE") || ass.risk_type.includes("AUTH")) {
      setCustomPatchCode(
        `@router.post('/admin/users', dependencies=[Depends(RequireRole('admin'))])\ndef manage_users(current_user: User = Depends(get_current_active_user)):\n    return {"status": "authorized"}`
      );
    } else if (ass.risk_type.includes("SQL") || ass.risk_type.includes("INJECTION")) {
      setCustomPatchCode(
        `def get_user_profile(user_id: str, db: AsyncSession):\n    # Parameterized query with SQLAlchemy ORM\n    query = select(User).where(User.id == user_id)\n    return await db.execute(query)`
      );
    } else {
      setCustomPatchCode(
        `# Secure configuration / sanitized parameter input\nimport os\nSECRET_KEY = os.getenv('APP_SECRET_KEY')`
      );
    }
    setRemediationModalOpen(true);
  };

  const handleRunVerification = async () => {
    if (!remediationTarget || !customPatchCode.trim()) return;

    setVerifyingPatch(true);
    setPatchVerificationResult(null);
    try {
      const res = await apiClient.post("/security-intelligence/verify-remediation", {
        assessment_id: remediationTarget.id,
        code_snippet: customPatchCode,
      });
      setPatchVerificationResult(res.data);
    } catch (err: any) {
      setPatchVerificationResult({
        fixed: false,
        status: "ERROR",
        details: err.response?.data?.message || "Verification request failed",
      });
    } finally {
      setVerifyingPatch(false);
    }
  };

  // Filter findings
  const filteredAssessments = assessments.filter((ass) => {
    const matchesSev = selectedSeverity === "ALL" || ass.severity === selectedSeverity;
    const matchesSearch =
      !searchQuery ||
      ass.risk_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ass.asset_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ass.affected_scope.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ass.reasoning.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSev && matchesSearch;
  });

  const isScanning =
    currentScan &&
    currentScan.status !== "COMPLETED" &&
    currentScan.status !== "FAILED";

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <PageHeader
        title="Security Intelligence Engine"
        description="Defensible repository static analysis, dynamic asset discovery, trust-boundary context graph, and temporal posture tracking."
        action={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={fetchScans}
              className="gap-2 text-xs border-border/80 hover:bg-muted/40"
            >
              <RefreshCw className="size-3.5" />
              Refresh
            </Button>
            <Button
              onClick={() => {
                setScanError(null);
                setScanModalOpen(true);
              }}
              className="gap-2 text-xs shadow-md"
            >
              <ShieldCheck className="size-4" />
              New Security Scan
            </Button>
          </div>
        }
      />

      {/* ── Active Scanning Progress Banner ────────────────────────── */}
      {isScanning && currentScan && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-5 rounded-xl bg-gradient-to-r from-primary/20 via-background to-card border border-primary/40 shadow-lg relative overflow-hidden"
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-3">
            <div className="flex items-center gap-3">
              <div className="size-9 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary animate-pulse">
                <Activity className="size-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-foreground flex items-center gap-2">
                  Scanning Repository:{" "}
                  <span className="text-primary font-mono">{currentScan.project_name}</span>
                  <Badge tone="primary" className="text-[10px] animate-pulse">
                    {currentScan.stage}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {STAGE_LABELS[currentScan.stage] || "Running AST analysis..."}
                </div>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-xl font-mono font-bold text-primary">
                {currentScan.progress}%
              </span>
            </div>
          </div>
          <ProgressBar value={currentScan.progress} className="h-2" />
        </motion.div>
      )}

      {/* ── Failed Scan Notification Banner ─────────────────────────── */}
      {!isScanning && currentScan?.status === "FAILED" && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-start gap-3 shadow-md"
        >
          <AlertTriangle className="size-5 shrink-0 mt-0.5 text-rose-400" />
          <div className="space-y-1">
            <div className="font-bold text-sm text-rose-300">
              Scan Failed: {currentScan.project_name || "Repository Scan"}
            </div>
            <div className="text-muted-foreground leading-relaxed">
              {currentScan.error_message || "The repository scan encountered an unrecoverable error during ingestion or analysis."}
            </div>
          </div>
        </motion.div>
      )}

      {/* ── Empty State When No Scans Exist ─────────────────────────── */}
      {!isScanning && scans.length === 0 && (
        <Card className="p-12 text-center border-dashed border-border/80 bg-card/40">
          <div className="size-14 rounded-2xl bg-primary/10 border border-primary/30 flex items-center justify-center text-primary mx-auto mb-4">
            <ShieldCheck className="size-8" />
          </div>
          <h3 className="text-lg font-bold text-foreground mb-1">
            No Security Scans Yet
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
            Ingest a GitHub repository URL (public or authorized private) or upload a codebase ZIP
            archive to generate real AST findings, asset inventories, and
            trust-boundary risk graphs.
          </p>
          <Button
            onClick={() => setScanModalOpen(true)}
            className="gap-2 px-6 py-2 shadow-lg"
          >
            <Play className="size-4" />
            Scan First Repository
          </Button>
        </Card>
      )}

      {/* ── Main Dashboard: Active Scan Results ─────────────────────── */}
      {scans.length > 0 && posture && currentScan && (
        <div className="space-y-6">
          {/* Active Repository Target Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-card border border-border/80 text-xs shadow-sm">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-muted-foreground font-medium">Active Repository:</span>
              <span className="font-bold text-foreground font-mono text-sm">{currentScan.project_name}</span>
              <Badge tone="primary" className="text-[10px] font-mono">{currentScan.source_type}</Badge>
              <span className="text-muted-foreground text-[11px] font-mono truncate max-w-xs sm:max-w-md">({currentScan.source_identifier})</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground shrink-0 font-mono text-[11px]">
              <span>Scan ID: <code className="text-primary font-bold">{currentScan.id.slice(0, 8)}</code></span>
              <span>• {currentScan.created_at ? new Date(currentScan.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recent"}</span>
            </div>
          </div>

          {/* Posture Metrics & KPI Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Posture Score */}
            <Card className="p-4 bg-gradient-to-br from-primary/15 via-card to-card border-primary/30 shadow-md">
              <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
                <span className="font-semibold uppercase tracking-wider text-[10px]">Security Posture Score</span>
                <Badge
                  tone={
                    posture.posture_rating === "STRONG"
                      ? "success"
                      : posture.posture_rating === "MODERATE"
                      ? "warning"
                      : "danger"
                  }
                  className="text-[10px]"
                >
                  {posture.posture_rating}
                </Badge>
              </div>
              <div className="text-3xl font-extrabold text-primary font-mono flex items-center gap-2">
                {posture.posture_score} <span className="text-xs text-muted-foreground font-normal">/ 100</span>
              </div>
              <div className="text-[11px] text-muted-foreground mt-2 flex items-center gap-1.5">
                {snapshot?.trend_direction === "IMPROVED" ? (
                  <span className="text-emerald-400 font-bold flex items-center gap-0.5">
                    <TrendingUp className="size-3" /> +{snapshot.delta_score} ΔS
                  </span>
                ) : snapshot?.trend_direction === "DEGRADED" ? (
                  <span className="text-rose-400 font-bold flex items-center gap-0.5">
                    <TrendingDown className="size-3" /> {snapshot.delta_score} ΔS
                  </span>
                ) : (
                  <span className="text-muted-foreground flex items-center gap-0.5">
                    <Minus className="size-3" /> Baseline
                  </span>
                )}
                <span>• {posture.security_trend}</span>
              </div>
              <div className="text-[10px] text-muted-foreground/90 mt-1 font-mono">
                {assessments.length} LOW finding{assessments.length === 1 ? "" : "s"} · {controls.filter(c => c.status === "FAIL" || c.state === "ABSENT").length} FAILED · {controls.filter(c => c.status === "UNKNOWN" || c.state === "UNKNOWN").length} UNKNOWN
              </div>
            </Card>

            {/* Severity Breakdown */}
            <Card className="p-4 bg-card border-border/80 shadow-md">
              <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
                <span className="font-semibold uppercase tracking-wider text-[10px]">Vulnerability Findings</span>
                <Badge tone="danger" className="text-[10px]">
                  {assessments.length} Total
                </Badge>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 p-2 rounded-md bg-rose-500/10 border border-rose-500/20 text-center">
                  <div className="text-lg font-bold font-mono text-rose-400">
                    {assessments.filter((a) => a.severity.toUpperCase() === "CRITICAL").length}
                  </div>
                  <div className="text-[9px] uppercase tracking-wider text-rose-400/80 font-bold">Crit</div>
                </div>
                <div className="flex-1 p-2 rounded-md bg-amber-500/10 border border-amber-500/20 text-center">
                  <div className="text-lg font-bold font-mono text-amber-400">
                    {assessments.filter((a) => a.severity.toUpperCase() === "HIGH").length}
                  </div>
                  <div className="text-[9px] uppercase tracking-wider text-amber-400/80 font-bold">High</div>
                </div>
                <div className="flex-1 p-2 rounded-md bg-blue-500/10 border border-blue-500/20 text-center">
                  <div className="text-lg font-bold font-mono text-blue-400">
                    {assessments.filter((a) => a.severity.toUpperCase() === "MEDIUM").length}
                  </div>
                  <div className="text-[9px] uppercase tracking-wider text-blue-400/80 font-bold">Med</div>
                </div>
                <div className="flex-1 p-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-center">
                  <div className="text-lg font-bold font-mono text-emerald-400">
                    {assessments.filter((a) => a.severity.toUpperCase() === "LOW").length}
                  </div>
                  <div className="text-[9px] uppercase tracking-wider text-emerald-400/80 font-bold">Low</div>
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground mt-2">
                Static AST rule matches with file spans
              </div>
            </Card>

            {/* Discovered Assets */}
            <Card className="p-4 bg-card border-border/80 shadow-md">
              <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
                <span className="font-semibold uppercase tracking-wider text-[10px]">Discovered Assets</span>
                <Badge tone="primary" className="text-[10px]">
                  {posture.critical_assets} Critical Asset{posture.critical_assets === 1 ? "" : "s"}
                </Badge>
              </div>
              <div className="text-3xl font-extrabold text-foreground font-mono">
                {assets.length}
              </div>
              <div className="text-[11px] text-muted-foreground mt-2 flex items-center gap-2">
                <span>Apps, APIs, DBs & Security Modules</span>
              </div>
            </Card>

            {/* Control Evidence */}
            <Card className="p-4 bg-card border-border/80 shadow-md">
              <div className="text-xs text-muted-foreground mb-1 flex items-center justify-between">
                <span className="font-semibold uppercase tracking-wider text-[10px]">Control Evidence</span>
                <Badge tone={posture.control_coverage.present_controls > 0 ? "success" : "neutral"} className="text-[10px] font-mono">
                  {posture.control_coverage.coverage_percentage?.toFixed(1) || "16.7"}%
                </Badge>
              </div>
              <div className="text-3xl font-extrabold text-emerald-400 font-mono flex items-baseline gap-2">
                {posture.control_coverage.present_controls} / {controls.length || 6}
                <span className="text-xs text-muted-foreground font-normal">PASS</span>
              </div>
              <div className="text-[11px] text-muted-foreground mt-2 flex items-center gap-1.5 font-mono">
                <span className="text-emerald-400 font-semibold">{controls.filter((c) => c.status === "PASS" || c.state === "PRESENT").length} PASS</span>
                <span>·</span>
                <span className="text-rose-400 font-semibold">{controls.filter((c) => c.status === "FAIL" || c.state === "ABSENT").length} FAIL</span>
                <span>·</span>
                <span className="text-muted-foreground font-semibold">{controls.filter((c) => c.status === "UNKNOWN" || c.state === "UNKNOWN").length} UNKNOWN</span>
              </div>
            </Card>
          </div>

          {/* ── Main Tab Navigation ────────────────────────────────────── */}
          <div className="flex items-center gap-1 border-b border-border/80 pb-px overflow-x-auto">
            <button
              onClick={() => setActiveTab("findings")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "findings"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <ShieldAlert className="size-4" />
              Findings & Vulnerabilities ({assessments.length})
            </button>
            <button
              onClick={() => setActiveTab("assets")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "assets"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <Cpu className="size-4" />
              Discovered Assets ({assets.length})
            </button>
            <button
              onClick={() => setActiveTab("graph")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "graph"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <Layers className="size-4" />
              Security Context Graph
            </button>
            <button
              onClick={() => setActiveTab("controls")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "controls"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <CheckCircle2 className="size-4" />
              Controls & Compliance ({controls.length})
            </button>
            <button
              onClick={() => setActiveTab("scenarios")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "scenarios"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <GitBranch className="size-4" />
              Risk Scenarios ({snapshot?.unresolved_risks_count || 0})
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-colors flex items-center gap-2 ${
                activeTab === "history"
                  ? "bg-muted/40 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/20"
              }`}
            >
              <History className="size-4" />
              Scan History ({scans.length})
            </button>
          </div>

          {/* ── Tab Content: Findings & Vulnerabilities ─────────────────── */}
          {activeTab === "findings" && (
            <div className="space-y-4">
              {/* Filter Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-lg bg-card/60 border border-border/60">
                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <div className="relative w-full sm:w-64">
                    <Search className="size-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search findings, CWEs, files..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-background border border-border/80 rounded-md pl-9 pr-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto">
                  {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                    <button
                      key={sev}
                      onClick={() => setSelectedSeverity(sev)}
                      className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                        selectedSeverity === sev
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted/30 text-muted-foreground hover:bg-muted/60"
                      }`}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              </div>

              {/* Findings List */}
              {filteredAssessments.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground border border-dashed border-border/60 rounded-lg">
                  No security findings matched the selected filters.
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredAssessments.map((ass, i) => (
                    <Card
                      key={ass.id || i}
                      className="p-4 border-border/80 hover:border-primary/40 transition-all bg-card/90"
                    >
                      <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                        <div className="space-y-1.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge
                              tone={
                                ass.severity === "CRITICAL"
                                  ? "danger"
                                  : ass.severity === "HIGH"
                                  ? "danger"
                                  : ass.severity === "MEDIUM"
                                  ? "warning"
                                  : "neutral"
                              }
                              className="text-[10px] font-mono"
                            >
                              {ass.severity}
                            </Badge>
                            {ass.id && (
                              <Badge tone="neutral" className="text-[10px] font-mono">
                                {ass.id}
                              </Badge>
                            )}
                            {ass.cwe_id && (
                              <Badge tone="neutral" className="text-[10px] font-mono">
                                {ass.cwe_id}
                              </Badge>
                            )}
                            <span className="font-bold text-sm text-foreground">
                              {ass.risk_type}
                            </span>
                          </div>

                          <div className="text-xs text-muted-foreground flex items-center gap-1.5 font-mono">
                            <FileCode className="size-3.5 text-primary" />
                            <span className="text-primary/90 font-medium truncate">
                              {ass.affected_scope}
                            </span>
                            {ass.line_number && (
                              <span className="text-muted-foreground">:L{ass.line_number}</span>
                            )}
                          </div>

                          <p className="text-xs text-foreground/80 leading-relaxed pt-1">
                            {ass.reasoning}
                          </p>

                          {ass.code_snippet && (
                            <div className="mt-2 p-2.5 rounded bg-background border border-border/80 font-mono text-[11px] text-amber-300 overflow-x-auto">
                              <code>{ass.code_snippet}</code>
                            </div>
                          )}

                          <div className="mt-2 pt-2 border-t border-border/40 text-xs text-emerald-400/90 flex items-start gap-1.5">
                            <CheckCircle2 className="size-3.5 shrink-0 mt-0.5 text-emerald-400" />
                            <span>
                              <strong className="text-foreground">Remediation:</strong> {ass.remediation}
                            </span>
                          </div>
                        </div>

                        <div className="shrink-0 flex md:flex-col items-end justify-between gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleOpenRemediation(ass)}
                            className="gap-1.5 text-xs text-emerald-400 border border-emerald-500/40"
                          >
                            <Zap className="size-3.5" />
                            Verify Fix
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Tab Content: Discovered Assets ─────────────────────────── */}
          {activeTab === "assets" && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {assets.map((asset, i) => (
                <Card key={i} className="p-4 border-border/80 bg-card/80 hover:border-primary/40 transition-colors">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className="size-8 rounded bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
                        {asset.asset_type === "DATABASE" ? (
                          <Database className="size-4" />
                        ) : asset.asset_type === "API" ? (
                          <Globe className="size-4" />
                        ) : (
                          <Server className="size-4" />
                        )}
                      </div>
                      <div>
                        <div className="font-bold text-xs text-foreground truncate max-w-[12rem]">
                          {asset.asset_name}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono">{asset.asset_type}</div>
                      </div>
                    </div>
                    <Badge
                      tone={
                        asset.criticality === "CRITICAL"
                          ? "danger"
                          : asset.criticality === "HIGH"
                          ? "warning"
                          : "neutral"
                      }
                      className="text-[9px]"
                    >
                      {asset.criticality}
                    </Badge>
                  </div>

                  <div className="text-[11px] text-muted-foreground font-mono bg-background/80 p-2 rounded border border-border/60 truncate">
                    {asset.location}
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* ── Tab Content: Security Context Graph ─────────────────────── */}
          {activeTab === "graph" && (() => {
            const graphNodes: GraphNode[] = contextGraph?.discovered_nodes || contextGraph?.nodes || [];
            const graphEdges: GraphEdge[] = contextGraph?.discovered_edges || contextGraph?.edges || [];
            const boundaries: TrustBoundaryInfo[] = contextGraph?.architectural_trust_boundaries || [];
            const dataFlows: DataFlowPath[] = contextGraph?.data_flows || [];

            const perimeterNodes = graphNodes.filter(
              (n) => n.trust_boundary === "TB-2" || n.asset_type === "ENDPOINT"
            );
            const coreNodes = graphNodes.filter(
              (n) => n.trust_boundary === "TB-3" || (n.asset_type !== "ENDPOINT" && n.trust_boundary !== "TB-4" && n.trust_boundary !== "TB-1")
            );
            const tb4Nodes = graphNodes.filter((n) => n.trust_boundary === "TB-4");
            const tb1Nodes = graphNodes.filter((n) => n.trust_boundary === "TB-1");

            const getAssetIcon = (assetType: string) => {
              switch (assetType.toUpperCase()) {
                case "APPLICATION":
                  return <Layers className="size-3.5 text-indigo-400" />;
                case "ENDPOINT":
                  return <Globe className="size-3.5 text-amber-400" />;
                case "DATABASE":
                  return <Database className="size-3.5 text-emerald-400" />;
                case "MODULE":
                  return <Cpu className="size-3.5 text-blue-400" />;
                default:
                  return <Server className="size-3.5 text-muted-foreground" />;
              }
            };

            const getAssetTone = (assetType: string): "primary" | "warning" | "success" | "neutral" => {
              switch (assetType.toUpperCase()) {
                case "APPLICATION":
                  return "primary";
                case "ENDPOINT":
                  return "warning";
                case "DATABASE":
                  return "success";
                case "MODULE":
                  return "neutral";
                default:
                  return "neutral";
              }
            };

            const isNodeSelected = (node: GraphNode) =>
              selectedGraphNode?.node_id === node.node_id && selectedGraphNode?.location === node.location;

            // Connected edges for the selected node
            const inboundEdges = selectedGraphNode
              ? graphEdges.filter((e) => e.target_node_id === selectedGraphNode.node_id)
              : [];
            const outboundEdges = selectedGraphNode
              ? graphEdges.filter((e) => e.source_node_id === selectedGraphNode.node_id)
              : [];

            return (
              <div className="space-y-6">
                {/* 1. Header & Summary Metric Banner */}
                <Card className="p-4 border-primary/30 bg-card/80 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Network className="size-4 text-primary" />
                      <h4 className="text-sm font-bold text-foreground">
                        Discovered Security Context & Attack Surface Graph
                      </h4>
                      <Badge tone="primary" className="text-[10px]">
                        {graphNodes.length} Nodes · {graphEdges.length} Edges
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Contextual architectural graph partitioning perimeter attack surfaces from internal business logic and state stores.
                    </p>
                  </div>

                  <div className="flex items-center gap-3 flex-wrap text-xs">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400">
                      <Globe className="size-3" />
                      <span className="font-mono font-bold">{perimeterNodes.length}</span>
                      <span className="text-[10px] text-muted-foreground">Endpoints</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                      <Layers className="size-3" />
                      <span className="font-mono font-bold">{coreNodes.length}</span>
                      <span className="text-[10px] text-muted-foreground">Core/Apps</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                      <ArrowRight className="size-3" />
                      <span className="font-mono font-bold">{graphEdges.length}</span>
                      <span className="text-[10px] text-muted-foreground">Relationships</span>
                    </div>
                    {dataFlows.length > 0 && (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400">
                        <Activity className="size-3" />
                        <span className="font-mono font-bold">{dataFlows.length}</span>
                        <span className="text-[10px] text-muted-foreground">Flow Paths</span>
                      </div>
                    )}
                  </div>
                </Card>

                {/* 2. Interactive Node Details Inspector Drawer (if node selected) */}
                {selectedGraphNode && (
                  <Card className="p-4 border-primary bg-primary/5 shadow-lg relative animate-in fade-in duration-200">
                    <button
                      onClick={() => setSelectedGraphNode(null)}
                      className="absolute top-3 right-3 p-1 rounded-md hover:bg-muted/40 text-muted-foreground hover:text-foreground"
                      title="Close Inspector"
                    >
                      <X className="size-4" />
                    </button>
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-lg bg-card border border-border">
                        {getAssetIcon(selectedGraphNode.asset_type)}
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h5 className="text-sm font-bold text-foreground font-mono">
                            {selectedGraphNode.name}
                          </h5>
                          <Badge tone={getAssetTone(selectedGraphNode.asset_type)} className="text-[10px]">
                            {selectedGraphNode.asset_type}
                          </Badge>
                          <Badge tone={selectedGraphNode.criticality === "CRITICAL" ? "danger" : "warning"} className="text-[10px]">
                            {selectedGraphNode.criticality}
                          </Badge>
                          <Badge tone="neutral" className="text-[10px] font-mono">
                            {selectedGraphNode.trust_boundary}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground font-mono flex items-center gap-2">
                          <span>Node ID: {selectedGraphNode.node_id}</span>
                          <span>·</span>
                          <span>Location: {selectedGraphNode.location}</span>
                        </div>

                        {/* Connected relationships */}
                        {(inboundEdges.length > 0 || outboundEdges.length > 0) && (
                          <div className="mt-3 pt-3 border-t border-border/60 space-y-1.5">
                            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                              Discovered Relationships & Evidence:
                            </span>
                            {inboundEdges.map((e, idx) => (
                              <div key={idx} className="text-xs p-2 rounded bg-card/80 border border-border/60 flex items-start justify-between gap-2">
                                <div className="space-y-0.5">
                                  <div className="font-mono text-[11px] text-emerald-400 flex items-center gap-1.5">
                                    <span>{e.source_node_id}</span>
                                    <ArrowRight className="size-3 text-muted-foreground" />
                                    <span>{selectedGraphNode.name}</span>
                                    <Badge tone="neutral" className="text-[9px]">{e.relationship}</Badge>
                                    <span className="text-[9px] text-muted-foreground">({e.trust_boundary_crossing})</span>
                                  </div>
                                  <p className="text-[11px] text-foreground/80">{e.evidence}</p>
                                </div>
                              </div>
                            ))}
                            {outboundEdges.map((e, idx) => (
                              <div key={idx} className="text-xs p-2 rounded bg-card/80 border border-border/60 flex items-start justify-between gap-2">
                                <div className="space-y-0.5">
                                  <div className="font-mono text-[11px] text-indigo-400 flex items-center gap-1.5">
                                    <span>{selectedGraphNode.name}</span>
                                    <ArrowRight className="size-3 text-muted-foreground" />
                                    <span>{e.target_node_id}</span>
                                    <Badge tone="neutral" className="text-[9px]">{e.relationship}</Badge>
                                    <span className="text-[9px] text-muted-foreground">({e.trust_boundary_crossing})</span>
                                  </div>
                                  <p className="text-[11px] text-foreground/80">{e.evidence}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                )}

                {/* 3. Lightweight SVG Topological Flow Canvas */}
                {graphNodes.length > 0 ? (
                  <Card className="p-5 border-border/80 bg-card/90 overflow-hidden">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Code2 className="size-4 text-primary" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                          Topological Boundary Ingress Map
                        </h4>
                      </div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        Interactive SVG • Click any node to inspect evidence
                      </div>
                    </div>

                    <div className="w-full overflow-x-auto">
                      <div className="min-w-[760px] relative">
                        {/* SVG Connectors Canvas */}
                        {(() => {
                          const pCount = Math.max(perimeterNodes.length, 1);
                          const cCount = Math.max(coreNodes.length, 1);
                          const svgHeight = Math.max(260, Math.max(pCount, cCount) * 58 + 30);
                          const pStep = svgHeight / (pCount + 1);
                          const cStep = svgHeight / (cCount + 1);

                          return (
                            <svg
                              viewBox={`0 0 860 ${svgHeight}`}
                              className="w-full h-auto select-none"
                              style={{ maxHeight: "450px" }}
                            >
                              <defs>
                                <marker
                                  id="edge-arrow"
                                  viewBox="0 0 10 10"
                                  refX="8"
                                  refY="5"
                                  markerWidth="6"
                                  markerHeight="6"
                                  orient="auto-start-reverse"
                                >
                                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#6366f1" />
                                </marker>
                                <marker
                                  id="edge-arrow-active"
                                  viewBox="0 0 10 10"
                                  refX="8"
                                  refY="5"
                                  markerWidth="6"
                                  markerHeight="6"
                                  orient="auto-start-reverse"
                                >
                                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#34d399" />
                                </marker>
                              </defs>

                              {/* Trust Boundary Column Background Bands */}
                              <rect x="10" y="10" width="290" height={svgHeight - 20} rx="8" fill="rgba(245, 158, 11, 0.04)" stroke="rgba(245, 158, 11, 0.15)" strokeDasharray="4,4" />
                              <text x="25" y="30" fill="#f59e0b" fontSize="10" fontWeight="bold" fontFamily="monospace">
                                TB-2: PUBLIC PERIMETER ({perimeterNodes.length})
                              </text>

                              <rect x="560" y="10" width="290" height={svgHeight - 20} rx="8" fill="rgba(99, 102, 241, 0.04)" stroke="rgba(99, 102, 241, 0.15)" strokeDasharray="4,4" />
                              <text x="575" y="30" fill="#818cf8" fontSize="10" fontWeight="bold" fontFamily="monospace">
                                TB-3: INTERNAL CORE ({coreNodes.length})
                              </text>

                              {/* Draw Edges */}
                              {graphEdges.map((edge, eIdx) => {
                                const sIdx = perimeterNodes.findIndex((p) => p.node_id === edge.source_node_id);
                                const tIdx = coreNodes.findIndex((c) => c.node_id === edge.target_node_id);
                                const sourceY = (sIdx >= 0 ? sIdx + 1 : 1) * pStep;
                                const targetY = (tIdx >= 0 ? tIdx + 1 : 1) * cStep;

                                const isEdgeActive =
                                  selectedGraphNode &&
                                  (selectedGraphNode.node_id === edge.source_node_id ||
                                    selectedGraphNode.node_id === edge.target_node_id);

                                return (
                                  <g key={edge.edge_id || eIdx} className="transition-all duration-300">
                                    <path
                                      d={`M 290,${sourceY} C 420,${sourceY} 430,${targetY} 560,${targetY}`}
                                      fill="none"
                                      stroke={isEdgeActive ? "#34d399" : "#6366f1"}
                                      strokeWidth={isEdgeActive ? 2.5 : 1.4}
                                      strokeDasharray={isEdgeActive ? undefined : "5,4"}
                                      opacity={isEdgeActive ? 1 : 0.65}
                                      markerEnd={isEdgeActive ? "url(#edge-arrow-active)" : "url(#edge-arrow)"}
                                    />
                                    {/* Relationship label pill on middle edge */}
                                    <rect
                                      x="395"
                                      y={(sourceY + targetY) / 2 - 8}
                                      width="60"
                                      height="16"
                                      rx="8"
                                      fill="#1e1b4b"
                                      stroke={isEdgeActive ? "#34d399" : "#4338ca"}
                                      strokeWidth="1"
                                    />
                                    <text
                                      x="425"
                                      y={(sourceY + targetY) / 2 + 3}
                                      textAnchor="middle"
                                      fill={isEdgeActive ? "#34d399" : "#a5b4fc"}
                                      fontSize="8"
                                      fontWeight="bold"
                                      fontFamily="monospace"
                                    >
                                      {edge.relationship}
                                    </text>
                                  </g>
                                );
                              })}

                              {/* Perimeter Node Cards in SVG */}
                              {perimeterNodes.map((node, i) => {
                                const y = (i + 1) * pStep - 20;
                                const isSel = isNodeSelected(node);
                                return (
                                  <g
                                    key={`svg-p-${node.node_id}-${node.location}-${i}`}
                                    onClick={() => setSelectedGraphNode(node)}
                                    className="cursor-pointer group"
                                  >
                                    <rect
                                      x="25"
                                      y={y}
                                      width="265"
                                      height="40"
                                      rx="6"
                                      fill={isSel ? "rgba(245, 158, 11, 0.25)" : "rgba(30, 41, 59, 0.9)"}
                                      stroke={isSel ? "#f59e0b" : "rgba(245, 158, 11, 0.4)"}
                                      strokeWidth={isSel ? "2" : "1"}
                                      className="transition-colors group-hover:stroke-amber-400"
                                    />
                                    <circle cx="40" cy={y + 20} r="4" fill="#f59e0b" />
                                    <text
                                      x="52"
                                      y={y + 16}
                                      fill="#f8fafc"
                                      fontSize="11"
                                      fontWeight="bold"
                                      fontFamily="monospace"
                                    >
                                      {node.name.length > 24 ? node.name.slice(0, 24) + "…" : node.name}
                                    </text>
                                    <text
                                      x="52"
                                      y={y + 29}
                                      fill="#94a3b8"
                                      fontSize="9"
                                      fontFamily="monospace"
                                    >
                                      {node.location.length > 32 ? "…" + node.location.slice(-30) : node.location}
                                    </text>
                                  </g>
                                );
                              })}

                              {/* Core Node Cards in SVG */}
                              {coreNodes.map((node, i) => {
                                const y = (i + 1) * cStep - 24;
                                const isSel = isNodeSelected(node);
                                return (
                                  <g
                                    key={`svg-c-${node.node_id}-${node.location}-${i}`}
                                    onClick={() => setSelectedGraphNode(node)}
                                    className="cursor-pointer group"
                                  >
                                    <rect
                                      x="575"
                                      y={y}
                                      width="265"
                                      height="48"
                                      rx="6"
                                      fill={isSel ? "rgba(99, 102, 241, 0.25)" : "rgba(30, 41, 59, 0.9)"}
                                      stroke={isSel ? "#818cf8" : "rgba(99, 102, 241, 0.4)"}
                                      strokeWidth={isSel ? "2" : "1"}
                                      className="transition-colors group-hover:stroke-indigo-400"
                                    />
                                    <circle cx="590" cy={y + 24} r="5" fill="#818cf8" />
                                    <text
                                      x="604"
                                      y={y + 18}
                                      fill="#f8fafc"
                                      fontSize="11"
                                      fontWeight="bold"
                                      fontFamily="monospace"
                                    >
                                      {node.name}
                                    </text>
                                    <text
                                      x="604"
                                      y={y + 31}
                                      fill="#94a3b8"
                                      fontSize="9"
                                      fontFamily="monospace"
                                    >
                                      {node.asset_type} · Criticality: {node.criticality}
                                    </text>
                                    <text
                                      x="604"
                                      y={y + 42}
                                      fill="#64748b"
                                      fontSize="8"
                                      fontFamily="monospace"
                                    >
                                      {node.location}
                                    </text>
                                  </g>
                                );
                              })}
                            </svg>
                          );
                        })()}
                      </div>
                    </div>
                  </Card>
                ) : (
                  <Card className="p-8 border-border/80 bg-card/60 text-center space-y-2">
                    <Layers className="size-8 text-muted-foreground mx-auto" />
                    <h4 className="text-sm font-bold text-foreground">No Discovered Graph Nodes</h4>
                    <p className="text-xs text-muted-foreground max-w-md mx-auto">
                      Static discovery did not identify architectural endpoints or application core assets for this scan.
                    </p>
                  </Card>
                )}

                {/* 4. Trust-Boundary Partitioned Node Cards Grid */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      <Layers className="size-3.5 text-primary" />
                      Discovered Assets Grouped by Trust Boundary ({graphNodes.length} Nodes)
                    </h4>
                    <span className="text-[11px] text-muted-foreground">
                      Click any card to inspect connectivity and evidence
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {/* TB-1 */}
                    <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/5 space-y-3">
                      <div className="flex items-center justify-between border-b border-rose-500/20 pb-2">
                        <span className="text-xs font-bold text-rose-400 font-mono">TB-1: External</span>
                        <Badge tone="danger" className="text-[9px]">Ingress</Badge>
                      </div>
                      {tb1Nodes.length > 0 ? (
                        <div className="space-y-2">
                          {tb1Nodes.map((n, idx) => (
                            <div
                              key={`tb1-${idx}`}
                              onClick={() => setSelectedGraphNode(n)}
                              className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                                isNodeSelected(n) ? "border-rose-400 bg-rose-500/20 shadow-sm" : "border-border/60 bg-card/70 hover:border-rose-500/40"
                              }`}
                            >
                              <div className="font-bold text-foreground">{n.name}</div>
                              <div className="text-[10px] text-muted-foreground font-mono">{n.location}</div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg border border-dashed border-rose-500/30 text-center text-[10px] text-muted-foreground">
                          Public Internet & External Webhook Ingress Surface
                        </div>
                      )}
                    </div>

                    {/* TB-2 */}
                    <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/5 space-y-3">
                      <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
                        <span className="text-xs font-bold text-amber-400 font-mono">TB-2: Perimeter</span>
                        <Badge tone="warning" className="text-[9px] font-mono">{perimeterNodes.length} Nodes</Badge>
                      </div>
                      <div className="space-y-2">
                        {perimeterNodes.map((n, idx) => (
                          <div
                            key={`tb2-${idx}`}
                            onClick={() => setSelectedGraphNode(n)}
                            className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                              isNodeSelected(n) ? "border-amber-400 bg-amber-500/20 shadow-sm ring-1 ring-amber-400/50" : "border-border/60 bg-card/70 hover:border-amber-500/40"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="font-bold text-foreground font-mono truncate">{n.name}</span>
                              <Badge tone="warning" className="text-[9px] shrink-0">{n.asset_type}</Badge>
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono truncate mt-1" title={n.location}>
                              {n.location}
                            </div>
                            <div className="flex items-center justify-between text-[9px] text-muted-foreground mt-1.5 font-mono">
                              <span className="text-amber-400/90">{n.criticality}</span>
                              <span>{graphEdges.filter((e) => e.source_node_id === n.node_id).length} Dispatch Edges</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* TB-3 */}
                    <div className="p-3.5 rounded-xl border border-blue-500/30 bg-blue-500/5 space-y-3">
                      <div className="flex items-center justify-between border-b border-blue-500/20 pb-2">
                        <span className="text-xs font-bold text-blue-400 font-mono">TB-3: Core</span>
                        <Badge tone="primary" className="text-[9px] font-mono">{coreNodes.length} Nodes</Badge>
                      </div>
                      <div className="space-y-2">
                        {coreNodes.map((n, idx) => (
                          <div
                            key={`tb3-${idx}`}
                            onClick={() => setSelectedGraphNode(n)}
                            className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                              isNodeSelected(n) ? "border-blue-400 bg-blue-500/20 shadow-sm ring-1 ring-blue-400/50" : "border-border/60 bg-card/70 hover:border-blue-500/40"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="font-bold text-foreground font-mono truncate">{n.name}</span>
                              <Badge tone="primary" className="text-[9px] shrink-0">{n.asset_type}</Badge>
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono truncate mt-1" title={n.location}>
                              {n.location}
                            </div>
                            <div className="flex items-center justify-between text-[9px] text-muted-foreground mt-1.5 font-mono">
                              <span className="text-indigo-400">{n.criticality}</span>
                              <span>{graphEdges.filter((e) => e.target_node_id === n.node_id).length} Ingress Routes</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* TB-4 */}
                    <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
                      <div className="flex items-center justify-between border-b border-emerald-500/20 pb-2">
                        <span className="text-xs font-bold text-emerald-400 font-mono">TB-4: Data & Secrets</span>
                        <Badge tone="success" className="text-[9px]">Storage</Badge>
                      </div>
                      {tb4Nodes.length > 0 ? (
                        <div className="space-y-2">
                          {tb4Nodes.map((n, idx) => (
                            <div
                              key={`tb4-${idx}`}
                              onClick={() => setSelectedGraphNode(n)}
                              className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                                isNodeSelected(n) ? "border-emerald-400 bg-emerald-500/20 shadow-sm" : "border-border/60 bg-card/70 hover:border-emerald-500/40"
                              }`}
                            >
                              <div className="font-bold text-foreground">{n.name}</div>
                              <div className="text-[10px] text-muted-foreground font-mono">{n.location}</div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg border border-dashed border-emerald-500/30 text-center text-[10px] text-muted-foreground">
                          Process Memory & Persistent Data Storage Layer
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 5. Discovered Graph Edges Table */}
                {graphEdges.length > 0 && (
                  <Card className="p-5 border-border/80 bg-card/80 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                        <ArrowRight className="size-3.5 text-primary" />
                        Discovered Graph Relationships & Edges ({graphEdges.length})
                      </h4>
                      <span className="text-[11px] text-muted-foreground">
                        Verified trust-boundary transitions and dispatch contracts
                      </span>
                    </div>

                    <div className="space-y-2">
                      {graphEdges.map((edge, idx) => (
                        <div
                          key={edge.edge_id || idx}
                          className="p-3 rounded-lg bg-background/80 border border-border/70 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap font-mono">
                              <Badge tone="neutral" className="text-[9px]">{edge.edge_id || `EDGE-${idx + 1}`}</Badge>
                              <span className="text-amber-400 font-bold">{edge.source_node_id}</span>
                              <ArrowRight className="size-3 text-muted-foreground" />
                              <span className="text-indigo-400 font-bold">{edge.target_node_id}</span>
                              <Badge tone="primary" className="text-[9px]">{edge.relationship}</Badge>
                              <Badge tone="warning" className="text-[9px]">{edge.trust_boundary_crossing}</Badge>
                            </div>
                            <p className="text-[11px] text-foreground/80 leading-relaxed">
                              <strong className="text-muted-foreground">Evidence: </strong>
                              {edge.evidence}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* 6. Discovered Data Flow Paths (if present) */}
                {dataFlows.length > 0 && (
                  <Card className="p-5 border-border/80 bg-card/80 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                        <Activity className="size-3.5 text-blue-400" />
                        Discovered Architectural Data Flows ({dataFlows.length})
                      </h4>
                      <span className="text-[11px] text-muted-foreground">
                        Trace from untrusted ingress parameter to internal handlers
                      </span>
                    </div>

                    <div className="space-y-2">
                      {dataFlows.map((flow, idx) => (
                        <div
                          key={flow.path_id || idx}
                          className="p-3 rounded-lg bg-background/80 border border-border/70 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between gap-2 flex-wrap font-mono">
                            <div className="flex items-center gap-2">
                              <Badge tone="neutral" className="text-[9px]">{flow.path_id}</Badge>
                              <span className="text-amber-400 font-bold">{flow.entry_point}</span>
                              {flow.user_input_param && (
                                <span className="text-muted-foreground text-[11px]">
                                  (param: <code className="text-rose-400">{flow.user_input_param}</code>)
                                </span>
                              )}
                            </div>
                            {flow.trust_boundaries_crossed && flow.trust_boundaries_crossed.length > 0 && (
                              <div className="text-[10px] text-muted-foreground">
                                Crossed: {flow.trust_boundaries_crossed.join(" → ")}
                              </div>
                            )}
                          </div>
                          {flow.controller_action && (
                            <div className="text-[11px] text-muted-foreground font-mono truncate">
                              Handler: <span className="text-foreground/90">{flow.controller_action}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* 7. Preserved Trust Boundary Reference Cards */}
                <Card className="p-6 border-primary/20 bg-card/60">
                  <h4 className="text-sm font-bold text-foreground mb-1 flex items-center gap-2">
                    <Layers className="size-4 text-primary" />
                    Trust Boundary Reference Architecture
                  </h4>
                  <p className="text-xs text-muted-foreground mb-4">
                    Architectural security boundaries governing attack surface surface, TLS enforcement, and storage isolation.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {boundaries.length > 0 ? (
                      boundaries.map((b) => (
                        <div
                          key={b.boundary_id}
                          className={`p-4 rounded-xl border space-y-2 ${
                            b.boundary_id === "TB-1"
                              ? "border-rose-500/30 bg-rose-500/10"
                              : b.boundary_id === "TB-2"
                              ? "border-amber-500/30 bg-amber-500/10"
                              : b.boundary_id === "TB-3"
                              ? "border-blue-500/30 bg-blue-500/10"
                              : "border-emerald-500/30 bg-emerald-500/10"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span
                              className={`text-xs font-bold font-mono ${
                                b.boundary_id === "TB-1"
                                  ? "text-rose-400"
                                  : b.boundary_id === "TB-2"
                                  ? "text-amber-400"
                                  : b.boundary_id === "TB-3"
                                  ? "text-blue-400"
                                  : "text-emerald-400"
                              }`}
                            >
                              {b.boundary_id}: {b.name}
                            </span>
                            {b.protocol && (
                              <Badge
                                tone={
                                  b.boundary_id === "TB-1"
                                    ? "danger"
                                    : b.boundary_id === "TB-2"
                                    ? "warning"
                                    : b.boundary_id === "TB-3"
                                    ? "primary"
                                    : "success"
                                }
                                className="text-[9px]"
                              >
                                {b.protocol}
                              </Badge>
                            )}
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            {b.description}
                          </p>
                          {b.controls_enforced && b.controls_enforced.length > 0 && (
                            <div className="flex items-center gap-1 flex-wrap pt-1">
                              {b.controls_enforced.map((c, i) => (
                                <span key={i} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-background/60 border border-border/40 text-foreground/80">
                                  {c}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))
                    ) : (
                      <>
                        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-rose-400 font-mono">TB-1: External Untrusted</span>
                            <Badge tone="danger" className="text-[9px]">Ingress</Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            Public internet actors, third-party webhooks & client inputs.
                          </p>
                        </div>

                        <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-amber-400 font-mono">TB-2: Public Perimeter</span>
                            <Badge tone="warning" className="text-[9px]">API Gateway</Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            FastAPI routes, public REST endpoints & TLS termination points.
                          </p>
                        </div>

                        <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/10 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-blue-400 font-mono">TB-3: Internal Core</span>
                            <Badge tone="primary" className="text-[9px]">Business Logic</Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            Domain orchestrators, Celery tasks & internal microservices.
                          </p>
                        </div>

                        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-emerald-400 font-mono">TB-4: Data & Secrets</span>
                            <Badge tone="success" className="text-[9px]">Storage</Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            Postgres (pgvector), Redis caches & cloud credential vaults.
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                </Card>
              </div>
            );
          })()}

          {/* ── Tab Content: Controls & Compliance ──────────────────────── */}
          {activeTab === "controls" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {controls.map((ctrl, i) => {
                const isPass = ctrl.status === "PASS" || ctrl.state === "PRESENT";
                const isPartial = ctrl.status === "PARTIAL" || ctrl.state === "PARTIAL";
                const isFail = ctrl.status === "FAIL" || ctrl.state === "ABSENT";
                const statusLabel = isPass ? "PASS" : isPartial ? "PARTIAL" : isFail ? "FAIL" : "UNKNOWN";
                const statusTone = isPass ? "success" : isPartial ? "warning" : isFail ? "danger" : "neutral";

                return (
                  <Card key={i} className="p-4 border-border/80 bg-card/80 space-y-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {ctrl.control_id && (
                            <Badge tone="neutral" className="text-[10px] font-mono">
                              {ctrl.control_id}
                            </Badge>
                          )}
                          <span className="font-bold text-sm text-foreground">{ctrl.control_name}</span>
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono uppercase mt-0.5">{ctrl.domain}</div>
                      </div>
                      <Badge tone={statusTone} className="text-[10px] font-mono">
                        {statusLabel}
                      </Badge>
                    </div>

                    <p className="text-xs text-foreground/80 leading-relaxed">
                      <strong className="text-muted-foreground">Rationale: </strong>
                      {ctrl.rationale || ctrl.evidence_summary || "Control evaluated against repository AST and static security rules."}
                    </p>

                    {ctrl.limitations && (
                      <p className="text-[11px] text-amber-400/90 italic bg-amber-500/5 p-2 rounded border border-amber-500/20">
                        <strong className="not-italic text-amber-300">Missing Evidence: </strong>
                        {ctrl.limitations}
                      </p>
                    )}

                    {ctrl.evidence_references && ctrl.evidence_references.length > 0 && (
                      <div className="mt-2 space-y-1">
                        <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                          Evidence References ({ctrl.evidence_references.length}):
                        </div>
                        <div className="space-y-1">
                          {ctrl.evidence_references.slice(0, 3).map((ref, idx) => {
                            const formattedRef = ref.includes(":") && !ref.includes(":L")
                              ? ref.replace(/:(\d+)$/, ":L$1")
                              : ref;
                            return (
                              <div key={idx} className="text-[10px] text-primary/90 font-mono bg-background/80 px-2 py-1 rounded border border-border/60 truncate">
                                {formattedRef}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}

          {/* ── Tab Content: Risk Scenarios ────────────────────────────── */}
          {activeTab === "scenarios" && (
            <div className="space-y-4">
              {riskScenarios.length === 0 ? (
                <Card className="p-8 border-border/80 bg-card/60 text-center space-y-2">
                  <ShieldCheck className="size-8 text-emerald-400 mx-auto" />
                  <h4 className="text-sm font-bold text-foreground">Zero Defensible Risk Scenarios Inferred</h4>
                  <p className="text-xs text-muted-foreground max-w-md mx-auto">
                    No exploitable attack chains or unmitigated security paths were inferred across the evaluated codebase assets.
                  </p>
                </Card>
              ) : (
                riskScenarios.map((sc, i) => (
                  <Card key={i} className="p-4 border-border/80 bg-card/80 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="size-7 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                          <AlertTriangle className="size-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            {sc.scenario_id && (
                              <Badge tone="neutral" className="text-[10px] font-mono">{sc.scenario_id}</Badge>
                            )}
                            <span className="font-bold text-sm text-foreground">{sc.title || sc.scenario_type}</span>
                          </div>
                        </div>
                      </div>
                      <Badge tone={sc.severity === "CRITICAL" || sc.severity === "HIGH" ? "danger" : "warning"} className="text-[10px] font-mono">
                        {sc.severity}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs bg-background/60 p-2.5 rounded border border-border/60">
                      <div>
                        <strong className="text-muted-foreground">Triggering Observation: </strong>
                        <span className="text-foreground/90 font-mono text-[11px]">{sc.triggering_finding}</span>
                      </div>
                      <div>
                        <strong className="text-muted-foreground">Control Weakness: </strong>
                        <span className="text-amber-300 font-mono text-[11px]">{sc.control_weakness}</span>
                      </div>
                      <div className="md:col-span-2">
                        <strong className="text-muted-foreground">Potential Impact: </strong>
                        <span className="text-rose-300/90">{sc.potential_impact}</span>
                      </div>
                    </div>

                    {sc.scenario_chain && (
                      <div className="p-3 rounded-lg bg-background border border-border/80 space-y-1.5">
                        <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                          Contextual Security Chain (Asset &rarr; Impact):
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap text-[11px] font-mono">
                          <span className="px-2 py-0.5 rounded bg-primary/15 border border-primary/30 text-primary">{sc.scenario_chain.asset}</span>
                          <ArrowRight className="size-3 text-muted-foreground" />
                          <span className="px-2 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 text-blue-300">{sc.scenario_chain.observation}</span>
                          <ArrowRight className="size-3 text-muted-foreground" />
                          <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">{sc.scenario_chain.control_weakness}</span>
                          <ArrowRight className="size-3 text-muted-foreground" />
                          <span className="px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300">{sc.scenario_chain.risk_scenario}</span>
                          <ArrowRight className="size-3 text-muted-foreground" />
                          <span className="px-2 py-0.5 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 font-bold">{sc.scenario_chain.impact}</span>
                        </div>
                      </div>
                    )}

                    {sc.attack_path && sc.attack_path.length > 0 && (
                      <div className="p-3 rounded-lg bg-background/80 border border-border/60 space-y-1.5">
                        <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                          Attack Path:
                        </div>
                        <div className="space-y-1 text-xs font-mono text-muted-foreground">
                          {sc.attack_path.map((step, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                              <span className="text-primary font-bold">{idx + 1}.</span>
                              <span>{step}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {sc.remediation && (
                      <div className="pt-2 border-t border-border/40 text-xs text-emerald-400/90 flex items-start gap-1.5">
                        <CheckCircle2 className="size-3.5 shrink-0 mt-0.5 text-emerald-400" />
                        <span><strong className="text-foreground">Remediation: </strong>{sc.remediation}</span>
                      </div>
                    )}
                  </Card>
                ))
              )}
            </div>
          )}

          {/* ── Tab Content: Scan History ──────────────────────────────── */}
          {activeTab === "history" && (
            <div className="space-y-3">
              {scans.map((scan) => (
                <Card
                  key={scan.id}
                  className={`p-4 border transition-all ${
                    scan.id === activeScanId
                      ? "border-primary bg-primary/10"
                      : "border-border/80 bg-card/60 hover:bg-card"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {scan.source_type === "GITHUB" ? (
                          <Code2 className="size-4 text-primary" />
                        ) : (
                          <FileArchive className="size-4 text-primary" />
                        )}
                        <span className="font-bold text-sm text-foreground">{scan.project_name}</span>
                        <Badge
                          tone={
                            scan.status === "COMPLETED"
                              ? "success"
                              : scan.status === "FAILED"
                              ? "danger"
                              : "primary"
                          }
                          className="text-[10px]"
                        >
                          {scan.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground font-mono truncate max-w-md">
                        {scan.source_identifier}
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      {scan.posture_score !== null && scan.posture_score !== undefined && (
                        <div className="text-right">
                          <div className="text-lg font-bold font-mono text-primary">
                            {scan.posture_score} / 100
                          </div>
                          <div className="text-[10px] text-muted-foreground">{scan.posture_rating}</div>
                        </div>
                      )}

                      <Button
                        size="sm"
                        variant={scan.id === activeScanId ? "primary" : "outline"}
                        onClick={() => selectScan(scan, true)}
                        className="text-xs"
                      >
                        {scan.id === activeScanId ? "Active View" : "View Results"}
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Scan Launcher Modal ─────────────────────────────────────── */}
      <Modal
        open={scanModalOpen}
        onClose={() => setScanModalOpen(false)}
        title="Launch Repository Security Scan"
        size="lg"
      >
        <div className="space-y-5 p-1">
          {/* Tab Selector */}
          <div className="flex items-center gap-2 p-1 bg-muted/30 rounded-lg border border-border/80">
            <button
              type="button"
              onClick={() => setModalTab("github")}
              className={`flex-1 py-2 rounded-md text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                modalTab === "github"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Code2 className="size-4" />
              GitHub Repository
            </button>
            <button
              type="button"
              onClick={() => setModalTab("zip")}
              className={`flex-1 py-2 rounded-md text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                modalTab === "zip"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Upload className="size-4" />
              Upload Codebase ZIP
            </button>
          </div>

          {scanError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0" />
              <span>{scanError}</span>
            </div>
          )}

          {/* GitHub Form */}
          {modalTab === "github" && (
            <form onSubmit={handleLaunchGithubScan} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground">GitHub Repository HTTPS URL</label>
                <Input
                  type="url"
                  placeholder="https://github.com/owner/repository"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  required
                />
                <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-foreground text-[11px] space-y-0.5">
                  <div className="font-semibold flex items-center gap-1.5 text-primary">
                    <ShieldCheck className="size-3.5" />
                    Public &amp; Authorized Private Repositories
                  </div>
                  <p className="text-muted-foreground">
                    Scan a GitHub repository that the configured NOVA GitHub integration can read. Leave branch empty to use the repository's default branch.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-foreground">Branch / Tag (Optional)</label>
                  <Input
                    type="text"
                    placeholder="Default branch (e.g. main, master)"
                    value={githubBranch}
                    onChange={(e) => setGithubBranch(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-foreground">Project Name (Optional)</label>
                  <Input
                    type="text"
                    placeholder="e.g. AcmeBackend"
                    value={githubProjectName}
                    onChange={(e) => setGithubProjectName(e.target.value)}
                  />
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setScanModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submittingScan || !githubUrl.trim()} className="gap-2">
                  {submittingScan ? <RefreshCw className="size-4 animate-spin" /> : <Play className="size-4" />}
                  {submittingScan ? "Starting Scan..." : "Start Ingestion & Scan"}
                </Button>
              </div>
            </form>
          )}

          {/* ZIP Upload Form */}
          {modalTab === "zip" && (
            <form onSubmit={handleLaunchZipScan} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground">Codebase ZIP Archive</label>
                <div className="border-2 border-dashed border-border/80 rounded-xl p-6 text-center hover:border-primary/50 transition-colors bg-background/40">
                  <Upload className="size-8 text-muted-foreground mx-auto mb-2" />
                  <input
                    type="file"
                    accept=".zip"
                    onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-muted-foreground file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
                  />
                  {zipFile && (
                    <div className="text-xs font-mono text-emerald-400 mt-2">
                      Selected: {zipFile.name} ({(zipFile.size / 1024 / 1024).toFixed(2)} MB)
                    </div>
                  )}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  ZIP archives are strictly verified for Zip Slip, compression ratios, and directory traversal.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground">Project Name</label>
                <Input
                  type="text"
                  placeholder="e.g. LocalService"
                  value={zipProjectName}
                  onChange={(e) => setZipProjectName(e.target.value)}
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setScanModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submittingScan || !zipFile} className="gap-2">
                  {submittingScan ? <RefreshCw className="size-4 animate-spin" /> : <Upload className="size-4" />}
                  {submittingScan ? "Uploading..." : "Upload & Run Security Scan"}
                </Button>
              </div>
            </form>
          )}
        </div>
      </Modal>

      {/* ── Interactive Remediation Verifier Modal ──────────────────── */}
      <Modal
        open={remediationModalOpen}
        onClose={() => setRemediationModalOpen(false)}
        title="Interactive Remediation Verification Engine"
        size="xl"
      >
        <div className="space-y-4 p-1">
          {remediationTarget && (
            <div className="p-3 rounded-lg bg-muted/30 border border-border/80 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-foreground">{remediationTarget.risk_type}</div>
                <div className="text-[11px] text-muted-foreground font-mono">{remediationTarget.affected_scope}</div>
              </div>
              <Badge tone="danger" className="text-[10px]">{remediationTarget.severity}</Badge>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-foreground flex items-center justify-between">
              <span>Proposed Code Remediation Patch:</span>
              <span className="text-[11px] text-muted-foreground font-mono">AST Syntax & Control Check</span>
            </label>
            <textarea
              rows={8}
              value={customPatchCode}
              onChange={(e) => setCustomPatchCode(e.target.value)}
              className="w-full bg-background border border-border/80 rounded-lg p-3 font-mono text-xs text-foreground focus:outline-none focus:border-primary"
            />
          </div>

          {patchVerificationResult && (
            <div
              className={`p-4 rounded-xl border ${
                patchVerificationResult.fixed
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-400"
              }`}
            >
              <div className="flex items-center gap-2 font-bold text-sm mb-1">
                {patchVerificationResult.fixed ? (
                  <CheckCircle2 className="size-4" />
                ) : (
                  <XCircle className="size-4" />
                )}
                <span>Status: {patchVerificationResult.status}</span>
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {patchVerificationResult.details}
              </p>
            </div>
          )}

          <div className="pt-3 flex items-center justify-end gap-2">
            <Button variant="outline" onClick={() => setRemediationModalOpen(false)}>
              Close
            </Button>
            <Button
              onClick={handleRunVerification}
              disabled={verifyingPatch || !customPatchCode.trim()}
              className="gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
            >
              {verifyingPatch ? <RefreshCw className="size-4 animate-spin" /> : <Zap className="size-4" />}
              {verifyingPatch ? "Verifying..." : "Run AST Verification"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
