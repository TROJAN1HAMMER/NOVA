import { useMemo, useState } from "react";
import { Network, Search, Sparkles } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { useGraphSnapshot } from "../hooks/useKnowledge";
import type { GraphNode, GraphRelation } from "../types/api";

export default function GraphExplorerPage() {
  const { data: graphData, isLoading } = useGraphSnapshot();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const nodes = useMemo(() => graphData?.nodes ?? [], [graphData]);
  const relations = useMemo(() => graphData?.relations ?? [], [graphData]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const node of nodes) {
      map.set(node.id, node);
    }
    return map;
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
    if (!query.trim()) return nodes;
    const lower = query.toLowerCase();
    return nodes.filter((n) => n.label.toLowerCase().includes(lower) || n.entity_type.toLowerCase().includes(lower));
  }, [nodes, query]);

  const selectedNode = useMemo(() => {
    if (selectedNodeId) {
      const found = nodeMap.get(selectedNodeId);
      if (found) return found;
    }
    return filteredNodes.length > 0 ? filteredNodes[0] : null;
  }, [selectedNodeId, nodeMap, filteredNodes]);

  const selectedTriples = useMemo(() => {
    if (!selectedNode) return [];
    return relations
      .filter((r) => r.source_id === selectedNode.id || r.target_id === selectedNode.id)
      .map((r) => {
        const source = nodeMap.get(r.source_id)?.label ?? r.source_id.slice(0, 8);
        const target = nodeMap.get(r.target_id)?.label ?? r.target_id.slice(0, 8);
        return {
          id: r.id,
          source,
          relation: r.relation_type,
          target,
        };
      });
  }, [selectedNode, relations, nodeMap]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="GraphRAG Entity Explorer"
        description="Interactive symbolic entity-relation knowledge graph for multi-hop retrieval."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Entity-Relation Visualization Canvas"
            description="2D/3D Node-Link Traversal Graph"
            action={
              <div className="flex items-center gap-2">
                <Badge tone="primary">{nodes.length} Active Entities</Badge>
                <Badge tone="neutral">{relations.length} Relations</Badge>
              </div>
            }
          />
          <CardContent className="h-[450px] relative flex items-center justify-center rounded-lg border border-border/40 bg-gradient-to-br from-card via-background to-muted/20 overflow-hidden">
            <div className="absolute inset-0 flex items-center justify-center opacity-30">
              <div className="size-80 rounded-full border border-dashed border-primary/40 animate-spin [animation-duration:40s]" />
              <div className="absolute size-56 rounded-full border border-primary/20" />
            </div>

            {isLoading ? (
              <div className="relative z-10 text-xs text-muted-foreground">Loading knowledge graph snapshot…</div>
            ) : nodes.length === 0 ? (
              <div className="relative z-10 p-6 text-center">
                <EmptyState
                  icon={<Sparkles className="size-8 text-primary" />}
                  title="No entities extracted yet"
                  description="Upload and index documents in Knowledge Base or Source Studio to build the symbolic graph."
                />
              </div>
            ) : (
              <div className="relative z-10 grid grid-cols-2 sm:grid-cols-3 gap-4 max-h-[400px] overflow-y-auto p-4 w-full">
                {filteredNodes.map((entity) => {
                  const isSelected = selectedNode?.id === entity.id;
                  const relCount = nodeRelationCounts.get(entity.id) ?? entity.chunk_count;
                  return (
                    <button
                      key={entity.id}
                      onClick={() => setSelectedNodeId(entity.id)}
                      className={`flex flex-col items-center gap-2 rounded-xl p-4 border backdrop-blur-md transition-all duration-200 ${
                        isSelected
                          ? "border-primary bg-primary/10 shadow-lg shadow-primary/20 scale-105"
                          : "border-border/60 bg-card/90 hover:border-primary/40 hover:scale-102"
                      }`}
                    >
                      <div className="flex size-10 items-center justify-center rounded-full bg-primary/20 text-primary">
                        <Network className="size-5" />
                      </div>
                      <span className="text-xs font-semibold text-foreground text-center line-clamp-2">{entity.label}</span>
                      <Badge tone="neutral" className="text-[10px]">
                        {entity.entity_type} · {relCount} rels
                      </Badge>
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader title="Entity Inspector" description="Entity metadata and relation triples" />
          <CardContent className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search entities…"
                className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>

            {selectedNode ? (
              <div className="space-y-4 rounded-xl border border-border/60 bg-muted/20 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">{selectedNode.label}</span>
                  <Badge tone="primary">{selectedNode.entity_type}</Badge>
                </div>
                <div className="space-y-2 text-xs text-muted-foreground">
                  <div className="flex justify-between border-b border-border/40 pb-1.5">
                    <span>Connected Relations:</span>
                    <span className="font-semibold text-foreground">
                      {nodeRelationCounts.get(selectedNode.id) ?? selectedNode.chunk_count}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1.5">
                    <span>Indexing Pass:</span>
                    <span className="font-semibold text-emerald-400">Dual-Pass GraphRAG</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Confidence Score:</span>
                    <span className="font-semibold text-foreground">{selectedNode.confidence.toFixed(2)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-2">
                  <span className="text-xs font-semibold text-foreground block mb-2">Relation Triples</span>
                  {selectedTriples.length > 0 ? (
                    <div className="space-y-1.5 text-xs max-h-48 overflow-y-auto">
                      {selectedTriples.map((triple) => (
                        <div key={triple.id} className="rounded-md border border-border/40 bg-card p-2 text-muted-foreground">
                          <span className="text-primary font-medium">{triple.source}</span> →{" "}
                          <span className="text-amber-400 font-medium">{triple.relation}</span> →{" "}
                          <span className="text-emerald-400 font-medium">{triple.target}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-md border border-dashed border-border/40 bg-card/50 p-3 text-center text-xs text-muted-foreground">
                      No direct symbolic relation triples recorded.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-muted-foreground">Select an entity node to inspect.</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
