import React, { useMemo, useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Network,
  Search,
  Sparkles,
  Zap,
  RefreshCw,
  ArrowRight,
  SlidersHorizontal,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  RotateCcw,
  Move,
  ChevronRight,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { useGraphSnapshot } from "../hooks/useKnowledge";
import type { GraphNode } from "../types/api";

const ENTITY_TYPE_COLORS: Record<string, { bg: string; stroke: string; glow: string; badge: string }> = {
  RULE: { bg: "#312e81", stroke: "#6366f1", glow: "rgba(99, 102, 241, 0.4)", badge: "#818cf8" },
  ALGORITHM: { bg: "#064e3b", stroke: "#10b981", glow: "rgba(16, 185, 129, 0.4)", badge: "#34d399" },
  POLICY: { bg: "#78350f", stroke: "#f59e0b", glow: "rgba(245, 158, 11, 0.4)", badge: "#fbbf24" },
  ASSET: { bg: "#164e63", stroke: "#06b6d4", glow: "rgba(6, 182, 212, 0.4)", badge: "#22d3ee" },
  STANDARD: { bg: "#1e3a8a", stroke: "#3b82f6", glow: "rgba(59, 130, 246, 0.4)", badge: "#60a5fa" },
  VULNERABILITY: { bg: "#7f1d1d", stroke: "#ef4444", glow: "rgba(239, 68, 68, 0.4)", badge: "#f87171" },
  CONTROL: { bg: "#4c1d95", stroke: "#8b5cf6", glow: "rgba(139, 92, 246, 0.4)", badge: "#a78bfa" },
  DOCUMENT: { bg: "#831843", stroke: "#ec4899", glow: "rgba(236, 72, 153, 0.4)", badge: "#f472b6" },
};

function getEntityTypeStyle(type: string) {
  const upper = type.toUpperCase();
  return (
    ENTITY_TYPE_COLORS[upper] || {
      bg: "#1e293b",
      stroke: "#64748b",
      glow: "rgba(100, 116, 139, 0.3)",
      badge: "#94a3b8",
    }
  );
}

interface CustomPosition {
  x: number;
  y: number;
}

export default function GraphExplorerPage() {
  const { data: graphData, isLoading } = useGraphSnapshot();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("ALL");

  // Interactive Viewport State (Zoom & Pan)
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Custom node positions from user drag
  const [customPositions, setCustomPositions] = useState<Record<string, CustomPosition>>({});
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);

  // Graph Traversal Settings
  const [hopDepth, setHopDepth] = useState<number>(1);
  const [spacingMultiplier, setSpacingMultiplier] = useState<number>(1.2);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  const nodes = useMemo(() => graphData?.nodes ?? [], [graphData]);
  const relations = useMemo(() => graphData?.relations ?? [], [graphData]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const node of nodes) {
      map.set(node.id, node);
    }
    return map;
  }, [nodes]);

  const entityTypes = useMemo(() => {
    const types = new Set<string>();
    for (const node of nodes) {
      if (node.entity_type) types.add(node.entity_type);
    }
    return Array.from(types);
  }, [nodes]);

  const nodeRelationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const rel of relations) {
      counts.set(rel.source_id, (counts.get(rel.source_id) ?? 0) + 1);
      counts.set(rel.target_id, (counts.get(rel.target_id) ?? 0) + 1);
    }
    return counts;
  }, [relations]);

  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      const matchesQuery =
        !query.trim() ||
        n.label.toLowerCase().includes(query.toLowerCase()) ||
        n.entity_type.toLowerCase().includes(query.toLowerCase());
      const matchesType = selectedType === "ALL" || n.entity_type === selectedType;
      return matchesQuery && matchesType;
    });
  }, [nodes, query, selectedType]);

  const selectedNode = useMemo(() => {
    if (selectedNodeId) {
      const found = nodeMap.get(selectedNodeId);
      if (found) return found;
    }
    return filteredNodes.length > 0 ? filteredNodes[0] : nodes.length > 0 ? nodes[0] : null;
  }, [selectedNodeId, nodeMap, filteredNodes, nodes]);

  // Handle selecting a node (with navigation breadcrumbs history)
  const handleSelectNode = useCallback(
    (id: string) => {
      if (id !== selectedNodeId) {
        if (selectedNodeId) {
          setNavigationHistory((prev) => [...prev.slice(-4), selectedNodeId]);
        }
        setSelectedNodeId(id);
      }
    },
    [selectedNodeId]
  );

  // Hop back in history
  const handleHopBack = useCallback(() => {
    if (navigationHistory.length > 0) {
      const previousId = navigationHistory[navigationHistory.length - 1];
      setNavigationHistory((prev) => prev.slice(0, -1));
      setSelectedNodeId(previousId);
    }
  }, [navigationHistory]);

  // Reset View Transforms
  const handleResetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setCustomPositions({});
  }, []);

  // Zoom Controls
  const handleZoomIn = () => setZoom((z) => Math.min(Number((z + 0.25).toFixed(2)), 3.0));
  const handleZoomOut = () => setZoom((z) => Math.max(Number((z - 0.25).toFixed(2)), 0.3));

  // Handle wheel zoom via React's onWheel event (no manual addEventListener)
  const handleWheel = React.useCallback((e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const zoomDelta = e.deltaY < 0 ? 0.12 : -0.12;
    setZoom((prev) => Math.min(Math.max(Number((prev + zoomDelta).toFixed(2)), 0.3), 3.0));
  }, []);

  // Mouse Pan Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only pan if clicking direct SVG background
    if ((e.target as HTMLElement).tagName === "svg" || (e.target as HTMLElement).id === "graph-bg") {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    } else if (draggedNodeId) {
      // Dragging a node in canvas space
      const svg = containerRef.current?.querySelector("svg");
      if (svg) {
        const rect = svg.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        // Convert to viewBox coordinates (viewBox 0 0 900 550)
        const viewBoxX = (mouseX / rect.width) * 900;
        const viewBoxY = (mouseY / rect.height) * 550;
        const canvasX = (viewBoxX - 450 - pan.x) / zoom + 450;
        const canvasY = (viewBoxY - 275 - pan.y) / zoom + 275;

        setCustomPositions((prev) => ({
          ...prev,
          [draggedNodeId]: { x: canvasX, y: canvasY },
        }));
      }
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggedNodeId(null);
  };

  // Derive connected nodes & relations for selected node (Supports 1-Hop and 2-Hop)
  const connectedGraph = useMemo(() => {
    if (!selectedNode) return { hop1Neighbors: [], hop2Neighbors: [], edges: [] };

    // 1-Hop Relations
    const hop1Relations = relations.filter(
      (r) => r.source_id === selectedNode.id || r.target_id === selectedNode.id
    );

    const hop1NeighborIds = new Set<string>();
    const edgesMap = new Map<
      string,
      { id: string; sourceId: string; targetId: string; source: string; target: string; relation: string; isOutgoing: boolean }
    >();

    for (const rel of hop1Relations) {
      const isOutgoing = rel.source_id === selectedNode.id;
      const otherId = isOutgoing ? rel.target_id : rel.source_id;
      hop1NeighborIds.add(otherId);

      const sourceLabel = nodeMap.get(rel.source_id)?.label ?? rel.source_id;
      const targetLabel = nodeMap.get(rel.target_id)?.label ?? rel.target_id;

      edgesMap.set(rel.id, {
        id: rel.id,
        sourceId: rel.source_id,
        targetId: rel.target_id,
        source: sourceLabel,
        target: targetLabel,
        relation: rel.relation_type,
        isOutgoing,
      });
    }

    const hop1Neighbors = Array.from(hop1NeighborIds)
      .map((id) => nodeMap.get(id))
      .filter((n): n is GraphNode => n !== undefined);

    // 2-Hop Relations (optional)
    const hop2NeighborIds = new Set<string>();
    if (hopDepth === 2) {
      for (const h1Id of hop1NeighborIds) {
        const h2Relations = relations.filter(
          (r) =>
            (r.source_id === h1Id || r.target_id === h1Id) &&
            r.source_id !== selectedNode.id &&
            r.target_id !== selectedNode.id
        );

        for (const rel of h2Relations) {
          const isOutgoing = rel.source_id === h1Id;
          const otherId = isOutgoing ? rel.target_id : rel.source_id;

          if (!hop1NeighborIds.has(otherId) && otherId !== selectedNode.id) {
            hop2NeighborIds.add(otherId);

            const sourceLabel = nodeMap.get(rel.source_id)?.label ?? rel.source_id;
            const targetLabel = nodeMap.get(rel.target_id)?.label ?? rel.target_id;

            edgesMap.set(rel.id, {
              id: rel.id,
              sourceId: rel.source_id,
              targetId: rel.target_id,
              source: sourceLabel,
              target: targetLabel,
              relation: rel.relation_type,
              isOutgoing,
            });
          }
        }
      }
    }

    const hop2Neighbors = Array.from(hop2NeighborIds)
      .map((id) => nodeMap.get(id))
      .filter((n): n is GraphNode => n !== undefined);

    return {
      hop1Neighbors,
      hop2Neighbors,
      edges: Array.from(edgesMap.values()),
    };
  }, [selectedNode, relations, nodeMap, hopDepth]);

  // Layout calculation for Graph Viewport (Center 450, 275 inside 900x550 canvas)
  const canvasLayout = useMemo(() => {
    const centerX = 450;
    const centerY = 275;
    const baseRadius1 = 180 * spacingMultiplier;
    const baseRadius2 = 320 * spacingMultiplier;

    const { hop1Neighbors, hop2Neighbors } = connectedGraph;

    // Position 1-Hop Neighbors
    const h1Count = hop1Neighbors.length;
    const positions: Record<
      string,
      { node: GraphNode; x: number; y: number; isHop1: boolean }
    > = {};

    hop1Neighbors.forEach((neighbor, idx) => {
      if (customPositions[neighbor.id]) {
        positions[neighbor.id] = {
          node: neighbor,
          x: customPositions[neighbor.id].x,
          y: customPositions[neighbor.id].y,
          isHop1: true,
        };
      } else {
        const angle = (2 * Math.PI * idx) / Math.max(h1Count, 1) - Math.PI / 2;
        const x = centerX + baseRadius1 * Math.cos(angle);
        const y = centerY + baseRadius1 * Math.sin(angle);
        positions[neighbor.id] = { node: neighbor, x, y, isHop1: true };
      }
    });

    // Position 2-Hop Neighbors
    const h2Count = hop2Neighbors.length;
    hop2Neighbors.forEach((neighbor, idx) => {
      if (customPositions[neighbor.id]) {
        positions[neighbor.id] = {
          node: neighbor,
          x: customPositions[neighbor.id].x,
          y: customPositions[neighbor.id].y,
          isHop1: false,
        };
      } else {
        const angle = (2 * Math.PI * idx) / Math.max(h2Count, 1) - Math.PI / 4;
        const x = centerX + baseRadius2 * Math.cos(angle);
        const y = centerY + baseRadius2 * Math.sin(angle);
        positions[neighbor.id] = { node: neighbor, x, y, isHop1: false };
      }
    });

    // Central Node Position
    const centerPos = customPositions[selectedNode?.id ?? ""] || { x: centerX, y: centerY };

    return { centerX: centerPos.x, centerY: centerPos.y, positions };
  }, [connectedGraph, customPositions, selectedNode, spacingMultiplier]);

  // Fullscreen escape listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="GraphRAG Dynamic Entity Explorer"
        description="Interactive symbolic entity-relation knowledge graph with pan, zoom, multi-hop physics, and node link traversal."
      />

      {/* Top Search & Entity Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-card/70 backdrop-blur-md p-4 rounded-xl border border-border/60 shadow-sm">
        <div className="flex items-center gap-3 flex-1 min-w-[260px]">
          <div className="relative w-full max-w-md">
            <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search entities, rules, algorithms..."
              className="w-full rounded-lg border border-border bg-background pl-9 pr-8 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-2.5 top-2.5 text-xs text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Entity Type Filter Badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setSelectedType("ALL")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
              selectedType === "ALL"
                ? "bg-primary text-primary-foreground shadow-xs"
                : "bg-muted/40 text-muted-foreground hover:bg-muted"
            }`}
          >
            All Types ({nodes.length})
          </button>
          {entityTypes.map((t) => {
            const style = getEntityTypeStyle(t);
            const count = nodes.filter((n) => n.entity_type === t).length;
            return (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${
                  selectedType === t
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "bg-muted/40 text-muted-foreground hover:bg-muted"
                }`}
              >
                <span className="size-2 rounded-full" style={{ backgroundColor: style.stroke }} />
                {t} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Entity Selector Scroll Grid */}
      <Card>
        <CardHeader
          title="Extracted Knowledge Entities"
          description="Click any entity below to focus the interactive dynamic graph visualizer"
          action={
            <div className="flex items-center gap-2">
              <Badge tone="primary">{filteredNodes.length} Visible</Badge>
              <Badge tone="neutral">{relations.length} Relations</Badge>
            </div>
          }
        />
        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <RefreshCw className="size-4 animate-spin text-primary" /> Loading knowledge graph snapshot...
            </div>
          ) : filteredNodes.length === 0 ? (
            <div className="py-8 text-center">
              <EmptyState
                icon={<Sparkles className="size-8 text-primary" />}
                title="No matching entities found"
                description="Try adjusting search terms or selecting 'All Types'."
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-[18rem] overflow-y-auto p-1">
              {filteredNodes.map((entity) => {
                const isSelected = selectedNode?.id === entity.id;
                const relCount = nodeRelationCounts.get(entity.id) ?? entity.chunk_count;
                const typeStyle = getEntityTypeStyle(entity.entity_type);

                return (
                  <motion.button
                    key={entity.id}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleSelectNode(entity.id)}
                    className={`flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border text-center transition-all ${
                      isSelected
                        ? "border-primary bg-primary/15 shadow-md shadow-primary/20 ring-2 ring-primary/50"
                        : "border-border/60 bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
                    }`}
                  >
                    <div
                      className="flex size-7 items-center justify-center rounded-full border shadow-xs"
                      style={{
                        backgroundColor: typeStyle.bg,
                        borderColor: typeStyle.stroke,
                        color: typeStyle.badge,
                      }}
                    >
                      <Network className="size-3.5" />
                    </div>
                    <span className="text-xs font-semibold text-foreground line-clamp-1 w-full truncate">
                      {entity.label}
                    </span>
                    <Badge tone={isSelected ? "primary" : "neutral"} className="text-[9px]">
                      {entity.entity_type} · {relCount} rels
                    </Badge>
                  </motion.button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Main Interactive Visualizer Canvas Section */}
      {selectedNode && (
        <motion.div
          key={selectedNode.id}
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className={`grid grid-cols-1 ${isFullscreen ? "fixed inset-0 z-50 bg-background p-6" : "lg:grid-cols-3"} gap-6`}
        >
          {/* SVG Visualizer Canvas Container */}
          <Card
            className={`${
              isFullscreen ? "h-full flex flex-col justify-between shadow-2xl" : "lg:col-span-2 shadow-xl"
            } border-primary/30 overflow-hidden relative`}
          >
            <CardHeader
              title={`Relational Graph — ${selectedNode.label}`}
              description="Interactive dynamic view. Scroll wheel or use toolbar buttons to Zoom In/Out. Click & drag canvas to Pan."
              action={
                <div className="flex items-center gap-2">
                  {navigationHistory.length > 0 && (
                    <button
                      onClick={handleHopBack}
                      className="px-2.5 py-1 text-xs rounded-lg border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
                    >
                      <ChevronRight className="size-3 rotate-180" /> Hop Back
                    </button>
                  )}
                  <Badge tone="success" className="gap-1 text-xs">
                    <Zap className="size-3" /> Live Dynamic Graph
                  </Badge>
                </div>
              }
            />

            <CardContent className="p-0 flex-1 relative">
              {/* Interactive Zoom/Pan Toolbar HUD */}
              <div className="absolute top-4 left-4 z-30 flex flex-wrap items-center gap-2 bg-slate-900/90 backdrop-blur-md p-2 rounded-xl border border-slate-700/60 shadow-xl text-white">
                {/* Zoom Buttons */}
                <div className="flex items-center gap-1 border-r border-slate-700/80 pr-2">
                  <button
                    onClick={handleZoomIn}
                    title="Zoom In (+)"
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                  >
                    <ZoomIn className="size-4" />
                  </button>
                  <span className="text-xs font-mono font-bold w-12 text-center text-primary-foreground">
                    {Math.round(zoom * 100)}%
                  </span>
                  <button
                    onClick={handleZoomOut}
                    title="Zoom Out (-)"
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
                  >
                    <ZoomOut className="size-4" />
                  </button>
                </div>

                {/* Reset & Fit View */}
                <button
                  onClick={handleResetView}
                  title="Reset Zoom & Pan"
                  className="px-2.5 py-1 text-xs rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 transition-colors"
                >
                  <RotateCcw className="size-3.5" /> Reset View
                </button>
                <button
                  onClick={() => setZoom(1)}
                  title="Fit View (Reset Zoom to 100%)"
                  className="px-2.5 py-1 text-xs rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white flex items-center gap-1 transition-colors"
                >
                  Fit View
                </button>

                {/* Multi-Hop Depth Filter */}
                <div className="flex items-center gap-1 border-l border-slate-700/80 pl-2">
                  <button
                    onClick={() => setHopDepth(1)}
                    className={`px-2 py-0.5 text-xs rounded-md font-medium transition-colors ${
                      hopDepth === 1 ? "bg-primary text-primary-foreground" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    1-Hop
                  </button>
                  <button
                    onClick={() => setHopDepth(2)}
                    className={`px-2 py-0.5 text-xs rounded-md font-medium transition-colors ${
                      hopDepth === 2 ? "bg-primary text-primary-foreground" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    2-Hop Mesh
                  </button>
                </div>

                {/* Spacing Slider */}
                <div className="flex items-center gap-2 border-l border-slate-700/80 pl-2 text-xs">
                  <SlidersHorizontal className="size-3.5 text-slate-400" />
                  <span className="text-[11px] text-slate-300">Spacing:</span>
                  <input
                    type="range"
                    min="0.8"
                    max="2.0"
                    step="0.1"
                    value={spacingMultiplier}
                    onChange={(e) => setSpacingMultiplier(parseFloat(e.target.value))}
                    className="w-16 h-1 accent-primary bg-slate-700 rounded-lg cursor-pointer"
                  />
                </div>

                {/* Fullscreen Toggle */}
                <button
                  onClick={() => setIsFullscreen(!isFullscreen)}
                  title={isFullscreen ? "Exit Fullscreen" : "Fullscreen Graph View"}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors border-l border-slate-700/80 pl-2"
                >
                  {isFullscreen ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
                </button>
              </div>

              {/* Viewport Canvas Element */}
              <div
                ref={containerRef}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                className={`relative w-full ${
                  isFullscreen ? "h-[calc(100vh-140px)]" : "h-[520px]"
                } bg-slate-950 border-t border-slate-800/80 overflow-hidden cursor-${isPanning ? "grabbing" : "grab"}`}
              >
                {/* Background Grid Pattern */}
                <svg
                  id="graph-bg"
                  className="absolute inset-0 size-full opacity-20 pointer-events-auto"
                >
                  <defs>
                    <pattern id="grid-dots" width="40" height="40" patternUnits="userSpaceOnUse">
                      <circle cx="20" cy="20" r="1.5" fill="#38bdf8" />
                      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="1" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid-dots)" />
                </svg>

                {/* Ambient Dynamic Orbit Rings */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
                  <div className="size-[500px] rounded-full border border-dashed border-sky-500/40 animate-spin [animation-duration:45s]" />
                  <div className="absolute size-[320px] rounded-full border border-sky-400/30" />
                  <div className="absolute size-[160px] rounded-full border border-indigo-500/30" />
                </div>

                {/* Interactive SVG Node-Link Canvas */}
                <svg
                  viewBox="0 0 900 550"
                  className="w-full h-full relative z-10 pointer-events-none"
                >
                  <defs>
                    {/* Beam Linear Gradient */}
                    <linearGradient id="beamGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
                      <stop offset="50%" stopColor="#818cf8" stopOpacity="0.9" />
                      <stop offset="100%" stopColor="#34d399" stopOpacity="0.9" />
                    </linearGradient>

                    {/* Arrow Marker Definition */}
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="22"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
                    </marker>

                    {/* Node Glow Filter */}
                    <filter id="glow-heavy" x="-30%" y="-30%" width="160%" height="160%">
                      <feGaussianBlur stdDeviation="5" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>

                  {/* Main Transformed Group (Zoom & Pan applied centered on 450, 275) */}
                  <g
                    transform={`translate(${pan.x + 450}, ${pan.y + 275}) scale(${zoom}) translate(-450, -275)`}
                    className="transition-transform duration-75 ease-out"
                  >
                    {/* Connecting Beams & Relation Pills */}
                    {connectedGraph.edges.map((edge) => {
                      // Determine source and target position coordinates
                      const isCenterSource = edge.sourceId === selectedNode.id;
                      const isCenterTarget = edge.targetId === selectedNode.id;

                      const sourcePos = isCenterSource
                        ? { x: canvasLayout.centerX, y: canvasLayout.centerY }
                        : canvasLayout.positions[edge.sourceId] ?? { x: canvasLayout.centerX, y: canvasLayout.centerY };

                      const targetPos = isCenterTarget
                        ? { x: canvasLayout.centerX, y: canvasLayout.centerY }
                        : canvasLayout.positions[edge.targetId] ?? { x: canvasLayout.centerX, y: canvasLayout.centerY };

                      const midX = (sourcePos.x + targetPos.x) / 2;
                      const midY = (sourcePos.y + targetPos.y) / 2;

                      return (
                        <g key={edge.id} className="pointer-events-auto">
                          {/* Outer Shadow Line */}
                          <line
                            x1={sourcePos.x}
                            y1={sourcePos.y}
                            x2={targetPos.x}
                            y2={targetPos.y}
                            stroke="#0284c7"
                            strokeWidth="4"
                            opacity="0.3"
                          />

                          {/* Animated Dashed Connecting Line */}
                          <line
                            x1={sourcePos.x}
                            y1={sourcePos.y}
                            x2={targetPos.x}
                            y2={targetPos.y}
                            stroke="url(#beamGradient)"
                            strokeWidth="2.5"
                            strokeDasharray="6,4"
                            markerEnd="url(#arrow)"
                            className="animate-[dash_2s_linear_infinite]"
                          />

                          {/* Relation Pill Badge */}
                          <g transform={`translate(${midX}, ${midY})`}>
                            <rect
                              x="-55"
                              y="-12"
                              width="110"
                              height="24"
                              rx="12"
                              fill="#0f172a"
                              stroke="#38bdf8"
                              strokeWidth="1.5"
                              opacity="0.95"
                              className="drop-shadow-lg"
                            />
                            <text
                              x="0"
                              y="4"
                              textAnchor="middle"
                              fill="#7dd3fc"
                              fontSize="10"
                              fontWeight="bold"
                              fontFamily="monospace"
                            >
                              {edge.relation}
                            </text>
                          </g>
                        </g>
                      );
                    })}

                    {/* Satellite Neighbor Nodes */}
                    {Object.values(canvasLayout.positions).map(({ node, x, y, isHop1 }) => {
                      const typeStyle = getEntityTypeStyle(node.entity_type);
                      const isHovered = hoveredNodeId === node.id;

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${x}, ${y})`}
                          className="cursor-pointer pointer-events-auto group"
                          onClick={() => handleSelectNode(node.id)}
                          onMouseEnter={() => setHoveredNodeId(node.id)}
                          onMouseLeave={() => setHoveredNodeId(null)}
                          onMouseDown={(e) => {
                            e.stopPropagation();
                            setDraggedNodeId(node.id);
                          }}
                        >
                          {/* Pulsing Outer Aura on Hover */}
                          <circle
                            cx="0"
                            cy="0"
                            r={isHop1 ? 34 : 26}
                            fill={typeStyle.stroke}
                            opacity={isHovered ? 0.35 : 0.15}
                            className="transition-opacity duration-200"
                          />

                          {/* Outer Circle Container */}
                          <circle
                            cx="0"
                            cy="0"
                            r={isHop1 ? 26 : 20}
                            fill={typeStyle.bg}
                            stroke={typeStyle.stroke}
                            strokeWidth={isHovered ? "3" : "2"}
                            className="transition-all duration-200 drop-shadow-xl"
                            filter="url(#glow-heavy)"
                          />

                          {/* Inner Core Dot */}
                          <circle cx="0" cy="0" r={isHop1 ? 8 : 6} fill={typeStyle.badge} />

                          {/* Node Label Card Pill (Clear Anti-Overlap Background Badge) */}
                          <g transform={`translate(0, ${isHop1 ? 40 : 32})`}>
                            <rect
                              x="-75"
                              y="-10"
                              width="150"
                              height="32"
                              rx="6"
                              fill="#090d16"
                              stroke={typeStyle.stroke}
                              strokeWidth="1"
                              opacity="0.95"
                              className="drop-shadow-md"
                            />
                            <text
                              x="0"
                              y="3"
                              textAnchor="middle"
                              fill="#f8fafc"
                              fontSize="11"
                              fontWeight="700"
                              className="group-hover:fill-sky-400 transition-colors"
                            >
                              {node.label.length > 22 ? node.label.slice(0, 20) + "..." : node.label}
                            </text>
                            <text
                              x="0"
                              y="16"
                              textAnchor="middle"
                              fill={typeStyle.badge}
                              fontSize="9"
                              fontWeight="600"
                            >
                              {node.entity_type} {isHop1 ? "" : "(2-Hop)"}
                            </text>
                          </g>
                        </g>
                      );
                    })}

                    {/* Central Target Node (Selected Focus Node) */}
                    <g
                      transform={`translate(${canvasLayout.centerX}, ${canvasLayout.centerY})`}
                      className="pointer-events-auto cursor-pointer"
                      filter="url(#glow-heavy)"
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        if (selectedNode) setDraggedNodeId(selectedNode.id);
                      }}
                    >
                      {/* Pulse Ring */}
                      <circle
                        cx="0"
                        cy="0"
                        r="55"
                        fill="#6366f1"
                        opacity="0.25"
                        className="animate-ping [animation-duration:3s]"
                      />
                      <circle cx="0" cy="0" r="44" fill="#1e1b4b" stroke="#818cf8" strokeWidth="4" />
                      <circle cx="0" cy="0" r="14" fill="#a5b4fc" />

                      {/* Central Label Pill */}
                      <g transform="translate(0, 62)">
                        <rect
                          x="-100"
                          y="-14"
                          width="200"
                          height="40"
                          rx="8"
                          fill="#0f172a"
                          stroke="#818cf8"
                          strokeWidth="2"
                          opacity="0.98"
                          className="drop-shadow-2xl"
                        />
                        <text
                          x="0"
                          y="4"
                          textAnchor="middle"
                          fill="#e0e7ff"
                          fontSize="13"
                          fontWeight="bold"
                        >
                          {selectedNode.label.length > 26
                            ? selectedNode.label.slice(0, 24) + "..."
                            : selectedNode.label}
                        </text>
                        <text
                          x="0"
                          y="19"
                          textAnchor="middle"
                          fill="#818cf8"
                          fontSize="10"
                          fontWeight="600"
                        >
                          Target Focus Entity
                        </text>
                      </g>
                    </g>
                  </g>
                </svg>

                {/* Helper Controls Guidance Overlay */}
                <div className="absolute bottom-3 left-3 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/60 text-[11px] text-slate-300 flex items-center gap-2 shadow-lg">
                  <Move className="size-3.5 text-sky-400" /> Pan: Click & Drag Canvas | Zoom: Scroll Wheel / Buttons
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Right Panel: Selected Entity Metadata & Triple Inspector */}
          {!isFullscreen && (
            <Card className="border-border/60">
            <CardHeader
              title="Entity Metadata & Triples"
              description={`Relation connections for ${selectedNode.label}`}
            />
            <CardContent className="space-y-4">
              <div className="p-3.5 rounded-xl bg-muted/30 border border-border/50 space-y-2.5 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Entity Type:</span>
                  <Badge
                    tone="primary"
                    style={{
                      backgroundColor: getEntityTypeStyle(selectedNode.entity_type).bg,
                      color: getEntityTypeStyle(selectedNode.entity_type).badge,
                      borderColor: getEntityTypeStyle(selectedNode.entity_type).stroke,
                    }}
                  >
                    {selectedNode.entity_type}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">1-Hop Relations:</span>
                  <span className="font-semibold text-foreground font-mono">
                    {connectedGraph.hop1Neighbors.length} Direct Neighbors
                  </span>
                </div>
                {hopDepth === 2 && (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">2-Hop Mesh:</span>
                    <span className="font-semibold text-sky-400 font-mono">
                      +{connectedGraph.hop2Neighbors.length} Mesh Nodes
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">GraphRAG Indexing:</span>
                  <span className="font-semibold text-emerald-400 font-mono">Dual-Pass Symbolic</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Confidence Score:</span>
                  <span className="font-semibold text-foreground font-mono">
                    {selectedNode.confidence.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Active Triples List */}
              <div>
                <span className="text-xs font-semibold text-foreground block mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <SlidersHorizontal className="size-3.5 text-primary" /> Active Triples (
                    {connectedGraph.edges.length})
                  </span>
                  <Badge tone="neutral" className="text-[10px]">
                    {hopDepth === 1 ? "1-Hop Mode" : "2-Hop Mesh"}
                  </Badge>
                </span>

                {connectedGraph.edges.length > 0 ? (
                  <div className="space-y-2 max-h-[18rem] overflow-y-auto pr-1">
                    {connectedGraph.edges.map((edge) => (
                      <motion.div
                        key={edge.id}
                        initial={{ opacity: 0, x: 5 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="p-2.5 rounded-lg border border-border/40 bg-card text-xs font-mono space-y-1.5 hover:border-primary/50 transition-colors"
                      >
                        <div className="flex items-center gap-1.5 text-[11px] overflow-hidden">
                          <span className="text-sky-400 font-semibold truncate max-w-[120px]" title={edge.source}>
                            {edge.source}
                          </span>
                          <ArrowRight className="size-3 text-muted-foreground shrink-0" />
                          <span className="text-emerald-400 font-semibold truncate max-w-[120px]" title={edge.target}>
                            {edge.target}
                          </span>
                        </div>
                        <div className="text-[10px] text-amber-400 font-semibold bg-amber-500/10 px-2 py-0.5 rounded w-fit border border-amber-500/20">
                          {edge.relation}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-dashed border-border/40 text-center text-xs text-muted-foreground">
                    No active relation triples found for this node.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
          )}
        </motion.div>
      )}
    </div>
  );
}
