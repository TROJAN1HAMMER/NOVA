import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Boxes,
  Network,
  RotateCcw,
  Activity,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Play,
  Search,
  ZoomIn,
  ZoomOut,
  Crosshair,
  GitMerge,
  History,
  Sparkles,
  ArrowRight,
  Info,
  Globe,
  ChevronDown,
  Layers,
  Minimize2,
  Compass,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { apiClient } from "../lib/api/client";

interface ScanOption {
  scan_id: string;
  project_name: string;
  source_type: string;
  source_identifier: string;
  status: string;
  posture_score?: number | null;
  posture_rating?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  workspace_path?: string | null;
}

interface ComponentItem {
  component_id: string;
  name: string;
  component_type: string;
  file_path: string;
  line_number?: number;
  language: string;
  fan_in: number;
  fan_out: number;
  ca: number;
  ce: number;
  instability?: number | null;
  lcom4?: number | null;
  cohesion_metric_type: string;
  is_god_candidate: boolean;
  in_circular_dependency: boolean;
  circular_cycles: string[][];
  dependency_depth: number;
  attributes?: Record<string, any>;
}

interface DependencyItem {
  source_id: string;
  target_id: string;
  relation_type: string;
  file_path?: string;
  line_number?: number;
  evidence?: string;
  is_circular: boolean;
}

interface HotspotItem {
  component_id: string;
  component_name: string;
  component_type: string;
  file_path: string;
  hotspot_score: number;
  hotspot_level: "CRITICAL" | "HIGH" | "MEDIUM";
  reasons: string[];
  constituent_scores: Record<string, number>;
  raw_metrics: Record<string, any>;
  correlated_security: Record<string, any>;
}

interface TraceabilityItem {
  chain_id: string;
  component_id: string;
  component_name: string;
  file_path: string;
  line_number?: number;
  requirement_doc_name?: string;
  graph_entity_name?: string;
  control_name?: string;
  control_state?: string;
  finding_title?: string;
  finding_severity?: string;
  risk_scenario_title?: string;
  provenance: Record<string, any>;
}

interface BlastRadiusDependent {
  component_id: string;
  name: string;
  component_type: string;
  file_path: string;
  hop_depth: number;
  relationship: string;
  path: string;
  relation_type?: string;
}

interface BlastRadiusData {
  scan_id?: string;
  target_component_id: string;
  target_component_name: string;
  direct_dependents_count: number;
  direct_dependents: BlastRadiusDependent[];
  transitive_dependents_count: number;
  transitive_dependents: BlastRadiusDependent[];
  max_impact_depth: number;
  affected_endpoints: Array<{ component_id: string; name: string; file_path: string; hop_depth: number }>;
  affected_services: Array<{ component_id: string; name: string; type: string; file_path: string; hop_depth: number }>;
  affected_findings: Array<Record<string, any>>;
  affected_controls: Array<Record<string, any>>;
  affected_scenarios: Array<Record<string, any>>;
  affected_assets: Array<Record<string, any>>;
  risk_level: string;
}

interface RemediationResult {
  scan_id?: string;
  target_component_id: string;
  target_component_name: string;
  proposed_remediation: string;
  metric_label: string;
  estimated_posture_delta: number;
  affected_components_count: number;
  affected_components: BlastRadiusDependent[];
  strengthened_controls: Array<{ control_name: string; scope: string; state?: string }>;
  mitigated_risk_scenarios: Array<{ scenario_id: string; title: string; severity?: string }>;
  remaining_hotspot_status: string;
  disclaimer: string;
  direct_dependents_count?: number;
  max_impact_depth?: number;
  simulated_at?: string;
}

interface DriftData {
  baseline_available: boolean;
  message?: string;
  status: string;
  previous_snapshot_id?: string;
  current_snapshot_id?: string;
  added_dependencies: any[];
  removed_dependencies: any[];
  new_circular_cycles: any[];
  resolved_circular_cycles: any[];
  increased_coupling_components: any[];
  new_god_candidates: any[];
  boundary_violations: any[];
  summary: Record<string, any>;
}

type ArchitectureLayer = "API" | "SERVICES" | "DOMAIN" | "DATA" | "INFRASTRUCTURE" | "EXTERNAL";

function getComponentLayer(comp: ComponentItem): ArchitectureLayer {
  const type = (comp.component_type || "").toUpperCase();
  const path = (comp.file_path || "").toLowerCase();
  const name = (comp.name || "").toLowerCase();

  if (type === "EXTERNAL_DEPENDENCY") return "EXTERNAL";
  if (
    type === "DATABASE" ||
    path.includes("database") ||
    path.includes("db/") ||
    path.includes("models") ||
    name.includes("session") ||
    name.includes("connection")
  )
    return "DATA";
  if (
    type === "ENDPOINT" ||
    path.includes("api/") ||
    path.includes("routes") ||
    path.includes("endpoints") ||
    path.includes("controller")
  )
    return "API";
  if (type === "SERVICE" || name.endsWith("service") || path.includes("services/") || path.includes("service"))
    return "SERVICES";
  if (type === "CLASS" || path.includes("schemas") || path.includes("domain") || path.includes("entities"))
    return "DOMAIN";
  return "INFRASTRUCTURE";
}

const LAYER_CONFIG: Record<
  ArchitectureLayer,
  { label: string; subLabel: string; y: number; color: string; border: string; bg: string }
> = {
  API: {
    label: "API & Ingress",
    subLabel: "Inferred Architecture Layer: REST Endpoints & Route Handlers",
    y: 80,
    color: "#38bdf8",
    border: "rgba(56, 189, 248, 0.2)",
    bg: "rgba(56, 189, 248, 0.03)",
  },
  SERVICES: {
    label: "Application Services",
    subLabel: "Inferred Architecture Layer: Core Business Logic & Orchestrators",
    y: 220,
    color: "#818cf8",
    border: "rgba(129, 140, 248, 0.2)",
    bg: "rgba(129, 140, 248, 0.03)",
  },
  DOMAIN: {
    label: "Domain & Schemas",
    subLabel: "Inferred Architecture Layer: Domain Entities, Models & Validation",
    y: 360,
    color: "#c084fc",
    border: "rgba(192, 132, 252, 0.2)",
    bg: "rgba(192, 132, 252, 0.03)",
  },
  DATA: {
    label: "Data & Storage",
    subLabel: "Inferred Architecture Layer: Repositories, Databases & Storage Access",
    y: 500,
    color: "#34d399",
    border: "rgba(52, 211, 153, 0.2)",
    bg: "rgba(52, 211, 153, 0.03)",
  },
  INFRASTRUCTURE: {
    label: "Infrastructure & Utils",
    subLabel: "Inferred Architecture Layer: Cross-cutting Config, Security & Helpers",
    y: 640,
    color: "#94a3b8",
    border: "rgba(148, 163, 184, 0.2)",
    bg: "rgba(148, 163, 184, 0.03)",
  },
  EXTERNAL: {
    label: "External Packages",
    subLabel: "Third-party Dependencies",
    y: 180,
    color: "#cbd5e1",
    border: "rgba(203, 213, 225, 0.2)",
    bg: "rgba(203, 213, 225, 0.03)",
  },
};

const TYPE_COLORS: Record<string, { bg: string; stroke: string; text: string }> = {
  SERVICE: { bg: "#1e1b4b", stroke: "#6366f1", text: "#a5b4fc" },
  MODULE: { bg: "#0f172a", stroke: "#38bdf8", text: "#bae6fd" },
  PACKAGE: { bg: "#172554", stroke: "#60a5fa", text: "#bfdbfe" },
  CLASS: { bg: "#2e1065", stroke: "#a855f7", text: "#e9d5ff" },
  FUNCTION: { bg: "#022c22", stroke: "#10b981", text: "#a7f3d0" },
  ENDPOINT: { bg: "#082f49", stroke: "#0ea5e9", text: "#7dd3fc" },
  DATABASE: { bg: "#451a03", stroke: "#f59e0b", text: "#fde68a" },
  EXTERNAL_DEPENDENCY: { bg: "#18181b", stroke: "#71717a", text: "#d4d4d8" },
};

const GLOSSARY_TERMS: { term: string; definition: string; category: string }[] = [
  {
    term: "AST (Abstract Syntax Tree)",
    definition: "A hierarchical tree representation of source code structure, parsed statically without executing any code or scripts.",
    category: "Foundation",
  },
  {
    term: "Component",
    definition: "A discovered modular unit of software: Service, Module, Class, Function, API Endpoint, Database session, or External package.",
    category: "Foundation",
  },
  {
    term: "Dependency Edge",
    definition: "A typed directed relationship between two components (e.g. IMPORTS, CALLS, ACCESSES, IMPLEMENTS, DEPENDS_ON).",
    category: "Graph",
  },
  {
    term: "Afferent Coupling (Ca)",
    definition: "The number of other components that depend on this component (incoming connections / Fan-in).",
    category: "Coupling",
  },
  {
    term: "Efferent Coupling (Ce)",
    definition: "The number of other components this component depends on (outgoing connections / Fan-out).",
    category: "Coupling",
  },
  {
    term: "Instability (I)",
    definition: "The ratio Ce / (Ca + Ce). Measures vulnerability to ripple changes: 0 = maximally stable/resilient; 1 = maximally unstable/reactive.",
    category: "Coupling",
  },
  {
    term: "Cohesion (LCOM4)",
    definition: "Lack of Cohesion of Methods (LCOM4). Measures connected functional components inside a class: LCOM4 = 1 indicates single responsibility; > 1 indicates multiple disconnected responsibilities.",
    category: "Cohesion",
  },
  {
    term: "Circular Dependency (Tarjan SCC)",
    definition: "A closed cycle of dependencies (e.g., A → B → C → A) detected using Tarjan's Strongly Connected Components algorithm. Cycles prevent clean modular decomposition.",
    category: "Cycles",
  },
  {
    term: "Architecture Hotspot",
    definition: "A software component exhibiting concentrated architectural and security risk based on multi-factor scoring: coupling, cohesion, circular cycles, and security findings.",
    category: "Risk",
  },
  {
    term: "Blast Radius",
    definition: "The downstream impact propagation: the complete set of direct and transitive components reachable if this component is altered or compromised.",
    category: "Impact",
  },
  {
    term: "Unified Traceability",
    definition: "Multi-layer provenance tracking linking high-level Requirements to Code Components, Security Findings, Security Controls, and Risk Scenarios.",
    category: "Traceability",
  },
  {
    term: "Architecture Drift",
    definition: "The structural delta between two architecture snapshots of the same repository over time (new dependencies, resolved cycles, coupling shifts).",
    category: "Evolution",
  },
  {
    term: "Remediation Estimate",
    definition: "Topological estimation of ripple benefit and posture delta from decoupling a module. Clearly labeled as an estimate; does not alter repository posture.",
    category: "Planning",
  },
];

export default function ArchitectureIntelligencePage() {
  const [activeTab, setActiveTab] = useState<
    "overview" | "graph" | "metrics" | "hotspots" | "blast" | "traceability" | "drift" | "remediation"
  >("overview");

  // Scans state
  const [availableScans, setAvailableScans] = useState<ScanOption[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [scansLoading, setScansLoading] = useState<boolean>(true);

  // Core Data state
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [data, setData] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanSuccessMessage, setScanSuccessMessage] = useState<string | null>(null);

  // Modal states
  const [isScanModalOpen, setIsScanModalOpen] = useState<boolean>(false);
  const [isGlossaryModalOpen, setIsGlossaryModalOpen] = useState<boolean>(false);
  const [isHowToReadOpen, setIsHowToReadOpen] = useState<boolean>(false);
  const [scanTargetChoice, setScanTargetChoice] = useState<"selected" | "local">("selected");

  // Progressive Graph Exploration & View State
  const [graphMode, setGraphMode] = useState<"HIGH_LEVEL" | "HOTSPOTS_ONLY" | "SECURITY_CRITICAL">("HIGH_LEVEL");
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Coupling & Cohesion Sorting
  const [metricsSortBy, setMetricsSortBy] = useState<"COUPLING" | "LCOM4" | "INSTABILITY_HIGH" | "INSTABILITY_LOW" | "NAME">("COUPLING");

  // Blast Radius State
  const [selectedBlastComponent, setSelectedBlastComponent] = useState<string>("");
  const [blastData, setBlastData] = useState<BlastRadiusData | null>(null);
  const [blastLoading, setBlastLoading] = useState<boolean>(false);
  const [blastError, setBlastError] = useState<string | null>(null);
  const [blastSearchFilter, setBlastSearchFilter] = useState<string>("");

  // Drift State
  const [driftData, setDriftData] = useState<DriftData | null>(null);
  const [driftLoading, setDriftLoading] = useState<boolean>(false);

  // Remediation Simulator State
  const [simComponent, setSimComponent] = useState<string>("");
  const [simText, setSimText] = useState<string>("Decouple module and enforce RBAC authorization boundary");
  const [simResult, setSimResult] = useState<RemediationResult | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simError, setSimError] = useState<string | null>(null);

  // Graph Canvas Viewport
  const [zoom, setZoom] = useState<number>(0.95);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 30, y: 10 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [customPositions, setCustomPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tabStripRef = useRef<HTMLDivElement>(null);

  // 1. Fetch available completed scans
  const fetchScans = async () => {
    setScansLoading(true);
    try {
      const res = await apiClient.get("/architecture/scans");
      if (res.data && res.data.length > 0) {
        setAvailableScans(res.data);
        if (!selectedScanId) {
          setSelectedScanId(res.data[0].scan_id);
        }
      }
    } catch {
      // Fallback
    } finally {
      setScansLoading(false);
    }
  };

  // 2. Fetch architecture strictly for selected scan
  const fetchArchitecture = async (scanIdToFetch?: string, isForceRefresh = false) => {
    const targetScanId = scanIdToFetch || selectedScanId;
    if (!targetScanId) {
      setLoading(false);
      return;
    }
    if (isForceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const url = isForceRefresh
        ? `/architecture/${targetScanId}?force_refresh=true`
        : `/architecture/${targetScanId}`;
      const res = await apiClient.get(url);
      setData(res.data);
      setExpandedNodeIds(new Set());
      setSelectedNodeId(null);
      setBlastData(null);
      setBlastError(null);
      setSimResult(null);
      setSimError(null);
      if (res.data.components?.length > 0) {
        setSelectedBlastComponent(res.data.components[0].component_id);
        setSimComponent(res.data.components[0].component_id);
      } else {
        setSelectedBlastComponent("");
        setSimComponent("");
      }
      if (isForceRefresh) {
        setScanSuccessMessage("Architecture snapshot refreshed successfully.");
        setTimeout(() => setScanSuccessMessage(null), 3500);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load Architecture Intelligence data for selected scan.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // 3. Execute AST Scan
  const handleRunAstScan = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const isSelectedChoice = scanTargetChoice === "selected" && activeScan;
      const payload: any = {
        force_refresh: true,
      };

      if (isSelectedChoice && activeScan) {
        payload.scan_id = activeScan.scan_id;
        payload.project_name = activeScan.project_name;
        if (activeScan.workspace_path) {
          payload.target_path = activeScan.workspace_path;
        }
      } else {
        payload.target_path = ".";
        payload.project_name = "NOVA Core";
      }

      const res = await apiClient.post("/architecture/analyze", payload);
      setData(res.data);
      setIsScanModalOpen(false);
      setScanSuccessMessage(
        `Static AST scan completed successfully for ${payload.project_name || "repository"}.`
      );
      setTimeout(() => setScanSuccessMessage(null), 4000);

      // Refresh scan list and select new scan if created
      await fetchScans();
      if (res.data.scan_id && res.data.scan_id !== selectedScanId) {
        setSelectedScanId(res.data.scan_id);
      }
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          "AST scan is unavailable for this source. Ensure the workspace is accessible or run a scan in Security Intelligence."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const fetchBlastRadius = async (compId: string) => {
    if (!compId || !selectedScanId) return;
    setBlastLoading(true);
    setBlastError(null);
    try {
      const res = await apiClient.get(`/architecture/${selectedScanId}/impact/${encodeURIComponent(compId)}`);
      setBlastData(res.data);
    } catch (err: any) {
      setBlastError(
        err?.response?.data?.detail ||
        "The dependency relationships for this component could not be loaded."
      );
      setBlastData(null);
    } finally {
      setBlastLoading(false);
    }
  };

  const fetchDrift = async () => {
    if (!selectedScanId) return;
    setDriftLoading(true);
    try {
      const res = await apiClient.get(`/architecture/${selectedScanId}/drift`);
      setDriftData(res.data);
    } catch {
      // Graceful fallback
    } finally {
      setDriftLoading(false);
    }
  };

  const handleRunRemediationSim = async () => {
    if (!simComponent || !selectedScanId) return;
    setSimLoading(true);
    setSimError(null);
    try {
      const res = await apiClient.post(`/architecture/${selectedScanId}/remediation-impact`, {
        component_id: simComponent,
        proposed_remediation: simText,
      });
      setSimResult({
        ...res.data,
        simulated_at: new Date().toLocaleTimeString(),
      });
    } catch (err: any) {
      setSimError(
        err?.response?.data?.detail ||
        "Unable to calculate remediation impact for the selected component."
      );
      setSimResult(null);
    } finally {
      setSimLoading(false);
    }
  };

  useEffect(() => {
    fetchScans();
  }, []);

  useEffect(() => {
    if (selectedScanId) {
      fetchArchitecture(selectedScanId);
    }
  }, [selectedScanId]);

  useEffect(() => {
    if (activeTab === "blast" && selectedBlastComponent) {
      fetchBlastRadius(selectedBlastComponent);
    } else if (activeTab === "drift") {
      fetchDrift();
    } else if (activeTab === "remediation" && simComponent && !simResult) {
      handleRunRemediationSim();
    }
  }, [activeTab, selectedBlastComponent, selectedScanId]);

  // Derived lists for active scan
  const components: ComponentItem[] = useMemo(() => data?.components || [], [data]);
  const dependencies: DependencyItem[] = useMemo(() => data?.dependencies || [], [data]);
  const hotspots: HotspotItem[] = useMemo(() => data?.hotspots || [], [data]);
  const traceability: TraceabilityItem[] = useMemo(() => data?.traceability || [], [data]);
  const summary = data?.summary || {};

  const activeScan = useMemo(() => {
    return availableScans.find((s) => s.scan_id === selectedScanId);
  }, [availableScans, selectedScanId]);

  const circularNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const c of components) {
      if (c.in_circular_dependency) ids.add(c.component_id);
    }
    return ids;
  }, [components]);

  const hotspotMap = useMemo(() => {
    const map = new Map<string, HotspotItem>();
    for (const h of hotspots) {
      map.set(h.component_id, h);
    }
    return map;
  }, [hotspots]);

  // Security critical components (connected to security findings, failed controls, or critical assets)
  const securityCriticalNodeIds = useMemo(() => {
    const ids = new Set<string>();
    for (const h of hotspots) {
      if (
        (h.correlated_security && h.correlated_security.findings_count > 0) ||
        h.reasons.some((r) => r.toLowerCase().includes("security") || r.toLowerCase().includes("control"))
      ) {
        ids.add(h.component_id);
      }
    }
    for (const t of traceability) {
      if (t.finding_title || t.control_name || t.risk_scenario_title) {
        ids.add(t.component_id);
      }
    }
    return ids;
  }, [hotspots, traceability]);

  // Initial High-Level Architecture Anchor Set (15–30 top-level visible nodes)
  const initialAnchorIds = useMemo(() => {
    const ids = new Set<string>();
    if (components.length <= 30) {
      components.forEach((c) => ids.add(c.component_id));
      return ids;
    }

    // 1. All Services (up to 8)
    const services = components.filter(
      (c) => c.component_type === "SERVICE" || c.name.toLowerCase().endsWith("service")
    );
    services.slice(0, 8).forEach((c) => ids.add(c.component_id));

    // 2. All Databases & Connections (up to 6)
    const dbs = components.filter(
      (c) =>
        c.component_type === "DATABASE" ||
        c.file_path.toLowerCase().includes("database") ||
        c.name.toLowerCase().includes("session") ||
        c.name.toLowerCase().includes("connection")
    );
    dbs.slice(0, 6).forEach((c) => ids.add(c.component_id));

    // 3. Key Endpoints & APIs (up to 6)
    const endpoints = components.filter(
      (c) =>
        c.component_type === "ENDPOINT" ||
        c.file_path.toLowerCase().includes("api/") ||
        c.file_path.toLowerCase().includes("routes")
    );
    endpoints.slice(0, 6).forEach((c) => ids.add(c.component_id));

    // 4. Circular dependency nodes (all)
    components.filter((c) => c.in_circular_dependency).forEach((c) => ids.add(c.component_id));

    // 5. Top Hotspots (up to 5)
    hotspots.slice(0, 5).forEach((h) => ids.add(h.component_id));

    // 6. If still under 18 nodes, fill with highest-coupled modules
    if (ids.size < 18) {
      const sortedByCoupling = [...components].sort((a, b) => b.ca + b.ce - (a.ca + a.ce));
      for (const c of sortedByCoupling) {
        if (ids.size >= 24) break;
        ids.add(c.component_id);
      }
    }

    return ids;
  }, [components, hotspots]);

  // Progressive Expansion Handlers
  const handleExpand1Hop = (nodeId: string) => {
    const neighbors = new Set<string>();
    for (const dep of dependencies) {
      if (dep.source_id === nodeId) neighbors.add(dep.target_id);
      if (dep.target_id === nodeId) neighbors.add(dep.source_id);
    }
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      next.add(nodeId);
      neighbors.forEach((id) => next.add(id));
      return next;
    });
  };

  const handleExpand2Hop = (nodeId: string) => {
    const hop1 = new Set<string>();
    for (const dep of dependencies) {
      if (dep.source_id === nodeId) hop1.add(dep.target_id);
      if (dep.target_id === nodeId) hop1.add(dep.source_id);
    }
    const hop2 = new Set<string>(hop1);
    for (const dep of dependencies) {
      if (hop1.has(dep.source_id)) hop2.add(dep.target_id);
      if (hop1.has(dep.target_id)) hop2.add(dep.source_id);
    }
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      next.add(nodeId);
      hop2.forEach((id) => next.add(id));
      return next;
    });
  };

  const handleCollapseExpansion = () => {
    setExpandedNodeIds(new Set());
    setSelectedNodeId(null);
  };

  // Search & Focus Handler
  const handleSelectSearchedComponent = (comp: ComponentItem) => {
    setExpandedNodeIds((prev) => {
      const next = new Set(prev);
      next.add(comp.component_id);
      for (const dep of dependencies) {
        if (dep.source_id === comp.component_id) next.add(dep.target_id);
        if (dep.target_id === comp.component_id) next.add(dep.source_id);
      }
      return next;
    });
    setSelectedNodeId(comp.component_id);
    setSearchQuery("");

    const pos = nodePosMap.get(comp.component_id);
    if (pos) {
      setPan({ x: 500 - pos.x * zoom, y: 350 - pos.y * zoom });
    }
  };

  // Visible Nodes Calculation
  const visibleNodes = useMemo(() => {
    if (components.length === 0) return [];

    let baseSet: Set<string>;
    if (graphMode === "HOTSPOTS_ONLY") {
      baseSet = new Set(hotspots.map((h) => h.component_id));
      if (baseSet.size === 0) baseSet = initialAnchorIds;
    } else if (graphMode === "SECURITY_CRITICAL") {
      baseSet = securityCriticalNodeIds.size > 0 ? securityCriticalNodeIds : initialAnchorIds;
    } else {
      baseSet = new Set([...initialAnchorIds, ...expandedNodeIds]);
    }

    if (searchQuery.trim().length > 1) {
      const q = searchQuery.toLowerCase();
      components.forEach((c) => {
        if (c.name.toLowerCase().includes(q) || c.file_path.toLowerCase().includes(q)) {
          baseSet.add(c.component_id);
        }
      });
    }

    let candidates = components.filter((c) => baseSet.has(c.component_id));

    if (selectedType !== "ALL") {
      candidates = candidates.filter((c) => c.component_type === selectedType);
    }

    return candidates;
  }, [
    components,
    initialAnchorIds,
    expandedNodeIds,
    graphMode,
    selectedType,
    searchQuery,
    hotspots,
    securityCriticalNodeIds,
  ]);

  // Hierarchical Architecture Layer Layout
  const layoutedNodes = useMemo(() => {
    const layers: Record<ArchitectureLayer, ComponentItem[]> = {
      API: [],
      SERVICES: [],
      DOMAIN: [],
      DATA: [],
      INFRASTRUCTURE: [],
      EXTERNAL: [],
    };

    visibleNodes.forEach((n) => {
      const layer = getComponentLayer(n);
      layers[layer].push(n);
    });

    const result: (ComponentItem & { x: number; y: number; layer: ArchitectureLayer })[] = [];

    (Object.keys(layers) as ArchitectureLayer[]).forEach((layer) => {
      const nodes = layers[layer];
      if (layer === "EXTERNAL") {
        nodes.forEach((node, idx) => {
          if (customPositions[node.component_id]) {
            result.push({
              ...node,
              x: customPositions[node.component_id].x,
              y: customPositions[node.component_id].y,
              layer,
            });
          } else {
            const x = 930;
            const y = 100 + idx * 60;
            result.push({ ...node, x, y, layer });
          }
        });
      } else {
        const count = nodes.length;
        const startX = 140;
        const endX = 820;
        const step = count > 1 ? (endX - startX) / (count - 1) : 0;
        const midX = (startX + endX) / 2;

        nodes.forEach((node, idx) => {
          if (customPositions[node.component_id]) {
            result.push({
              ...node,
              x: customPositions[node.component_id].x,
              y: customPositions[node.component_id].y,
              layer,
            });
          } else {
            const x = count === 1 ? midX : startX + idx * step;
            const y = LAYER_CONFIG[layer].y;
            result.push({ ...node, x, y, layer });
          }
        });
      }
    });

    return result;
  }, [visibleNodes, customPositions]);

  const nodePosMap = useMemo(() => {
    const map = new Map<string, { x: number; y: number; node: ComponentItem & { layer: ArchitectureLayer } }>();
    for (const n of layoutedNodes) {
      map.set(n.component_id, { x: n.x, y: n.y, node: n });
    }
    return map;
  }, [layoutedNodes]);

  const visibleEdges = useMemo(() => {
    return dependencies.filter((dep) => nodePosMap.has(dep.source_id) && nodePosMap.has(dep.target_id));
  }, [dependencies, nodePosMap]);

  const searchResults = useMemo(() => {
    if (!searchQuery || searchQuery.trim().length < 2) return [];
    const q = searchQuery.toLowerCase();
    return components
      .filter((c) => c.name.toLowerCase().includes(q) || c.file_path.toLowerCase().includes(q))
      .slice(0, 8);
  }, [components, searchQuery]);

  // Panning & Dragging Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).tagName !== "svg" && (e.target as HTMLElement).id !== "canvas-bg") return;
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    } else if (draggedNodeId) {
      const rect = containerRef.current?.getBoundingClientRect();
      if (rect) {
        const x = (e.clientX - rect.left - pan.x) / zoom;
        const y = (e.clientY - rect.top - pan.y) / zoom;
        setCustomPositions((prev) => ({ ...prev, [draggedNodeId]: { x, y } }));
      }
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggedNodeId(null);
  };

  // Coupling & Cohesion Highlights & Sorted List
  const couplingHighlights = useMemo(() => {
    if (components.length === 0) return null;
    const sortedByCoupling = [...components].sort((a, b) => b.ca + b.ce - (a.ca + a.ce));
    const sortedByLcom = [...components].sort((a, b) => (b.lcom4 ?? 0) - (a.lcom4 ?? 0));
    const mostBalanced = [...components]
      .filter((c) => c.ca > 0 && c.ce > 0 && c.instability !== null)
      .sort((a, b) => Math.abs((a.instability ?? 0.5) - 0.5) - Math.abs((b.instability ?? 0.5) - 0.5));

    return {
      highestCoupling: sortedByCoupling[0],
      lowestCohesion: sortedByLcom[0],
      mostBalanced: mostBalanced[0] || sortedByCoupling[sortedByCoupling.length - 1],
    };
  }, [components]);

  const sortedAndFilteredComponents = useMemo(() => {
    let result = components.filter((c) => {
      const matchesSearch =
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.file_path.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = selectedType === "ALL" || c.component_type === selectedType;
      return matchesSearch && matchesType;
    });

    if (metricsSortBy === "COUPLING") {
      result.sort((a, b) => b.ca + b.ce - (a.ca + a.ce));
    } else if (metricsSortBy === "LCOM4") {
      result.sort((a, b) => (b.lcom4 ?? 0) - (a.lcom4 ?? 0));
    } else if (metricsSortBy === "INSTABILITY_HIGH") {
      result.sort((a, b) => (b.instability ?? 0) - (a.instability ?? 0));
    } else if (metricsSortBy === "INSTABILITY_LOW") {
      result.sort((a, b) => (a.instability ?? 1) - (b.instability ?? 1));
    } else if (metricsSortBy === "NAME") {
      result.sort((a, b) => a.name.localeCompare(b.name));
    }

    return result;
  }, [components, searchQuery, selectedType, metricsSortBy]);

  // Tab Strip Scroll
  const scrollTabs = (offset: number) => {
    if (tabStripRef.current) {
      tabStripRef.current.scrollBy({ left: offset, behavior: "smooth" });
    }
  };

  return (
    <div className="space-y-6 pb-16 max-w-full overflow-x-hidden">
      {/* Page Header */}
      <PageHeader
        title="Architecture & Connectivity Intelligence"
        description="Understand how your software components depend on each other, where architecture is becoming difficult to maintain, and what could be affected by a change."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsGlossaryModalOpen(true)}
              className="text-xs"
              title="Architecture Terminology Glossary"
            >
              <HelpCircle className="size-4 mr-1.5 text-primary" />
              Glossary
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fetchArchitecture(selectedScanId, true)}
              disabled={loading || refreshing || analyzing || !selectedScanId}
              className="text-xs"
            >
              <RefreshCw className={`size-4 mr-1.5 ${refreshing ? "animate-spin text-primary" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh Scan"}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsScanModalOpen(true)}
              disabled={analyzing}
              className="text-xs font-semibold shadow-sm"
            >
              <Play className={`size-4 mr-1.5 ${analyzing ? "animate-spin" : ""}`} />
              {analyzing ? "Analyzing AST..." : "Run New AST Scan"}
            </Button>
          </div>
        }
      />

      {/* Success Notification Banner */}
      {scanSuccessMessage && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3.5 text-xs text-emerald-300 flex items-center justify-between shadow-sm animate-in fade-in duration-300">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
            <span className="font-medium">{scanSuccessMessage}</span>
          </div>
          <button
            onClick={() => setScanSuccessMessage(null)}
            className="text-emerald-400 hover:text-emerald-200 text-xs px-2 py-0.5 rounded"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive flex items-center justify-between gap-3 shadow-sm">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="size-5 shrink-0 text-destructive" />
            <span className="font-medium">{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchArchitecture(selectedScanId)}
            className="text-xs shrink-0"
          >
            Retry
          </Button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* REPOSITORY / SCAN SCOPE CARD                                              */}
      {/* ========================================================================= */}
      <Card className="border-border/70 bg-gradient-to-r from-card/90 via-card/75 to-card/90 shadow-sm">
        <CardContent className="p-4 sm:p-5">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                  <Compass className="size-3.5" />
                  Repository / Scan Scope
                </span>
                <span className="text-xs text-muted-foreground">• All architecture metrics strictly scoped to this scan</span>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="relative min-w-[280px] sm:min-w-[360px] flex-1 max-w-lg">
                  <select
                    id="scan-selector-dropdown"
                    value={selectedScanId}
                    onChange={(e) => setSelectedScanId(e.target.value)}
                    disabled={scansLoading || availableScans.length === 0}
                    className="w-full h-10 pl-3.5 pr-10 rounded-xl border border-primary/40 bg-background/90 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 shadow-inner appearance-none cursor-pointer"
                  >
                    {availableScans.map((s) => (
                      <option key={s.scan_id} value={s.scan_id} className="bg-card text-foreground py-1">
                        {s.project_name} — Scan {s.scan_id.slice(0, 8)}... (
                        {s.completed_at ? new Date(s.completed_at).toLocaleDateString() : "Active"})
                      </option>
                    ))}
                    {availableScans.length === 0 && (
                      <option value="">No completed scans found (run analysis above)</option>
                    )}
                  </select>
                  <ChevronDown className="size-4 text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>

                {activeScan && (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge tone="neutral" className="gap-1 px-2.5 py-1 font-medium">
                      <Globe className="size-3 text-muted-foreground" />
                      {activeScan.source_type}
                    </Badge>
                    {activeScan.posture_score !== null && activeScan.posture_score !== undefined && (
                      <Badge
                        tone={
                          activeScan.posture_score >= 80
                            ? "success"
                            : activeScan.posture_score >= 50
                            ? "warning"
                            : "danger"
                        }
                        className="px-2.5 py-1 font-semibold"
                      >
                        Security Posture: {activeScan.posture_score.toFixed(1)}/100
                      </Badge>
                    )}
                    <span className="text-muted-foreground text-[11px] font-mono">
                      Completed:{" "}
                      {activeScan.completed_at
                        ? new Date(activeScan.completed_at).toLocaleString([], {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Ready"}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions in Scan Context */}
            <div className="flex items-center gap-2 pt-2 lg:pt-0 border-t lg:border-t-0 border-border/40">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsHowToReadOpen((prev) => !prev)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                <Info className="size-3.5 mr-1.5 text-primary" />
                {isHowToReadOpen ? "Hide Guide" : "How to read this"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* "How to read this" Collapsible Guide */}
      {isHowToReadOpen && (
        <Card className="border-primary/30 bg-primary/5 p-4 animate-in fade-in duration-200">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 text-xs">
              <div className="font-bold text-foreground flex items-center gap-2 text-sm">
                <Sparkles className="size-4 text-primary" />
                How to Read Architecture & Connectivity Intelligence
              </div>
              <p className="text-muted-foreground leading-relaxed">
                This system parses your repository statically via Abstract Syntax Trees (AST) without executing code.
                It maps relationships into <strong className="text-foreground">Inferred Architecture Layers</strong> (API, Services, Domain, Data, Infrastructure, External),
                computes coupling & cohesion metrics, detects circular dependency cycles, and traces components through security findings and risks.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                <div className="p-2.5 rounded-lg bg-background/70 border border-border/50">
                  <div className="font-semibold text-foreground mb-1 flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-primary" />
                    1. High-Level Map
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Initial graph renders 15–30 major architectural anchors rather than a hairball of thousands of internal functions.
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-background/70 border border-border/50">
                  <div className="font-semibold text-foreground mb-1 flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-indigo-400" />
                    2. Progressive Disclosure
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Click any component to inspect metrics (Ca, Ce, Instability, Cohesion) and expand its 1-hop or 2-hop neighborhood.
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-background/70 border border-border/50">
                  <div className="font-semibold text-foreground mb-1 flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-rose-400" />
                    3. Impact & Hotspots
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Analyze blast radius reachability and view hotspots where high coupling and low cohesion create fragility.
                  </div>
                </div>
              </div>
            </div>
            <button
              onClick={() => setIsHowToReadOpen(false)}
              className="text-muted-foreground hover:text-foreground text-xs"
            >
              ✕
            </button>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* ARCHITECTURE STORY / EXECUTIVE SUMMARY                                    */}
      {/* ========================================================================= */}
      <Card className="border-border/60 bg-card/60 shadow-sm">
        <CardContent className="p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary mt-0.5 shrink-0">
              <Activity className="size-4" />
            </div>
            <div className="space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                Architecture Summary
              </div>
              <div className="text-sm font-medium text-foreground leading-relaxed">
                This scan of{" "}
                <span className="font-semibold text-primary">{activeScan?.project_name || "the repository"}</span> contains{" "}
                <span className="font-semibold text-foreground">{summary.total_components ?? components.length}</span> components and{" "}
                <span className="font-semibold text-foreground">{summary.total_dependencies ?? dependencies.length}</span> direct relationships across 5 inferred architectural tiers.{" "}
                {(summary.total_circular_cycles ?? 0) === 0 ? (
                  <span className="text-emerald-400 font-medium">No circular dependencies were detected (strictly acyclic DAG).</span>
                ) : (
                  <span className="text-rose-400 font-medium">
                    {summary.total_circular_cycles} circular dependency cycle(s) were detected across components.
                  </span>
                )}{" "}
                {hotspots.length === 0 ? (
                  <span className="text-muted-foreground">No structural architecture hotspots were identified.</span>
                ) : (
                  <span className="text-amber-400 font-medium">
                    {hotspots.length} architectural hotspot(s) require attention (top priority:{" "}
                    <span className="underline decoration-amber-400/50">{hotspots[0]?.component_name}</span>).
                  </span>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ========================================================================= */}
      {/* KEY METRIC CARDS WITH INTERPRETATION & EXPLANATION                        */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Components */}
        <Card className="border-border/60 bg-card/60 hover:border-primary/40 transition-colors">
          <CardContent className="p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground font-semibold uppercase tracking-wider">
              <span>Components</span>
              <span
                className="cursor-help"
                title="Total software components identified in this scan via static AST parsing across Services, Modules, Classes, Functions, Databases, and Endpoints."
              >
                <HelpCircle className="size-3.5 text-muted-foreground/70" />
              </span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-foreground">
              {summary.total_components ?? components.length}
            </div>
            <div className="text-xs text-muted-foreground leading-snug">
              Software components identified in this scan.
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Dependencies */}
        <Card className="border-border/60 bg-card/60 hover:border-primary/40 transition-colors">
          <CardContent className="p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground font-semibold uppercase tracking-wider">
              <span>Dependencies</span>
              <span
                className="cursor-help"
                title="Direct static relationships between components (IMPORTS, CALLS, DEPENDS_ON, ACCESSES, IMPLEMENTS)."
              >
                <HelpCircle className="size-3.5 text-muted-foreground/70" />
              </span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-cyan-400">
              {summary.total_dependencies ?? dependencies.length}
            </div>
            <div className="text-xs text-muted-foreground leading-snug">
              Direct relationships between components.
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Cycles */}
        <Card className="border-border/60 bg-card/60 hover:border-primary/40 transition-colors">
          <CardContent className="p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground font-semibold uppercase tracking-wider">
              <span>Cycles</span>
              <span
                className="cursor-help"
                title="Tarjan Strongly Connected Component (SCC) cycles where components depend on each other cyclically, causing tight coupling."
              >
                <HelpCircle className="size-3.5 text-muted-foreground/70" />
              </span>
            </div>
            <div
              className={`text-2xl sm:text-3xl font-bold ${
                (summary.total_circular_cycles ?? 0) > 0 ? "text-rose-400" : "text-emerald-400"
              }`}
            >
              {summary.total_circular_cycles ?? 0}
            </div>
            <div className="text-xs text-muted-foreground leading-snug">
              {(summary.total_circular_cycles ?? 0) === 0
                ? "Healthy — no circular dependencies detected."
                : "Attention — circular dependency paths detected."}
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Hotspots */}
        <Card className="border-border/60 bg-card/60 hover:border-primary/40 transition-colors">
          <CardContent className="p-4 sm:p-5 space-y-1.5">
            <div className="flex items-center justify-between text-xs text-muted-foreground font-semibold uppercase tracking-wider">
              <span>Hotspots</span>
              <span
                className="cursor-help"
                title="Components exhibiting multi-factor architectural stress: high afferent/efferent coupling, low cohesion (LCOM4), or linked security findings."
              >
                <HelpCircle className="size-3.5 text-muted-foreground/70" />
              </span>
            </div>
            <div
              className={`text-2xl sm:text-3xl font-bold ${
                hotspots.length > 0 ? "text-amber-400" : "text-muted-foreground"
              }`}
            >
              {hotspots.length}
            </div>
            <div className="text-xs text-muted-foreground leading-snug">
              {hotspots.length === 0
                ? "Optimal — no structural hotspots."
                : "Attention needed — high coupling / low cohesion."}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* HORIZONTAL TAB NAVIGATION (WITH HIDDEN SCROLLBAR & GROUPED HIERARCHY)     */}
      {/* ========================================================================= */}
      <div className="relative border-b border-border/80">
        <div className="flex items-center justify-between">
          <button
            onClick={() => scrollTabs(-180)}
            className="p-1.5 text-muted-foreground hover:text-foreground hidden sm:block"
            title="Scroll tabs left"
          >
            <ChevronLeft className="size-4" />
          </button>

          <div
            ref={tabStripRef}
            className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden py-1 px-1 flex-1"
          >
            {[
              { key: "overview", label: "Health Overview", icon: Activity, group: "UNDERSTAND" },
              { key: "graph", label: "Architecture Graph", icon: Network, group: "UNDERSTAND" },
              { key: "metrics", label: "Coupling & Cohesion", icon: Boxes, group: "UNDERSTAND" },
              { key: "hotspots", label: "Hotspots", icon: ShieldAlert, badge: hotspots.length, group: "INVESTIGATE" },
              { key: "blast", label: "Blast Radius / Impact", icon: Crosshair, group: "INVESTIGATE" },
              { key: "traceability", label: "Unified Traceability", icon: GitMerge, badge: traceability.length, group: "INVESTIGATE" },
              { key: "drift", label: "Architecture Drift", icon: History, group: "MONITOR" },
              { key: "remediation", label: "Remediation Simulator", icon: Sparkles, group: "PLAN" },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as any)}
                  className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                    isActive
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                  }`}
                >
                  <Icon className="size-3.5" />
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                        isActive ? "bg-primary-foreground text-primary" : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => scrollTabs(180)}
            className="p-1.5 text-muted-foreground hover:text-foreground hidden sm:block"
            title="Scroll tabs right"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>

      {/* Loading Overlay State for Core Data */}
      {loading && (
        <Card className="border-border/60 bg-card/60 p-12 text-center">
          <div className="flex flex-col items-center justify-center gap-3">
            <Spinner className="size-8 text-primary" />
            <div className="text-sm font-semibold text-foreground">Loading architecture for selected scan...</div>
            <div className="text-xs text-muted-foreground">
              Retrieving static components, dependency edges, coupling metrics, and security links.
            </div>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: HEALTH OVERVIEW                                                    */}
      {/* ========================================================================= */}
      {!loading && activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Component Distribution */}
            <Card className="border-border/60 bg-card/70">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <Boxes className="size-4 text-primary" />
                    Component Distribution by Layer & Type
                  </h3>
                  <Badge tone="neutral" className="text-xs">
                    {components.length} Total Components
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(
                  components.reduce<Record<string, number>>((acc, c) => {
                    acc[c.component_type] = (acc[c.component_type] || 0) + 1;
                    return acc;
                  }, {})
                ).map(([type, count]) => {
                  const pct = Math.round((count / Math.max(1, components.length)) * 100);
                  const color = TYPE_COLORS[type]?.stroke || "#94a3b8";
                  return (
                    <div key={type} className="space-y-1">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="flex items-center gap-2 text-foreground">
                          <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} />
                          {type}
                        </span>
                        <span className="text-muted-foreground">
                          {count} ({pct}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, backgroundColor: color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            {/* Circular Cycles Card */}
            <Card className="border-border/60 bg-card/70">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <RotateCcw className="size-4 text-rose-400" />
                    Circular Dependency Cycles (Tarjan SCC)
                  </h3>
                  <Badge tone={(summary.total_circular_cycles ?? 0) > 0 ? "danger" : "success"} className="text-xs">
                    {(summary.total_circular_cycles ?? 0) === 0
                      ? "Zero Cycles"
                      : `${summary.total_circular_cycles} Cycle(s)`}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                {data?.cycles_detected && data.cycles_detected.length > 0 ? (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">
                      Circular dependencies increase architectural coupling, complicate testing, and impede modular refactoring.
                    </p>
                    {data.cycles_detected.map((cycle: string[], idx: number) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-3 text-xs space-y-2"
                      >
                        <div className="font-semibold text-rose-300 flex items-center gap-1.5">
                          <span>Cycle #{idx + 1}</span>
                          <span className="text-[10px] text-rose-400">({cycle.length} components in loop)</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground font-mono text-[11px]">
                          {cycle.map((nodeId, i) => (
                            <React.Fragment key={nodeId}>
                              <span className="px-2 py-0.5 rounded bg-background/80 border border-border text-foreground">
                                {nodeId.split(":").pop()?.split("-").pop() || nodeId}
                              </span>
                              {i < cycle.length - 1 && <ArrowRight className="size-3 text-rose-400" />}
                            </React.Fragment>
                          ))}
                          <ArrowRight className="size-3 text-rose-400" />
                          <span className="text-rose-400 font-bold">↺</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
                    <CheckCircle2 className="size-8 text-success" />
                    <span className="font-medium text-foreground">No circular dependencies detected.</span>
                    <span className="text-[11px] text-muted-foreground">Component dependency DAG is strictly acyclic.</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Top Hotspots Quick Preview */}
          <Card className="border-border/60 bg-card/70">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <ShieldAlert className="size-4 text-amber-400" />
                    High Priority Architectural Hotspots
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Components requiring architectural refactoring based on coupling, cohesion, and security risk.
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => setActiveTab("hotspots")} className="text-xs">
                  View All Hotspots ({hotspots.length})
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {hotspots.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {hotspots.slice(0, 3).map((h) => (
                    <div
                      key={h.component_id}
                      className="rounded-xl border border-border/80 bg-background/50 p-3.5 space-y-2 hover:border-primary/50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-sm text-foreground truncate max-w-[180px]">
                          {h.component_name}
                        </span>
                        <Badge
                          tone={
                            h.hotspot_level === "CRITICAL"
                              ? "danger"
                              : h.hotspot_level === "HIGH"
                              ? "warning"
                              : "primary"
                          }
                          className="text-xs"
                        >
                          {h.hotspot_level} ({h.hotspot_score})
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground truncate font-mono">{h.file_path}</div>
                      <div className="text-xs space-y-1">
                        {h.reasons.slice(0, 2).map((r, ri) => (
                          <div key={ri} className="text-muted-foreground flex items-start gap-1.5">
                            <span className="text-primary">•</span>
                            <span className="text-[11px] leading-tight">{r}</span>
                          </div>
                        ))}
                      </div>
                      <div className="pt-2 border-t border-border/40 flex justify-between items-center text-[11px] text-muted-foreground">
                        <span>
                          Ca: {h.raw_metrics.ca} | Ce: {h.raw_metrics.ce}
                        </span>
                        <button
                          onClick={() => {
                            setSelectedBlastComponent(h.component_id);
                            setActiveTab("blast");
                          }}
                          className="text-primary hover:underline flex items-center gap-1 font-medium"
                        >
                          Blast Radius <ArrowRight className="size-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  No architecture hotspots exceeded the evidence threshold (Score ≥ 3.0).
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: PROGRESSIVE INTERACTIVE DEPENDENCY GRAPH                            */}
      {/* ========================================================================= */}
      {!loading && activeTab === "graph" && (
        <Card className="border-border/60 bg-card/80 overflow-hidden relative shadow-xl">
          {/* Top Control Bar: Search, Type Filters, Graph Modes, Zoom */}
          <div className="p-3 border-b border-border/60 flex flex-wrap items-center justify-between gap-3 bg-muted/20">
            <div className="flex flex-wrap items-center gap-2">
              {/* Component Search with Autocomplete Dropdown */}
              <div className="relative w-64">
                <Search className="size-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search & focus component..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full h-8 pl-8 pr-3 rounded-lg border border-border/60 bg-background text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
                {searchResults.length > 0 && (
                  <div className="absolute left-0 right-0 top-9 rounded-lg border border-border bg-card shadow-2xl z-50 overflow-hidden py-1 max-h-60 overflow-y-auto">
                    {searchResults.map((sr) => (
                      <button
                        key={sr.component_id}
                        onClick={() => handleSelectSearchedComponent(sr)}
                        className="w-full text-left px-3 py-1.5 hover:bg-primary/10 text-xs flex items-center justify-between transition-colors"
                      >
                        <span className="font-semibold text-foreground truncate max-w-[170px]">{sr.name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">{sr.component_type}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Type Filter Select */}
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="h-8 px-2.5 rounded-lg border border-border/60 bg-background text-xs text-foreground focus:outline-none"
              >
                <option value="ALL">All Types ({components.length})</option>
                <option value="SERVICE">Services</option>
                <option value="ENDPOINT">API Endpoints</option>
                <option value="DATABASE">Databases</option>
                <option value="MODULE">Modules</option>
                <option value="CLASS">Classes</option>
                <option value="EXTERNAL_DEPENDENCY">External Packages</option>
              </select>

              {/* Graph Mode Buttons */}
              <div className="flex items-center rounded-lg border border-border/60 bg-background p-0.5 text-xs">
                <button
                  onClick={() => setGraphMode("HIGH_LEVEL")}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    graphMode === "HIGH_LEVEL"
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  High-Level Map
                </button>
                <button
                  onClick={() => setGraphMode("HOTSPOTS_ONLY")}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    graphMode === "HOTSPOTS_ONLY"
                      ? "bg-rose-600 text-white shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Hotspots ({hotspots.length})
                </button>
                <button
                  onClick={() => setGraphMode("SECURITY_CRITICAL")}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    graphMode === "SECURITY_CRITICAL"
                      ? "bg-cyan-600 text-white shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Security Paths ({securityCriticalNodeIds.size})
                </button>
              </div>

              {/* Expansion reset */}
              {expandedNodeIds.size > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCollapseExpansion}
                  className="h-8 text-xs text-muted-foreground gap-1"
                >
                  <Minimize2 className="size-3" />
                  Collapse Expansion ({expandedNodeIds.size})
                </Button>
              )}
            </div>

            {/* Viewport Zoom Controls */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setZoom((z) => Math.min(2.2, z + 0.15))}
                className="p-1.5 rounded-lg border border-border/60 bg-background text-muted-foreground hover:text-foreground transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="size-4" />
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
                className="p-1.5 rounded-lg border border-border/60 bg-background text-muted-foreground hover:text-foreground transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="size-4" />
              </button>
              <button
                onClick={() => {
                  setZoom(0.95);
                  setPan({ x: 30, y: 10 });
                }}
                className="p-1.5 rounded-lg border border-border/60 bg-background text-muted-foreground hover:text-foreground transition-colors"
                title="Reset View"
              >
                <RotateCcw className="size-4" />
              </button>
            </div>
          </div>

          {/* Density Notice Banner */}
          {components.length > 30 && (
            <div className="px-4 py-2 bg-primary/10 border-b border-primary/20 text-xs flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-foreground font-medium">
                <Info className="size-4 text-primary shrink-0" />
                <span>
                  Showing high-level architecture map ({layoutedNodes.length} of {components.length} components,{" "}
                  {visibleEdges.length} edges). Select any node to expand 1-hop or 2-hop dependencies.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setGraphMode("HOTSPOTS_ONLY")}
                  className="text-rose-400 font-semibold hover:underline"
                >
                  Show Hotspots
                </button>
                <span className="text-muted-foreground">•</span>
                <button
                  onClick={() => setGraphMode("SECURITY_CRITICAL")}
                  className="text-cyan-400 font-semibold hover:underline"
                >
                  Security Paths
                </button>
              </div>
            </div>
          )}

          {/* SVG Interactive Canvas */}
          <div
            ref={containerRef}
            className="w-full h-[660px] overflow-hidden cursor-grab active:cursor-grabbing bg-radial from-card/90 via-background to-background relative select-none"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          >
            <svg width="100%" height="100%" viewBox="0 0 1100 750" className="w-full h-full">
              <defs>
                <marker
                  id="arrow-normal"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" opacity="0.6" />
                </marker>
                <marker
                  id="arrow-active-ingress"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
                </marker>
                <marker
                  id="arrow-active-egress"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#c084fc" />
                </marker>
                <marker
                  id="arrow-circular"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#f43f5e" />
                </marker>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                <rect id="canvas-bg" x="-1000" y="-1000" width="3500" height="3000" fill="transparent" />

                {/* Architecture Layer Inferred Visual Bands */}
                {(["API", "SERVICES", "DOMAIN", "DATA", "INFRASTRUCTURE"] as ArchitectureLayer[]).map((layer) => {
                  const cfg = LAYER_CONFIG[layer];
                  return (
                    <g key={layer}>
                      <rect
                        x={90}
                        y={cfg.y - 45}
                        width={780}
                        height={90}
                        rx={16}
                        fill={cfg.bg}
                        stroke={cfg.border}
                        strokeDasharray="4 4"
                      />
                      <text
                        x={110}
                        y={cfg.y - 25}
                        fill={cfg.color}
                        fontSize="10"
                        fontWeight="bold"
                        letterSpacing="1"
                        className="uppercase opacity-70 pointer-events-none"
                      >
                        {cfg.subLabel}
                      </text>
                    </g>
                  );
                })}

                {/* External Dependencies Column Box */}
                <g>
                  <rect
                    x={890}
                    y={50}
                    width={180}
                    height={580}
                    rx={16}
                    fill={LAYER_CONFIG.EXTERNAL.bg}
                    stroke={LAYER_CONFIG.EXTERNAL.border}
                    strokeDasharray="4 4"
                  />
                  <text
                    x={910}
                    y={75}
                    fill={LAYER_CONFIG.EXTERNAL.color}
                    fontSize="10"
                    fontWeight="bold"
                    letterSpacing="1"
                    className="uppercase opacity-70 pointer-events-none"
                  >
                    External Packages
                  </text>
                </g>

                {/* Layered Dependency Curved Edges */}
                {visibleEdges.map((dep, idx) => {
                  const source = nodePosMap.get(dep.source_id);
                  const target = nodePosMap.get(dep.target_id);
                  if (!source || !target) return null;

                  const isCircular =
                    dep.is_circular || (circularNodeIds.has(dep.source_id) && circularNodeIds.has(dep.target_id));
                  const isIncoming = selectedNodeId && dep.target_id === selectedNodeId;
                  const isOutgoing = selectedNodeId && dep.source_id === selectedNodeId;
                  const isHovered =
                    hoveredNodeId && (dep.source_id === hoveredNodeId || dep.target_id === hoveredNodeId);
                  const isHighlighted = isIncoming || isOutgoing || isHovered;

                  const dx = target.x - source.x;
                  const dy = target.y - source.y;
                  const cx1 = source.x + dx * 0.2;
                  const cy1 = source.y + dy * 0.5;
                  const cx2 = source.x + dx * 0.8;
                  const cy2 = source.y + dy * 0.5;
                  const pathData = `M ${source.x} ${source.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${target.x} ${target.y}`;

                  return (
                    <path
                      key={`${dep.source_id}-${dep.target_id}-${idx}`}
                      d={pathData}
                      fill="none"
                      stroke={
                        isCircular
                          ? "#f43f5e"
                          : isIncoming
                          ? "#38bdf8"
                          : isOutgoing
                          ? "#c084fc"
                          : isHovered
                          ? "#facc15"
                          : "#475569"
                      }
                      strokeWidth={isCircular ? 2.5 : isHighlighted ? 2.2 : 1}
                      strokeDasharray={isCircular ? "5 3" : undefined}
                      opacity={isHighlighted ? 0.95 : isCircular ? 0.85 : 0.22}
                      markerEnd={
                        isCircular
                          ? "url(#arrow-circular)"
                          : isIncoming
                          ? "url(#arrow-active-ingress)"
                          : isOutgoing
                          ? "url(#arrow-active-egress)"
                          : "url(#arrow-normal)"
                      }
                      className="transition-all duration-300 pointer-events-none"
                    />
                  );
                })}

                {/* Nodes with Smart Label Prioritization */}
                {layoutedNodes.map((n) => {
                  const isSelected = selectedNodeId === n.component_id;
                  const isHovered = hoveredNodeId === n.component_id;
                  const isHotspot = hotspotMap.has(n.component_id);
                  const isCircular = circularNodeIds.has(n.component_id);
                  const isSecCritical = securityCriticalNodeIds.has(n.component_id);
                  const colors = TYPE_COLORS[n.component_type] || TYPE_COLORS.MODULE;

                  // Label display rule: Show label on primary nodes, hotspots, selected, hovered, or when zoomed in
                  const isPrimaryNode =
                    n.layer === "SERVICES" ||
                    n.layer === "DATA" ||
                    n.component_type === "DATABASE" ||
                    n.component_type === "SERVICE" ||
                    n.component_type === "ENDPOINT";
                  const showLabel =
                    isSelected || isHovered || isHotspot || isCircular || isPrimaryNode || zoom >= 1.25;

                  return (
                    <g
                      key={n.component_id}
                      transform={`translate(${n.x}, ${n.y})`}
                      className="cursor-pointer transition-transform duration-200"
                      onMouseEnter={() => setHoveredNodeId(n.component_id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedNodeId(isSelected ? null : n.component_id);
                      }}
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        setDraggedNodeId(n.component_id);
                      }}
                    >
                      {/* Highlight Outer Rings */}
                      {isSelected && (
                        <circle r="30" fill="none" stroke="#38bdf8" strokeWidth="2.5" strokeDasharray="4 2" />
                      )}
                      {isHotspot && (
                        <circle
                          r="28"
                          fill="none"
                          stroke="#f59e0b"
                          strokeWidth="2"
                          opacity="0.85"
                          className="animate-pulse"
                        />
                      )}
                      {isCircular && (
                        <circle r="26" fill="none" stroke="#f43f5e" strokeWidth="2" strokeDasharray="3 2" />
                      )}

                      {/* Main Node Circle */}
                      <circle
                        r={isHotspot ? 20 : isSelected ? 20 : 16}
                        fill={colors.bg}
                        stroke={isCircular ? "#f43f5e" : isHotspot ? "#f59e0b" : isSecCritical ? "#06b6d4" : colors.stroke}
                        strokeWidth={isSelected || isHovered ? 3 : 2}
                        className="transition-all duration-200 shadow-md"
                      />

                      {/* Inner glyph/icon indicator */}
                      <text
                        textAnchor="middle"
                        dy=".3em"
                        fontSize={isHotspot || isSelected ? "11" : "9"}
                        fontWeight="bold"
                        fill={colors.text}
                        className="pointer-events-none select-none font-mono"
                      >
                        {n.component_type === "DATABASE"
                          ? "DB"
                          : n.component_type === "SERVICE"
                          ? "SVC"
                          : n.component_type === "ENDPOINT"
                          ? "API"
                          : n.component_type === "CLASS"
                          ? "CLS"
                          : n.component_type === "FUNCTION"
                          ? "FN"
                          : n.component_type === "EXTERNAL_DEPENDENCY"
                          ? "EXT"
                          : "MOD"}
                      </text>

                      {/* Smart Label Below Node */}
                      {showLabel && (
                        <g transform="translate(0, 26)">
                          <rect
                            x={-(Math.min(n.name.length * 4.5 + 8, 90) / 2)}
                            y="-2"
                            width={Math.min(n.name.length * 4.5 + 8, 90)}
                            height="16"
                            rx="4"
                            fill="#0b0f19"
                            fillOpacity="0.85"
                            stroke="#1e293b"
                            strokeWidth="0.8"
                          />
                          <text
                            textAnchor="middle"
                            dy="9"
                            fontSize="9"
                            fontWeight={isSelected || isHotspot ? "bold" : "medium"}
                            fill={isSelected ? "#38bdf8" : isHotspot ? "#fde68a" : "#cbd5e1"}
                            className="pointer-events-none select-none"
                          >
                            {n.name.length > 15 ? `${n.name.slice(0, 13)}…` : n.name}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* Floating Legend (Phase 10) */}
            <div className="absolute bottom-4 left-4 bg-card/90 backdrop-blur-md border border-border/70 rounded-xl p-3 text-xs shadow-xl space-y-1.5 pointer-events-auto">
              <div className="font-semibold text-[11px] text-foreground uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Layers className="size-3 text-primary" />
                Graph Legend
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-indigo-500" />
                  <span className="text-muted-foreground">Service</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-sky-500" />
                  <span className="text-muted-foreground">API / Endpoint</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-amber-500" />
                  <span className="text-muted-foreground">Database</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-purple-500" />
                  <span className="text-muted-foreground">Class / Model</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-emerald-500" />
                  <span className="text-muted-foreground">Function</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full bg-zinc-500" />
                  <span className="text-muted-foreground">External Package</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full border border-rose-500 bg-rose-500/20" />
                  <span className="text-rose-400">Circular Cycle</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="size-2.5 rounded-full border border-amber-400 bg-amber-400/20" />
                  <span className="text-amber-400">Architecture Hotspot</span>
                </div>
              </div>
            </div>

            {/* Selected Node Inspector Drawer (Phase 13 & 15) */}
            {selectedNodeId && nodePosMap.has(selectedNodeId) && (
              <div className="absolute top-4 right-4 w-80 max-h-[620px] overflow-y-auto bg-card/95 backdrop-blur-md border border-primary/40 rounded-2xl p-4 shadow-2xl space-y-3 z-40 animate-in fade-in slide-in-from-right-4 duration-200">
                {(() => {
                  const n = nodePosMap.get(selectedNodeId)!.node;
                  const hotspotInfo = hotspotMap.get(n.component_id);
                  const isInCircularDep = circularNodeIds.has(n.component_id);
                  const linkedTrace = traceability.filter((t) => t.component_id === n.component_id);

                  return (
                    <>
                      <div className="flex items-start justify-between pb-2 border-b border-border/60">
                        <div className="space-y-0.5 max-w-[210px]">
                          <div className="font-bold text-sm text-foreground truncate">{n.name}</div>
                          <Badge tone="primary" className="text-[10px]">
                            {n.component_type}
                          </Badge>
                        </div>
                        <button
                          onClick={() => setSelectedNodeId(null)}
                          className="text-muted-foreground hover:text-foreground text-xs p-1 rounded-md"
                        >
                          ✕
                        </button>
                      </div>

                      <div className="text-xs text-muted-foreground font-mono break-all bg-background/50 p-2 rounded-lg border border-border/40">
                        {n.file_path}
                        {n.line_number && <span className="text-primary font-bold">:{n.line_number}</span>}
                      </div>

                      {/* Architecture Metrics Grid */}
                      <div className="grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-background/60 border border-border/40 text-xs">
                        <div>
                          <span className="text-muted-foreground">Fan-in (Ca):</span>{" "}
                          <span className="font-bold text-foreground">{n.ca}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Fan-out (Ce):</span>{" "}
                          <span className="font-bold text-foreground">{n.ce}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Instability (I):</span>{" "}
                          <span className="font-bold text-foreground">
                            {n.instability !== null && n.instability !== undefined ? n.instability.toFixed(2) : "N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">LCOM4:</span>{" "}
                          <span className="font-bold text-foreground">{n.lcom4 ?? "N/A"}</span>
                        </div>
                      </div>

                      {/* Circular Dependency Status */}
                      {isInCircularDep && (
                        <div className="p-2 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-[11px] flex items-center gap-2">
                          <RotateCcw className="size-3.5 text-rose-400 shrink-0" />
                          <span className="font-medium">This component is part of a circular dependency cycle.</span>
                        </div>
                      )}

                      {/* Hotspot Evidence */}
                      {hotspotInfo && hotspotInfo.reasons.length > 0 && (
                        <div className="p-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-[11px] space-y-1">
                          <div className="font-bold flex items-center gap-1">
                            <AlertTriangle className="size-3 text-amber-400" />
                            Hotspot Evidence (Score: {hotspotInfo.hotspot_score}):
                          </div>
                          {hotspotInfo.reasons.map((r, ri) => (
                            <div key={ri} className="flex items-start gap-1">
                              <span>•</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Security Findings / Traceability Link */}
                      <div className="space-y-1 text-xs">
                        <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">
                          Security Correlation
                        </div>
                        {linkedTrace.length > 0 ? (
                          <div className="space-y-1 p-2 rounded-lg bg-background/50 border border-border/40">
                            {linkedTrace.map((lt, li) => (
                              <div key={li} className="text-[11px] space-y-0.5">
                                {lt.finding_title && (
                                  <div className="text-rose-400 font-medium">Finding: {lt.finding_title}</div>
                                )}
                                {lt.control_name && (
                                  <div className="text-muted-foreground">Control: {lt.control_name} ({lt.control_state})</div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[11px] text-muted-foreground italic">
                            No security findings are currently linked to this component.
                          </div>
                        )}
                      </div>

                      {/* Progressive Exploration Actions */}
                      <div className="space-y-1.5 pt-1">
                        <div className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider">
                          Graph Exploration
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleExpand1Hop(n.component_id)}
                            className="text-xs justify-center"
                          >
                            Expand 1-Hop
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleExpand2Hop(n.component_id)}
                            className="text-xs justify-center"
                          >
                            Expand 2-Hop
                          </Button>
                        </div>
                      </div>

                      {/* Cross-Tab Actions */}
                      <div className="space-y-1.5 pt-1">
                        <Button
                          variant="primary"
                          size="sm"
                          className="w-full justify-center text-xs"
                          onClick={() => {
                            setSelectedBlastComponent(n.component_id);
                            setActiveTab("blast");
                          }}
                        >
                          <Crosshair className="size-3.5 mr-1.5" />
                          Analyze Blast Radius
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full justify-center text-xs"
                          onClick={() => {
                            setSimComponent(n.component_id);
                            setSimResult(null);
                            setActiveTab("remediation");
                          }}
                        >
                          <Sparkles className="size-3.5 mr-1.5" />
                          Simulate Remediation
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full justify-center text-xs"
                          onClick={() => {
                            setActiveTab("traceability");
                          }}
                        >
                          <GitMerge className="size-3.5 mr-1.5" />
                          View Traceability
                        </Button>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: COUPLING & COHESION MATRIX                                         */}
      {/* ========================================================================= */}
      {!loading && activeTab === "metrics" && (
        <div className="space-y-4">
          <Card className="border-border/60 bg-card/70">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <Boxes className="size-4 text-primary" />
                    Coupling & Cohesion Analysis Matrix
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Coupling shows how strongly components depend on each other. Cohesion indicates how focused each component's responsibilities are.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={metricsSortBy}
                    onChange={(e) => setMetricsSortBy(e.target.value as any)}
                    className="h-8 px-2.5 rounded-lg border border-border/80 bg-background text-xs text-foreground focus:outline-none"
                  >
                    <option value="COUPLING">Sort: Highest Coupling (Ca + Ce)</option>
                    <option value="LCOM4">Sort: Lowest Cohesion (LCOM4)</option>
                    <option value="INSTABILITY_HIGH">Sort: Highest Instability</option>
                    <option value="INSTABILITY_LOW">Sort: Lowest Instability</option>
                    <option value="NAME">Sort: Component Name (A-Z)</option>
                  </select>
                  <Input
                    placeholder="Search components..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-52 h-8 text-xs"
                  />
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* Quick Highlights Summary Cards */}
          {couplingHighlights && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Card className="border-border/60 bg-card/60 p-4 space-y-1">
                <div className="text-[11px] font-bold uppercase tracking-wider text-rose-400">
                  Highest Coupling
                </div>
                <div className="font-bold text-foreground text-sm truncate">
                  {couplingHighlights.highestCoupling.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  Ca: {couplingHighlights.highestCoupling.ca} | Ce: {couplingHighlights.highestCoupling.ce} | Total:{" "}
                  {couplingHighlights.highestCoupling.ca + couplingHighlights.highestCoupling.ce}
                </div>
              </Card>

              <Card className="border-border/60 bg-card/60 p-4 space-y-1">
                <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                  Lowest Cohesion
                </div>
                <div className="font-bold text-foreground text-sm truncate">
                  {couplingHighlights.lowestCohesion.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  LCOM4: {couplingHighlights.lowestCohesion.lcom4 ?? "N/A"}{" "}
                  {couplingHighlights.lowestCohesion.is_god_candidate && "• God Candidate"}
                </div>
              </Card>

              <Card className="border-border/60 bg-card/60 p-4 space-y-1">
                <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                  Most Balanced Component
                </div>
                <div className="font-bold text-foreground text-sm truncate">
                  {couplingHighlights.mostBalanced.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  Instability:{" "}
                  {couplingHighlights.mostBalanced.instability !== null
                    ? couplingHighlights.mostBalanced.instability?.toFixed(2)
                    : "N/A"}{" "}
                  (Healthy balance)
                </div>
              </Card>
            </div>
          )}

          {/* Metrics Table */}
          <Card className="border-border/60 bg-card/70">
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-y border-border/60 bg-muted/30 text-muted-foreground font-semibold">
                    <th className="py-2.5 px-4">Component Name</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Location</th>
                    <th className="py-2.5 px-2 text-center" title="Afferent Coupling (Incoming dependencies / Fan-in)">
                      Ca ⓘ
                    </th>
                    <th className="py-2.5 px-2 text-center" title="Efferent Coupling (Outgoing dependencies / Fan-out)">
                      Ce ⓘ
                    </th>
                    <th className="py-2.5 px-3 text-center" title="Instability = Ce / (Ca + Ce)">
                      Instability (I) ⓘ
                    </th>
                    <th className="py-2.5 px-3 text-center" title="LCOM4 Class Cohesion">
                      LCOM4 ⓘ
                    </th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {sortedAndFilteredComponents.map((c) => (
                    <tr key={c.component_id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-2.5 px-4 font-semibold text-foreground">{c.name}</td>
                      <td className="py-2.5 px-3">
                        <Badge tone="neutral" className="text-[10px]">
                          {c.component_type}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-muted-foreground font-mono text-[11px] truncate max-w-[200px]">
                        {c.file_path}
                      </td>
                      <td className="py-2.5 px-2 text-center font-bold text-foreground">{c.ca}</td>
                      <td className="py-2.5 px-2 text-center font-bold text-foreground">{c.ce}</td>
                      <td className="py-2.5 px-3 text-center">
                        {c.instability !== null && c.instability !== undefined ? (
                          <span
                            className={`font-mono font-semibold ${
                              c.instability > 0.8
                                ? "text-amber-400"
                                : c.instability < 0.2
                                ? "text-cyan-400"
                                : "text-foreground"
                            }`}
                          >
                            {c.instability.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">N/A</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono">{c.lcom4 ?? "—"}</td>
                      <td className="py-2.5 px-3 text-center">
                        {c.in_circular_dependency ? (
                          <Badge tone="danger" className="text-[10px]">
                            Circular
                          </Badge>
                        ) : c.is_god_candidate ? (
                          <Badge tone="warning" className="text-[10px]">
                            God Candidate
                          </Badge>
                        ) : (
                          <Badge tone="success" className="text-[10px]">
                            Stable
                          </Badge>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setSelectedBlastComponent(c.component_id);
                              setActiveTab("blast");
                            }}
                            className="text-[11px] h-7"
                          >
                            Blast Radius
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedNodeId(c.component_id);
                              handleExpand1Hop(c.component_id);
                              setActiveTab("graph");
                            }}
                            className="text-[11px] h-7"
                          >
                            View in Graph
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: ARCHITECTURE HOTSPOTS                                              */}
      {/* ========================================================================= */}
      {!loading && activeTab === "hotspots" && (
        <div className="space-y-4">
          <Card className="border-border/60 bg-card/70">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <ShieldAlert className="size-4 text-rose-400" />
                    Evidence-Based Architecture Hotspots
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Where should you look first? Deterministic hotspots ranked by high coupling, low cohesion, circular cycles, and correlated security findings.
                  </p>
                </div>
                <Badge tone="danger" className="text-xs">
                  {hotspots.length} Classified Hotspot(s)
                </Badge>
              </div>
            </CardHeader>
          </Card>

          {hotspots.length === 0 ? (
            <Card className="border-border/60 bg-card/60 p-12 text-center">
              <div className="flex flex-col items-center justify-center gap-2">
                <CheckCircle2 className="size-8 text-success" />
                <div className="text-sm font-semibold text-foreground">No Architecture Hotspots Identified</div>
                <div className="text-xs text-muted-foreground max-w-md">
                  No components in this scan currently exceed the multi-factor threshold for structural risk.
                </div>
              </div>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {hotspots.map((h) => (
                <Card key={h.component_id} className="border-border/60 bg-card/70 hover:border-primary/40 transition-colors">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-bold text-base text-foreground">{h.component_name}</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">{h.file_path}</div>
                      </div>
                      <Badge
                        tone={
                          h.hotspot_level === "CRITICAL" ? "danger" : h.hotspot_level === "HIGH" ? "warning" : "primary"
                        }
                        className="text-xs font-semibold"
                      >
                        {h.hotspot_level} ({h.hotspot_score})
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-1">
                      <span className="text-[11px] font-semibold text-foreground">Trigger Reasons:</span>
                      {h.reasons.map((r, ri) => (
                        <div key={ri} className="text-xs text-muted-foreground flex items-start gap-2">
                          <span className="text-danger font-bold">•</span>
                          <span>{r}</span>
                        </div>
                      ))}
                    </div>

                    <div className="grid grid-cols-3 gap-2 p-2 rounded-lg bg-background/60 border border-border/40 text-[11px]">
                      <div>
                        <span className="text-muted-foreground">Afferent (Ca):</span>{" "}
                        <span className="font-bold text-foreground">{h.raw_metrics.ca}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Efferent (Ce):</span>{" "}
                        <span className="font-bold text-foreground">{h.raw_metrics.ce}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Instability:</span>{" "}
                        <span className="font-bold text-foreground">{h.raw_metrics.instability ?? "N/A"}</span>
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2 border-t border-border/40">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setSelectedNodeId(h.component_id);
                          handleExpand1Hop(h.component_id);
                          setActiveTab("graph");
                        }}
                        className="text-xs"
                      >
                        Inspect in Graph
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          setSelectedBlastComponent(h.component_id);
                          setActiveTab("blast");
                        }}
                        className="text-xs"
                      >
                        Analyze Impact
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: BLAST RADIUS & IMPACT ANALYZER                                     */}
      {/* ========================================================================= */}
      {!loading && activeTab === "blast" && (
        <div className="space-y-4">
          {/* Target Component Selector & Filter Card */}
          <Card className="border-border/60 bg-card/70">
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground flex items-center gap-2">
                    <Crosshair className="size-4 text-primary" />
                    Component Blast Radius & Downstream Impact Analyzer
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Select a component from the active scan to trace reverse reachability, dependency depth, callers, and correlated security controls.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="size-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Filter components..."
                      value={blastSearchFilter}
                      onChange={(e) => setBlastSearchFilter(e.target.value)}
                      className="h-9 pl-8 pr-3 rounded-lg border border-border/80 bg-background text-xs text-foreground focus:outline-none focus:border-primary w-40"
                    />
                  </div>
                  <select
                    value={selectedBlastComponent}
                    onChange={(e) => {
                      const newId = e.target.value;
                      setSelectedBlastComponent(newId);
                      setBlastData(null);
                      setBlastError(null);
                      fetchBlastRadius(newId);
                    }}
                    className="h-9 px-3 rounded-lg border border-border/80 bg-background text-xs text-foreground focus:outline-none focus:border-primary max-w-xs"
                  >
                    {components
                      .filter((c) => {
                        if (!blastSearchFilter.trim()) return true;
                        const q = blastSearchFilter.toLowerCase();
                        return (
                          c.name.toLowerCase().includes(q) ||
                          c.component_type.toLowerCase().includes(q) ||
                          c.file_path.toLowerCase().includes(q)
                        );
                      })
                      .map((c) => (
                        <option key={c.component_id} value={c.component_id}>
                          {c.name} ({c.component_type})
                        </option>
                      ))}
                  </select>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => fetchBlastRadius(selectedBlastComponent)}
                    disabled={blastLoading || !selectedBlastComponent}
                  >
                    {blastLoading ? (
                      <>
                        <Spinner className="size-3.5 mr-1.5" />
                        Calculating...
                      </>
                    ) : (
                      <>
                        <Crosshair className="size-3.5 mr-1.5" />
                        Compute Blast Radius
                      </>
                    )}
                  </Button>
                  {selectedBlastComponent && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSimComponent(selectedBlastComponent);
                        setSimResult(null);
                        setActiveTab("remediation");
                      }}
                      className="text-xs"
                    >
                      <Sparkles className="size-3.5 mr-1.5" />
                      Simulate Remediation
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* Loading State */}
          {blastLoading && (
            <Card className="border-border/60 bg-card/60 p-10 text-center space-y-3">
              <Spinner className="size-6 mx-auto text-primary" />
              <div className="text-sm font-semibold text-foreground">Calculating blast radius...</div>
              <div className="text-xs text-muted-foreground max-w-md mx-auto">
                Traversing reverse dependency reachability, transitive callers, and security associations for the selected component...
              </div>
            </Card>
          )}

          {/* Error State with Retry */}
          {!blastLoading && blastError && (
            <Card className="border-rose-500/40 bg-rose-500/5 p-8 text-center space-y-3">
              <AlertTriangle className="size-8 mx-auto text-rose-400" />
              <div className="text-sm font-semibold text-rose-300">Unable to calculate blast radius</div>
              <div className="text-xs text-muted-foreground max-w-md mx-auto">
                {blastError}
              </div>
              <div className="pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchBlastRadius(selectedBlastComponent)}
                  className="text-xs"
                >
                  <RefreshCw className="size-3.5 mr-1.5" />
                  Retry
                </Button>
              </div>
            </Card>
          )}

          {/* Blast Radius Results */}
          {!blastLoading && !blastError && blastData && (
            <div className="space-y-4">
              {/* KPI Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card className="border-border/60 bg-card/60">
                  <CardContent className="p-4 space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                      Direct Dependents
                    </div>
                    <div className="text-2xl font-bold text-foreground">
                      {blastData.direct_dependents_count}
                    </div>
                    <div className="text-[11px] text-muted-foreground">1-hop direct callers</div>
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60">
                  <CardContent className="p-4 space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                      Total Reachable Dependents
                    </div>
                    <div className="text-2xl font-bold text-cyan-400">
                      {blastData.transitive_dependents_count}
                    </div>
                    <div className="text-[11px] text-muted-foreground">Transitive ripple closure</div>
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60">
                  <CardContent className="p-4 space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                      Max Dependency Depth
                    </div>
                    <div className="text-2xl font-bold text-foreground">
                      {blastData.max_impact_depth} hops
                    </div>
                    <div className="text-[11px] text-muted-foreground">Longest reverse path</div>
                  </CardContent>
                </Card>

                <Card className="border-border/60 bg-card/60">
                  <CardContent className="p-4 space-y-1">
                    <div className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                      Architectural Risk Level
                    </div>
                    <div className="text-2xl font-bold">
                      <span
                        className={
                          blastData.risk_level === "CRITICAL"
                            ? "text-danger"
                            : blastData.risk_level === "HIGH"
                            ? "text-warning"
                            : "text-success"
                        }
                      >
                        {blastData.risk_level}
                      </span>
                    </div>
                    <div className="text-[11px] text-muted-foreground">Reachable exposure</div>
                  </CardContent>
                </Card>
              </div>

              {/* Empty Downstream State (STEP 6) */}
              {blastData.direct_dependents_count === 0 && blastData.transitive_dependents_count === 0 ? (
                <Card className="border-border/60 bg-card/70 p-8 text-center space-y-3">
                  <CheckCircle2 className="size-8 mx-auto text-emerald-400" />
                  <div className="text-sm font-semibold text-foreground">No downstream impact detected</div>
                  <div className="text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">
                    This component does not currently have reachable dependents in the selected architecture graph.
                  </div>
                  <div className="text-[11px] text-muted-foreground max-w-md mx-auto">
                    Because this component has no incoming callers in the current AST snapshot, changes or refactorings are locally contained.
                  </div>
                  <div className="pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSimComponent(blastData.target_component_id);
                        setSimResult(null);
                        setActiveTab("remediation");
                      }}
                      className="text-xs"
                    >
                      <Sparkles className="size-3.5 mr-1.5" />
                      Simulate Remediation
                    </Button>
                  </div>
                </Card>
              ) : (
                <>
                  {/* IMPACT PATH SUMMARY (STEP 4) */}
                  <Card className="border-border/60 bg-card/70 p-4">
                    <div className="text-xs font-semibold text-foreground uppercase tracking-wider mb-3 flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Crosshair className="size-4 text-primary" />
                        IMPACT PATH
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSimComponent(blastData.target_component_id);
                          setSimResult(null);
                          setActiveTab("remediation");
                        }}
                        className="text-xs h-7"
                      >
                        <Sparkles className="size-3 mr-1 text-primary" />
                        Simulate Remediation for this Component
                      </Button>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                      <div className="p-3 rounded-xl bg-background/60 border border-border/50">
                        <div className="text-muted-foreground text-[11px]">Target Component</div>
                        <div className="font-bold text-foreground truncate mt-0.5" title={blastData.target_component_name}>
                          {blastData.target_component_name}
                        </div>
                        <div className="text-[10px] text-primary font-mono truncate">{blastData.target_component_id}</div>
                      </div>
                      <div className="p-3 rounded-xl bg-background/60 border border-border/50">
                        <div className="text-muted-foreground text-[11px]">Direct Dependents</div>
                        <div className="font-bold text-foreground mt-0.5">{blastData.direct_dependents_count} immediate callers</div>
                        <div className="text-[10px] text-muted-foreground">1-hop reverse dependencies</div>
                      </div>
                      <div className="p-3 rounded-xl bg-background/60 border border-border/50">
                        <div className="text-muted-foreground text-[11px]">Reachable Dependents</div>
                        <div className="font-bold text-cyan-400 mt-0.5">{blastData.transitive_dependents_count} downstream closure</div>
                        <div className="text-[10px] text-muted-foreground">Total transitive reachable callers</div>
                      </div>
                      <div className="p-3 rounded-xl bg-background/60 border border-border/50">
                        <div className="text-muted-foreground text-[11px]">Maximum Dependency Depth</div>
                        <div className="font-bold text-foreground mt-0.5">{blastData.max_impact_depth} hops deep</div>
                        <div className="text-[10px] text-muted-foreground">Longest ripple cascade path</div>
                      </div>
                    </div>
                  </Card>

                  {/* Impact Reachability Chain (STEP 3) */}
                  <Card className="border-border/60 bg-card/70 p-4 space-y-3">
                    <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                      <GitMerge className="size-4 text-primary" />
                      Impact Reachability Chain
                    </div>
                    <div className="p-4 rounded-xl bg-background/40 border border-border/40 space-y-4">
                      {/* Target Node */}
                      <div className="flex items-center gap-3">
                        <div className="px-3 py-1.5 rounded-lg bg-primary/20 border border-primary/50 text-primary font-bold text-xs flex items-center gap-2">
                          <span className="size-2 rounded-full bg-primary animate-pulse" />
                          TARGET: {blastData.target_component_name}
                        </div>
                        <span className="text-xs text-muted-foreground font-mono text-[11px] truncate">
                          {components.find((c) => c.component_id === blastData.target_component_id)?.file_path}
                        </span>
                      </div>

                      {/* Tree Flow */}
                      <div className="pl-6 border-l-2 border-dashed border-primary/40 ml-4 space-y-4">
                        {/* Direct Callers */}
                        <div className="space-y-1.5">
                          <div className="text-[11px] font-semibold text-foreground flex items-center gap-2">
                            <span className="size-1.5 rounded-full bg-amber-400" />
                            DIRECT DEPENDENTS ({blastData.direct_dependents_count} components, 1 hop)
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {blastData.direct_dependents.slice(0, 8).map((dep) => (
                              <button
                                key={dep.component_id}
                                onClick={() => {
                                  setSelectedBlastComponent(dep.component_id);
                                  setBlastData(null);
                                  setBlastError(null);
                                  fetchBlastRadius(dep.component_id);
                                }}
                                className="px-2.5 py-1 rounded-md bg-card/80 border border-border/60 text-[11px] hover:border-primary/60 hover:text-primary transition-colors text-foreground flex items-center gap-1.5"
                                title={`Click to analyze blast radius for ${dep.name}`}
                              >
                                <span className="font-medium">{dep.name}</span>
                                <Badge tone="neutral" className="text-[9px] py-0 px-1">
                                  {dep.component_type}
                                </Badge>
                              </button>
                            ))}
                            {blastData.direct_dependents.length > 8 && (
                              <span className="text-[11px] text-muted-foreground self-center">
                                +{blastData.direct_dependents.length - 8} more
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Transitive Callers (hops > 1) */}
                        {blastData.transitive_dependents.filter((d) => d.hop_depth > 1).length > 0 && (
                          <div className="space-y-1.5">
                            <div className="text-[11px] font-semibold text-foreground flex items-center gap-2">
                              <span className="size-1.5 rounded-full bg-cyan-400" />
                              TRANSITIVE DEPENDENTS ({blastData.transitive_dependents.filter((d) => d.hop_depth > 1).length} components, 2+ hops)
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {blastData.transitive_dependents
                                .filter((d) => d.hop_depth > 1)
                                .slice(0, 8)
                                .map((dep) => (
                                  <button
                                    key={dep.component_id}
                                    onClick={() => {
                                      setSelectedBlastComponent(dep.component_id);
                                      setBlastData(null);
                                      setBlastError(null);
                                      fetchBlastRadius(dep.component_id);
                                    }}
                                    className="px-2.5 py-1 rounded-md bg-card/80 border border-border/60 text-[11px] hover:border-primary/60 hover:text-primary transition-colors text-foreground flex items-center gap-1.5"
                                    title={`Click to analyze blast radius for ${dep.name}`}
                                  >
                                    <span className="font-medium">{dep.name}</span>
                                    <span className="text-[9px] text-muted-foreground">({dep.hop_depth} hops)</span>
                                  </button>
                                ))}
                              {blastData.transitive_dependents.filter((d) => d.hop_depth > 1).length > 8 && (
                                <span className="text-[11px] text-muted-foreground self-center">
                                  +{blastData.transitive_dependents.filter((d) => d.hop_depth > 1).length - 8} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Reachable Impact Entities */}
                        <div className="space-y-1.5">
                          <div className="text-[11px] font-semibold text-foreground flex items-center gap-2">
                            <span className="size-1.5 rounded-full bg-purple-400" />
                            REACHABLE IMPACT ({blastData.affected_endpoints.length} Endpoints, {blastData.affected_services.length} Services)
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {blastData.affected_endpoints.length === 0 && blastData.affected_services.length === 0
                              ? "No external endpoints or services directly in this cascade."
                              : "Cascade reaches the public endpoints and service boundaries listed below."}
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Component Breakdown Table (STEP 5) */}
                  <Card className="border-border/60 bg-card/70">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-sm text-foreground flex items-center gap-2">
                          <Layers className="size-4 text-primary" />
                          Reachable Component Closure ({blastData.transitive_dependents.length})
                        </h4>
                        <span className="text-[11px] text-muted-foreground">
                          Click any component to make it the new target or simulate remediation
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0 overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-y border-border/60 bg-muted/30 text-muted-foreground font-semibold">
                            <th className="py-2.5 px-4">Component</th>
                            <th className="py-2.5 px-3">Relationship</th>
                            <th className="py-2.5 px-3">Hop</th>
                            <th className="py-2.5 px-4">Impact Path</th>
                            <th className="py-2.5 px-4 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/40">
                          {blastData.transitive_dependents.map((dep) => (
                            <tr key={dep.component_id} className="hover:bg-muted/20 transition-colors">
                              <td className="py-2.5 px-4">
                                <div className="font-semibold text-foreground">{dep.name}</div>
                                <div className="text-[10px] text-muted-foreground font-mono truncate max-w-[200px]">
                                  {dep.file_path}
                                </div>
                              </td>
                              <td className="py-2.5 px-3">
                                <Badge
                                  tone={dep.hop_depth === 1 ? "warning" : "neutral"}
                                  className="text-[10px]"
                                >
                                  {dep.relationship || (dep.hop_depth === 1 ? "Direct dependent" : "Transitive dependent")}
                                </Badge>
                              </td>
                              <td className="py-2.5 px-3 font-semibold text-foreground">
                                {dep.hop_depth} {dep.hop_depth === 1 ? "hop" : "hops"}
                              </td>
                              <td className="py-2.5 px-4 font-mono text-[11px] text-muted-foreground max-w-xs truncate" title={dep.path}>
                                {dep.path || `${blastData.target_component_name} -> ${dep.name}`}
                              </td>
                              <td className="py-2.5 px-4 text-right space-x-2">
                                <button
                                  onClick={() => {
                                    setSelectedBlastComponent(dep.component_id);
                                    setBlastData(null);
                                    setBlastError(null);
                                    fetchBlastRadius(dep.component_id);
                                  }}
                                  className="px-2 py-1 rounded bg-background border border-border/60 text-[11px] text-foreground hover:border-primary hover:text-primary transition-colors"
                                >
                                  Target this
                                </button>
                                <button
                                  onClick={() => {
                                    setSimComponent(dep.component_id);
                                    setSimResult(null);
                                    setActiveTab("remediation");
                                  }}
                                  className="px-2 py-1 rounded bg-primary/10 border border-primary/30 text-[11px] text-primary hover:bg-primary/20 transition-colors"
                                >
                                  Simulate fix
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </CardContent>
                  </Card>

                  {/* Downstream Structural Entities & Security Correlations */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className="border-border/60 bg-card/70">
                      <CardHeader className="pb-3">
                        <h4 className="font-semibold text-sm text-foreground">Affected Endpoints & Services</h4>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {blastData.affected_endpoints.length > 0 || blastData.affected_services.length > 0 ? (
                          <>
                            {blastData.affected_endpoints.map((ep, i) => (
                              <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-background/50 border border-border/40">
                                <div className="flex items-center gap-2">
                                  <Badge tone="primary">ENDPOINT</Badge>
                                  <span className="font-mono text-foreground font-semibold">{ep.name || ep.component_id}</span>
                                </div>
                                <span className="text-[10px] text-muted-foreground">{ep.hop_depth} hops</span>
                              </div>
                            ))}
                            {blastData.affected_services.map((svc, i) => (
                              <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-background/50 border border-border/40">
                                <div className="flex items-center gap-2">
                                  <Badge tone="neutral">SERVICE</Badge>
                                  <span className="font-mono text-foreground font-semibold">{svc.name || svc.component_id}</span>
                                </div>
                                <span className="text-[10px] text-muted-foreground">{svc.hop_depth} hops</span>
                              </div>
                            ))}
                          </>
                        ) : (
                          <div className="text-xs text-muted-foreground py-4 text-center">
                            No downstream endpoints or services are reachable from this component.
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="border-border/60 bg-card/70">
                      <CardHeader className="pb-3">
                        <h4 className="font-semibold text-sm text-foreground">Correlated Security Controls & Risks</h4>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {blastData.affected_controls.length > 0 || blastData.affected_scenarios.length > 0 ? (
                          <>
                            {blastData.affected_controls.map((ctrl, i) => (
                              <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-background/50 border border-border/40">
                                <div className="flex items-center gap-2">
                                  <Badge tone="warning">CONTROL</Badge>
                                  <span className="text-foreground font-medium">{ctrl.control_name || ctrl.control_id || "Security Control"}</span>
                                </div>
                                <span className="text-[10px] text-muted-foreground font-mono">{ctrl.scope || "repo"}</span>
                              </div>
                            ))}
                            {blastData.affected_scenarios.map((sc, i) => (
                              <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-background/50 border border-border/40">
                                <div className="flex items-center gap-2">
                                  <Badge tone="danger">RISK</Badge>
                                  <span className="text-foreground font-medium">{sc.title || sc.scenario_id || "Risk Scenario"}</span>
                                </div>
                                <span className="text-[10px] text-danger font-semibold">{sc.severity || "HIGH"}</span>
                              </div>
                            ))}
                          </>
                        ) : (
                          <div className="text-xs text-muted-foreground py-4 text-center">
                            Security impact: No linked security relationships in this simulation.
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 6: UNIFIED TRACEABILITY                                               */}
      {/* ========================================================================= */}
      {!loading && activeTab === "traceability" && (
        <Card className="border-border/60 bg-card/70">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <GitMerge className="size-4 text-primary" />
                  Unified Traceability Explorer
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Provenance chain: Requirement &rarr; Knowledge Document &rarr; Component &rarr; Finding &rarr; Control &rarr; Risk.
                </p>
              </div>
              <Badge tone="primary" className="text-xs">
                {traceability.length} Provenance Chains
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            {traceability.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                No traceability relationships currently mapped for this scan scope.
              </div>
            ) : (
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-y border-border/60 bg-muted/30 text-muted-foreground font-semibold">
                    <th className="py-2.5 px-4">Component</th>
                    <th className="py-2.5 px-3">Requirement Standard</th>
                    <th className="py-2.5 px-3">Security Control</th>
                    <th className="py-2.5 px-3">Security Finding</th>
                    <th className="py-2.5 px-3">Risk Scenario</th>
                    <th className="py-2.5 px-4">Provenance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {traceability.map((t) => (
                    <tr key={t.chain_id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-3 px-4 font-semibold text-foreground">
                        <div>{t.component_name}</div>
                        <div className="text-[11px] text-muted-foreground font-mono truncate max-w-[160px]">
                          {t.file_path}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        {t.requirement_doc_name ? (
                          <Badge tone="neutral" className="text-[10px]">
                            {t.requirement_doc_name}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">N/A</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {t.control_name ? (
                          <div>
                            <div className="font-medium text-foreground">{t.control_name}</div>
                            <Badge
                              tone={t.control_state === "PASS" ? "success" : "danger"}
                              className="text-[9px] mt-0.5"
                            >
                              {t.control_state || "ABSENT"}
                            </Badge>
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">N/A</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {t.finding_title ? (
                          <div>
                            <div className="font-medium text-foreground">{t.finding_title}</div>
                            <Badge
                              tone={t.finding_severity === "CRITICAL" ? "danger" : "warning"}
                              className="text-[9px] mt-0.5"
                            >
                              {t.finding_severity}
                            </Badge>
                          </div>
                        ) : (
                          <span className="text-success text-[10px]">Clean</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {t.risk_scenario_title ? (
                          <span className="text-danger font-medium">{t.risk_scenario_title}</span>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono text-[10px] text-muted-foreground">
                        <div>File: {t.file_path.split("/").pop()}</div>
                        <div>Line: {t.line_number ?? "N/A"}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 7: ARCHITECTURE DRIFT                                                 */}
      {/* ========================================================================= */}
      {!loading && activeTab === "drift" && (
        <Card className="border-border/60 bg-card/70">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <History className="size-4 text-primary" />
                  Architecture Drift & Evolution Inspector
                </h3>
                <p className="text-xs text-muted-foreground">
                  Compares current architecture snapshot with historical baseline of the same repository.
                </p>
              </div>
              {driftData && driftData.baseline_available && (
                <Badge
                  tone={
                    driftData.status === "IMPROVED"
                      ? "success"
                      : driftData.status === "DEGRADED"
                      ? "danger"
                      : "neutral"
                  }
                >
                  {driftData.status}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {driftLoading ? (
              <div className="py-12 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
                <Spinner className="size-6 text-primary" />
                <span>Evaluating snapshot drift...</span>
              </div>
            ) : driftData && !driftData.baseline_available ? (
              <div className="py-8 text-center space-y-4 max-w-lg mx-auto">
                <div className="p-3 rounded-2xl bg-muted/30 border border-border/50 inline-block">
                  <History className="size-8 text-muted-foreground mx-auto" />
                </div>
                <div className="space-y-1">
                  <div className="font-bold text-base text-foreground uppercase tracking-wide">
                    Baseline Unavailable
                  </div>
                  <div className="text-xs text-muted-foreground leading-relaxed">
                    Architecture drift requires at least two comparable scans of the same repository to compute structural delta.
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-background/60 border border-border/50 text-xs text-left space-y-1 font-mono">
                  <div className="text-muted-foreground font-semibold">Current Scan Context:</div>
                  <div className="text-foreground font-bold">{activeScan?.project_name || "Repository"}</div>
                  <div className="text-muted-foreground">Scan ID: {selectedScanId}</div>
                  <div className="text-muted-foreground">
                    Completed: {activeScan?.completed_at ? new Date(activeScan.completed_at).toLocaleString() : "Ready"}
                  </div>
                </div>
                <div className="pt-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setIsScanModalOpen(true)}
                    className="text-xs"
                  >
                    <Play className="size-3.5 mr-1.5" />
                    Run Another Scan to Establish Baseline
                  </Button>
                </div>
              </div>
            ) : driftData ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-background/60 border border-border/40 text-center">
                    <div className="text-[11px] text-muted-foreground">Added Dependencies</div>
                    <div className="text-xl font-bold text-foreground mt-1">{driftData.added_dependencies.length}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-background/60 border border-border/40 text-center">
                    <div className="text-[11px] text-muted-foreground">Removed Dependencies</div>
                    <div className="text-xl font-bold text-success mt-1">{driftData.removed_dependencies.length}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-background/60 border border-border/40 text-center">
                    <div className="text-[11px] text-muted-foreground">New Circular Cycles</div>
                    <div className="text-xl font-bold text-danger mt-1">{driftData.new_circular_cycles.length}</div>
                  </div>
                  <div className="p-3 rounded-lg bg-background/60 border border-border/40 text-center">
                    <div className="text-[11px] text-muted-foreground">Coupling Increases</div>
                    <div className="text-xl font-bold text-warning mt-1">
                      {driftData.increased_coupling_components.length}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* TAB 8: REMEDIATION SIMULATOR                                              */}
      {/* ========================================================================= */}
      {!loading && activeTab === "remediation" && (
        <Card className="border-border/60 bg-card/70">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <Sparkles className="size-4 text-primary" />
                  Remediation Impact Simulator (ESTIMATE)
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Simulate the ripple benefit and posture delta of architectural decoupling or security fixes based on dependency graph topology.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {simComponent && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSelectedBlastComponent(simComponent);
                      setBlastData(null);
                      setBlastError(null);
                      setActiveTab("blast");
                    }}
                    className="text-xs"
                  >
                    <Crosshair className="size-3.5 mr-1.5" />
                    View in Blast Radius
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Prominent Mandatory Disclaimer (STEP 16) */}
            <div className="p-3 rounded-xl border border-primary/30 bg-primary/5 text-xs text-primary/90 flex items-start gap-2.5">
              <Info className="size-4 shrink-0 text-primary mt-0.5" />
              <div className="leading-relaxed">
                <strong>ESTIMATE ONLY:</strong> This simulation estimates architectural impact from the current dependency graph. It does not modify repository code, deployment state, or authoritative security posture. Simulation is based on dependency-graph topology and reachability.
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left Column: Form Controls */}
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-foreground block mb-1">Target Component:</label>
                  <select
                    value={simComponent}
                    onChange={(e) => {
                      const newId = e.target.value;
                      setSimComponent(newId);
                      setSimResult(null);
                      setSimError(null);
                    }}
                    className="w-full h-9 px-3 rounded-lg border border-border/80 bg-background text-xs text-foreground focus:outline-none focus:border-primary"
                  >
                    {components.map((c) => (
                      <option key={c.component_id} value={c.component_id}>
                        {c.name} ({c.component_type})
                      </option>
                    ))}
                  </select>
                  <div className="text-[11px] text-muted-foreground font-mono mt-1 truncate">
                    {components.find((c) => c.component_id === simComponent)?.file_path}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-foreground block mb-1">Proposed Refactoring / Remediation:</label>
                  <Input
                    value={simText}
                    onChange={(e) => setSimText(e.target.value)}
                    placeholder="e.g. Decouple auth and add RBAC control"
                    className="text-xs"
                  />
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    <span className="text-[10px] text-muted-foreground self-center">Presets:</span>
                    <button
                      type="button"
                      onClick={() => setSimText("Decouple module and enforce RBAC authorization boundary")}
                      className="text-[10px] px-2 py-0.5 rounded bg-muted/40 hover:bg-muted/70 text-muted-foreground hover:text-foreground transition-colors border border-border/40"
                    >
                      RBAC Boundary
                    </button>
                    <button
                      type="button"
                      onClick={() => setSimText("Extract interface to break circular dependency cycle")}
                      className="text-[10px] px-2 py-0.5 rounded bg-muted/40 hover:bg-muted/70 text-muted-foreground hover:text-foreground transition-colors border border-border/40"
                    >
                      Break Circular Cycle
                    </button>
                    <button
                      type="button"
                      onClick={() => setSimText("Isolate database access behind repository boundary")}
                      className="text-[10px] px-2 py-0.5 rounded bg-muted/40 hover:bg-muted/70 text-muted-foreground hover:text-foreground transition-colors border border-border/40"
                    >
                      Repository Boundary
                    </button>
                  </div>
                </div>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleRunRemediationSim}
                  disabled={simLoading || !simComponent}
                  className="w-full text-xs"
                >
                  {simLoading ? (
                    <>
                      <Spinner className="size-3.5 mr-1.5" />
                      Simulating Impact...
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-3.5 mr-1.5" />
                      Simulate Architectural Benefit
                    </>
                  )}
                </Button>
              </div>

              {/* Right Column: Simulation Result & State Transition */}
              <div className="space-y-3">
                {/* Loading State */}
                {simLoading && (
                  <div className="p-8 rounded-xl border border-border/60 bg-background/40 text-center space-y-3 h-full flex flex-col items-center justify-center">
                    <Spinner className="size-6 text-primary" />
                    <div className="text-xs font-semibold text-foreground">Evaluating remediation impact...</div>
                    <div className="text-[11px] text-muted-foreground max-w-xs">
                      Traversing reverse callers and security controls for {components.find((c) => c.component_id === simComponent)?.name || simComponent}...
                    </div>
                  </div>
                )}

                {/* Error State */}
                {!simLoading && simError && (
                  <div className="p-6 rounded-xl border border-rose-500/40 bg-rose-500/5 text-center space-y-2.5">
                    <AlertTriangle className="size-6 mx-auto text-rose-400" />
                    <div className="text-xs font-semibold text-rose-300">Unable to calculate simulation</div>
                    <div className="text-[11px] text-muted-foreground">{simError}</div>
                    <Button variant="outline" size="sm" onClick={handleRunRemediationSim} className="text-xs mt-1">
                      <RefreshCw className="size-3 mr-1" />
                      Retry Simulation
                    </Button>
                  </div>
                )}

                {/* Simulation Completed Result (STEPS 13, 14, 15, 17, 18) */}
                {!simLoading && !simError && simResult && (
                  <div className="space-y-3 animate-in fade-in duration-200">
                    {/* Completion & Scope Metadata Banner (STEP 18) */}
                    <div className="p-2.5 rounded-xl border border-primary/30 bg-primary/10 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="size-3.5 text-success shrink-0" />
                        <span className="font-bold text-foreground">Simulation completed</span>
                        <span className="text-[11px] text-muted-foreground">({simResult.simulated_at || "just now"})</span>
                      </div>
                      <div className="text-[10px] text-muted-foreground flex items-center gap-2">
                        <span>Target: <strong className="text-foreground">{simResult.target_component_name}</strong></span>
                        <span>•</span>
                        <span>Scope: <strong className="text-foreground">{activeScan?.project_name || "Active Scan"}</strong></span>
                      </div>
                    </div>

                    {/* Benefit Score Card */}
                    <div className="p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm text-foreground">Estimated Ripple Benefit</span>
                        <div className="flex items-center gap-1.5">
                          <Badge tone="warning" className="text-[10px]">
                            {simResult.metric_label}
                          </Badge>
                          <Badge
                            tone={simResult.remaining_hotspot_status === "HOTSPOT_RESOLVED" ? "success" : "neutral"}
                            className="text-[10px]"
                          >
                            {simResult.remaining_hotspot_status}
                          </Badge>
                        </div>
                      </div>
                      <div className="text-2xl font-bold text-success">
                        +{simResult.estimated_posture_delta} pts
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {simResult.estimated_posture_delta > 0
                          ? "Modeled architectural & security posture improvement based on mitigating downstream reachability of security findings."
                          : "No measurable security posture delta was detected from the current graph topology for this component."}
                      </div>
                    </div>

                    {/* Topology & Reachability Evaluation (STEPS 14 & 15) */}
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-2.5 rounded-lg bg-background/60 border border-border/40 text-center">
                        <div className="text-[10px] text-muted-foreground">Direct Callers</div>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {simResult.direct_dependents_count ?? 0}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-lg bg-background/60 border border-border/40 text-center">
                        <div className="text-[10px] text-muted-foreground">Reachable Closure</div>
                        <div className="text-base font-bold text-cyan-400 mt-0.5">
                          {simResult.affected_components_count}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-lg bg-background/60 border border-border/40 text-center">
                        <div className="text-[10px] text-muted-foreground">Max Depth</div>
                        <div className="text-base font-bold text-foreground mt-0.5">
                          {simResult.max_impact_depth ?? 0} hops
                        </div>
                      </div>
                    </div>

                    {/* Security Correlation Detail (STEP 17) */}
                    <div className="p-3 rounded-xl bg-background/50 border border-border/40 space-y-2 text-xs">
                      <div className="font-semibold text-foreground text-[11px] uppercase tracking-wider">
                        Security Correlation
                      </div>

                      {/* Strengthened Controls */}
                      <div className="space-y-1">
                        <span className="text-muted-foreground text-[11px]">Strengthened Controls:</span>
                        {simResult.strengthened_controls.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {simResult.strengthened_controls.map((ctrl, i) => (
                              <div
                                key={i}
                                className="px-2 py-0.5 rounded bg-background border border-border/60 text-[10px] text-foreground flex items-center gap-1"
                              >
                                <span>{ctrl.control_name}</span>
                                {ctrl.scope && <span className="text-muted-foreground font-mono">({ctrl.scope})</span>}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[11px] text-muted-foreground italic">
                            Security impact: No linked security controls affected in this simulation.
                          </div>
                        )}
                      </div>

                      {/* Mitigated Scenarios */}
                      <div className="space-y-1 pt-1 border-t border-border/30">
                        <span className="text-muted-foreground text-[11px]">Mitigated Risk Scenarios:</span>
                        {simResult.mitigated_risk_scenarios.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {simResult.mitigated_risk_scenarios.map((sc, i) => (
                              <div
                                key={i}
                                className="px-2 py-0.5 rounded bg-background border border-border/60 text-[10px] text-foreground flex items-center gap-1"
                              >
                                <span>{sc.title}</span>
                                {sc.severity && <Badge tone="danger" className="text-[8px] py-0 px-1">{sc.severity}</Badge>}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-[11px] text-muted-foreground italic">
                            Security impact: No linked risk scenarios affected in this simulation.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Disclaimer Footer (STEP 16) */}
                    <div className="text-[10px] text-muted-foreground italic border-t border-border/40 pt-2">
                      {simResult.disclaimer}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* RUN NEW AST SCAN MODAL (PHASE 2)                                          */}
      {/* ========================================================================= */}
      <Modal
        open={isScanModalOpen}
        onClose={() => setIsScanModalOpen(false)}
        title="Run Static AST Architecture Scan"
        size="md"
      >
        <div className="space-y-4 pt-2">
          <p className="text-xs text-muted-foreground leading-relaxed">
            NOVA parses Python and repository source files statically via read-only Abstract Syntax Trees (AST) without executing any code or scripts.
          </p>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-foreground">Target Scope:</label>
            <div className="space-y-2">
              <label className="flex items-start gap-2.5 p-3 rounded-xl border border-border/80 bg-background/50 hover:border-primary/40 cursor-pointer text-xs">
                <input
                  type="radio"
                  name="scan-choice"
                  checked={scanTargetChoice === "selected"}
                  onChange={() => setScanTargetChoice("selected")}
                  className="mt-0.5 text-primary"
                />
                <div>
                  <div className="font-semibold text-foreground">
                    Selected Repository ({activeScan?.project_name || "Active Scope"})
                  </div>
                  <div className="text-muted-foreground text-[11px]">
                    Re-runs AST extraction on the workspace of the currently selected scan.
                  </div>
                </div>
              </label>

              <label className="flex items-start gap-2.5 p-3 rounded-xl border border-border/80 bg-background/50 hover:border-primary/40 cursor-pointer text-xs">
                <input
                  type="radio"
                  name="scan-choice"
                  checked={scanTargetChoice === "local"}
                  onChange={() => setScanTargetChoice("local")}
                  className="mt-0.5 text-primary"
                />
                <div>
                  <div className="font-semibold text-foreground">NOVA Core (Local Repository Root)</div>
                  <div className="text-muted-foreground text-[11px]">
                    Scans all backend and local source code modules to create a fresh architecture snapshot.
                  </div>
                </div>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-border/60">
            <Button variant="outline" size="sm" onClick={() => setIsScanModalOpen(false)} disabled={analyzing}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={handleRunAstScan} disabled={analyzing}>
              {analyzing ? (
                <>
                  <Spinner className="size-3.5 mr-1.5" />
                  Running AST Analysis...
                </>
              ) : (
                <>
                  <Play className="size-3.5 mr-1.5" />
                  Start AST Scan
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========================================================================= */}
      {/* ARCHITECTURE TERMINOLOGY GLOSSARY MODAL (PHASE 28)                        */}
      {/* ========================================================================= */}
      <Modal
        open={isGlossaryModalOpen}
        onClose={() => setIsGlossaryModalOpen(false)}
        title="Architecture Intelligence Terminology Glossary"
        size="lg"
      >
        <div className="space-y-4 pt-2 max-h-[70vh] overflow-y-auto pr-1">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Plain-English reference guide for software architecture metrics, graph topology, and security correlation concepts.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {GLOSSARY_TERMS.map((item, idx) => (
              <div key={idx} className="p-3 rounded-xl border border-border/60 bg-background/60 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-foreground">{item.term}</span>
                  <Badge tone="neutral" className="text-[9px]">
                    {item.category}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{item.definition}</p>
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-3 border-t border-border/60">
            <Button variant="secondary" size="sm" onClick={() => setIsGlossaryModalOpen(false)}>
              Close Glossary
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
