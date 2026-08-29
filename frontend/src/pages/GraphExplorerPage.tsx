import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Network,
  Search,
  Sparkles,
  Zap,
  GitBranch,
  RefreshCw,
  ArrowRight,
  SlidersHorizontal,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { useGraphSnapshot } from "../hooks/useKnowledge";
import type { GraphNode } from "../types/api";

export default function GraphExplorerPage() {
  const { data: graphData, isLoading } = useGraphSnapshot();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string>("ALL");

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

  // Derive connected nodes & relations for the selected node
  const connectedGraph = useMemo(() => {
    if (!selectedNode) return { neighbors: [], edges: [] };

    const matchingRelations = relations.filter(
      (r) => r.source_id === selectedNode.id || r.target_id === selectedNode.id
    );

    const neighborIds = new Set<string>();
    const edges: { id: string; source: string; target: string; relation: string; isOutgoing: boolean }[] = [];

    for (const rel of matchingRelations) {
      const isOutgoing = rel.source_id === selectedNode.id;
      const otherId = isOutgoing ? rel.target_id : rel.source_id;
      neighborIds.add(otherId);

      const sourceLabel = nodeMap.get(rel.source_id)?.label ?? rel.source_id;
      const targetLabel = nodeMap.get(rel.target_id)?.label ?? rel.target_id;

      edges.push({
        id: rel.id,
        source: sourceLabel,
        target: targetLabel,
        relation: rel.relation_type,
        isOutgoing,
      });
    }

    const neighbors = Array.from(neighborIds)
      .map((id) => nodeMap.get(id))
      .filter((n): n is GraphNode => n !== undefined);

    return { neighbors, edges };
  }, [selectedNode, relations, nodeMap]);

  // Layout positions for graph visualizer canvas
  const canvasLayout = useMemo(() => {
    const centerX = 350;
    const centerY = 200;
    const radius = 170;

    const neighbors = connectedGraph.neighbors;
    const count = neighbors.length;

    const neighborPositions = neighbors.map((neighbor, idx) => {
      const angle = (2 * Math.PI * idx) / Math.max(count, 1) - Math.PI / 2;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      const edge = connectedGraph.edges.find(
        (e) => e.source === neighbor.label || e.target === neighbor.label
      );

      return {
        node: neighbor,
        x,
        y,
        relation: edge?.relation ?? "CONNECTED_TO",
        isOutgoing: edge?.isOutgoing ?? true,
      };
    });

    return { centerX, centerY, neighborPositions };
  }, [connectedGraph]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="GraphRAG Entity Explorer"
        description="Interactive symbolic entity-relation knowledge graph with dynamic node-link traversal."
      />

      {/* Top Filter & Metrics Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-card/60 backdrop-blur-md p-4 rounded-xl border border-border/60">
        <div className="flex items-center gap-3 flex-1 min-w-[240px]">
          <div className="relative w-full max-w-md">
            <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search entities & relations..."
              className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
        </div>

        {/* Entity Type Filter Badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setSelectedType("ALL")}
            className={`px-3 py-1 rounded-full text-xs transition-all ${
              selectedType === "ALL"
                ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                : "bg-muted/40 text-muted-foreground hover:bg-muted"
            }`}
          >
            All Types ({nodes.length})
          </button>
          {entityTypes.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`px-3 py-1 rounded-full text-xs transition-all ${
                selectedType === t
                  ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                  : "bg-muted/40 text-muted-foreground hover:bg-muted"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Entity Selection Cards Grid */}
      <Card>
        <CardHeader
          title="Extracted Knowledge Entities"
          description="Select any entity to generate its interactive relational graph below"
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
                description="Try clearing search filters or uploading new documents in Knowledge Base."
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-[16rem] overflow-y-auto p-1">
              {filteredNodes.map((entity) => {
                const isSelected = selectedNode?.id === entity.id;
                const relCount = nodeRelationCounts.get(entity.id) ?? entity.chunk_count;
                return (
                  <motion.button
                    key={entity.id}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => setSelectedNodeId(entity.id)}
                    className={`flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border text-center transition-all ${
                      isSelected
                        ? "border-primary bg-primary/15 shadow-md shadow-primary/20 ring-2 ring-primary/40"
                        : "border-border/60 bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
                    }`}
                  >
                    <div
                      className={`flex size-8 items-center justify-center rounded-full transition-colors ${
                        isSelected ? "bg-primary text-primary-foreground" : "bg-primary/20 text-primary"
                      }`}
                    >
                      <Network className="size-4" />
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

      {/* Interactive Relational Graph Visualizer Canvas (Rendered Directly Below Selection Card) */}
      {selectedNode && (
        <motion.div
          key={selectedNode.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
        >
          {/* Main Visualizer SVG Canvas */}
          <Card className="lg:col-span-2 border-primary/30 shadow-xl overflow-hidden">
            <CardHeader
              title={`Relational Graph — ${selectedNode.label}`}
              description="Interactive node-link traversal. Click satellite nodes to hop multi-hop."
              action={
                <Badge tone="success" className="gap-1 text-xs">
                  <Zap className="size-3" /> Live Dynamic Graph
                </Badge>
              }
            />
            <CardContent className="p-0">
              <div className="relative w-full h-[420px] bg-gradient-to-br from-card via-background to-muted/20 border-t border-border/40 overflow-hidden flex items-center justify-center">
                {/* Background Grid Pattern */}
                <svg className="absolute inset-0 size-full opacity-15 pointer-events-none">
                  <defs>
                    <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                      <path d="M 30 0 L 0 0 0 30" fill="none" stroke="currentColor" strokeWidth="0.5" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid)" />
                </svg>

                {/* Ambient Radial Pulsing Rings */}
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-25">
                  <div className="size-96 rounded-full border border-dashed border-primary/40 animate-spin [animation-duration:35s]" />
                  <div className="absolute size-64 rounded-full border border-primary/30 animate-ping [animation-duration:6s]" />
                  <div className="absolute size-40 rounded-full border border-primary/20" />
                </div>

                {/* Interactive SVG Node-Link Canvas */}
                <svg viewBox="0 0 700 400" className="w-full h-full relative z-10">
                  <defs>
                    {/* Animated Beam Gradient */}
                    <linearGradient id="beamGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                      <stop offset="50%" stopColor="#10b981" stopOpacity="0.9" />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.8" />
                    </linearGradient>

                    {/* Glow Filter */}
                    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                      <feGaussianBlur stdDeviation="3" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>

                  {/* Connecting Beams & Relation Labels */}
                  {canvasLayout.neighborPositions.map((pos, idx) => (
                    <g key={idx}>
                      {/* Animated Dashed Connecting Line */}
                      <line
                        x1={canvasLayout.centerX}
                        y1={canvasLayout.centerY}
                        x2={pos.x}
                        y2={pos.y}
                        stroke="url(#beamGradient)"
                        strokeWidth="2.5"
                        strokeDasharray="6,4"
                        className="animate-[dash_1.5s_linear_infinite]"
                      />

                      {/* Relation Label Pill */}
                      <g transform={`translate(${(canvasLayout.centerX + pos.x) / 2}, ${(canvasLayout.centerY + pos.y) / 2})`}>
                        <rect
                          x="-45"
                          y="-10"
                          width="90"
                          height="20"
                          rx="10"
                          fill="#0f172a"
                          stroke="#3b82f6"
                          strokeWidth="1"
                          opacity="0.9"
                        />
                        <text
                          x="0"
                          y="3"
                          textAnchor="middle"
                          fill="#60a5fa"
                          fontSize="9"
                          fontWeight="bold"
                          fontFamily="monospace"
                        >
                          {pos.relation}
                        </text>
                      </g>
                    </g>
                  ))}

                  {/* Satellite Connected Nodes */}
                  {canvasLayout.neighborPositions.map((pos, idx) => (
                    <g
                      key={idx}
                      className="cursor-pointer group"
                      onClick={() => setSelectedNodeId(pos.node.id)}
                    >
                      {/* Hover Halo */}
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r="28"
                        fill="#3b82f6"
                        opacity="0.15"
                        className="group-hover:opacity-40 transition-opacity"
                      />
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r="20"
                        fill="#1e293b"
                        stroke="#3b82f6"
                        strokeWidth="2"
                        className="group-hover:stroke-emerald-400 group-hover:scale-110 transition-all"
                        filter="url(#glow)"
                      />

                      {/* Node Type Dot */}
                      <circle cx={pos.x} cy={pos.y} r="6" fill="#10b981" />

                      {/* Label below node */}
                      <text
                        x={pos.x}
                        y={pos.y + 34}
                        textAnchor="middle"
                        fill="#f8fafc"
                        fontSize="10"
                        fontWeight="600"
                        className="group-hover:fill-emerald-400 transition-colors"
                      >
                        {pos.node.label.length > 20 ? pos.node.label.slice(0, 18) + "..." : pos.node.label}
                      </text>
                      <text
                        x={pos.x}
                        y={pos.y + 45}
                        textAnchor="middle"
                        fill="#94a3b8"
                        fontSize="8"
                      >
                        {pos.node.entity_type}
                      </text>
                    </g>
                  ))}

                  {/* Central Node (Selected Entity) */}
                  <g filter="url(#glow)">
                    {/* Glowing Aura Ring */}
                    <circle
                      cx={canvasLayout.centerX}
                      cy={canvasLayout.centerY}
                      r="42"
                      fill="#3b82f6"
                      opacity="0.25"
                      className="animate-pulse"
                    />
                    <circle
                      cx={canvasLayout.centerX}
                      cy={canvasLayout.centerY}
                      r="32"
                      fill="#1e1b4b"
                      stroke="#6366f1"
                      strokeWidth="3"
                    />
                    <circle
                      cx={canvasLayout.centerX}
                      cy={canvasLayout.centerY}
                      r="10"
                      fill="#818cf8"
                    />

                    <text
                      x={canvasLayout.centerX}
                      y={canvasLayout.centerY + 48}
                      textAnchor="middle"
                      fill="#818cf8"
                      fontSize="12"
                      fontWeight="bold"
                    >
                      {selectedNode.label}
                    </text>
                    <text
                      x={canvasLayout.centerX}
                      y={canvasLayout.centerY + 62}
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize="9"
                      fontWeight="500"
                    >
                      Target Focus Node
                    </text>
                  </g>
                </svg>

                {/* Instruction Overlay */}
                <div className="absolute bottom-3 left-3 bg-card/80 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-border/40 text-[10px] text-muted-foreground flex items-center gap-2">
                  <GitBranch className="size-3 text-primary" /> Click any surrounding node to traverse graph multi-hop
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Right Panel: Detailed Entity Metadata & Triple List */}
          <Card className="border-border/60">
            <CardHeader title="Entity Metadata & Triples" description={`Relation connections for ${selectedNode.label}`} />
            <CardContent className="space-y-4">
              <div className="p-3 rounded-lg bg-muted/30 border border-border/40 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Entity Type:</span>
                  <Badge tone="primary">{selectedNode.entity_type}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Direct Relations:</span>
                  <span className="font-semibold text-foreground font-mono">
                    {connectedGraph.neighbors.length} Neighbors
                  </span>
                </div>
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

              <div>
                <span className="text-xs font-semibold text-foreground block mb-2 flex items-center gap-1.5">
                  <SlidersHorizontal className="size-3.5 text-primary" /> Active Relation Triples ({connectedGraph.edges.length})
                </span>
                {connectedGraph.edges.length > 0 ? (
                  <div className="space-y-2 max-h-[16rem] overflow-y-auto pr-1">
                    {connectedGraph.edges.map((edge) => (
                      <motion.div
                        key={edge.id}
                        initial={{ opacity: 0, x: 5 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="p-2.5 rounded-lg border border-border/40 bg-card text-xs font-mono space-y-1"
                      >
                        <div className="flex items-center gap-1.5 text-[11px]">
                          <span className="text-primary font-semibold truncate">{edge.source}</span>
                          <ArrowRight className="size-3 text-muted-foreground shrink-0" />
                          <span className="text-emerald-400 font-semibold truncate">{edge.target}</span>
                        </div>
                        <div className="text-[10px] text-amber-400 font-semibold bg-amber-500/10 px-2 py-0.5 rounded w-fit">
                          {edge.relation}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-dashed border-border/40 text-center text-xs text-muted-foreground">
                    No active relation triples for this node.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
