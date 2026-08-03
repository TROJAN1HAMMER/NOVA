import { useState } from "react";
import { Network, Search } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface EntityNode {
  id: string;
  name: string;
  type: "ORG" | "POLICY" | "CONCEPT" | "PRODUCT";
  relations: number;
}

const SAMPLE_ENTITIES: EntityNode[] = [
  { id: "e1", name: "AEKOF Architecture", type: "CONCEPT", relations: 12 },
  { id: "e2", name: "Isotonic Calibrator", type: "CONCEPT", relations: 8 },
  { id: "e3", name: "HDBSCAN Failure Clusterer", type: "CONCEPT", relations: 6 },
  { id: "e4", name: "Exa Web Fallback", type: "PRODUCT", relations: 5 },
  { id: "e5", name: "PostgreSQL pgvector", type: "PRODUCT", relations: 14 },
  { id: "e6", name: "GraphRAG Entity Traversal", type: "POLICY", relations: 9 },
];

export default function GraphExplorerPage() {
  const [selectedEntity, setSelectedEntity] = useState<EntityNode | null>(SAMPLE_ENTITIES[0]);
  const [query, setQuery] = useState("");

  const filtered = SAMPLE_ENTITIES.filter((e) => e.name.toLowerCase().includes(query.toLowerCase()));

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
                <Badge tone="primary">6 Active Entities</Badge>
                <Badge tone="neutral">18 Relations</Badge>
              </div>
            }
          />
          <CardContent className="h-[450px] relative flex items-center justify-center rounded-lg border border-border/40 bg-gradient-to-br from-card via-background to-muted/20 overflow-hidden">
            <div className="absolute inset-0 flex items-center justify-center opacity-30">
              <div className="size-80 rounded-full border border-dashed border-primary/40 animate-spin [animation-duration:40s]" />
              <div className="absolute size-56 rounded-full border border-primary/20" />
            </div>

            <div className="relative z-10 grid grid-cols-3 gap-8">
              {filtered.map((entity) => {
                const isSelected = selectedEntity?.id === entity.id;
                return (
                  <button
                    key={entity.id}
                    onClick={() => setSelectedEntity(entity)}
                    className={`flex flex-col items-center gap-2 rounded-xl p-4 border backdrop-blur-md transition-all duration-200 ${
                      isSelected
                        ? "border-primary bg-primary/10 shadow-lg shadow-primary/20 scale-105"
                        : "border-border/60 bg-card/90 hover:border-primary/40 hover:scale-102"
                    }`}
                  >
                    <div className="flex size-10 items-center justify-center rounded-full bg-primary/20 text-primary">
                      <Network className="size-5" />
                    </div>
                    <span className="text-xs font-semibold text-foreground text-center">{entity.name}</span>
                    <Badge tone="neutral" className="text-[10px]">
                      {entity.type} · {entity.relations} rels
                    </Badge>
                  </button>
                );
              })}
            </div>
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

            {selectedEntity ? (
              <div className="space-y-4 rounded-xl border border-border/60 bg-muted/20 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">{selectedEntity.name}</span>
                  <Badge tone="primary">{selectedEntity.type}</Badge>
                </div>
                <div className="space-y-2 text-xs text-muted-foreground">
                  <div className="flex justify-between border-b border-border/40 pb-1.5">
                    <span>Connected Relations:</span>
                    <span className="font-semibold text-foreground">{selectedEntity.relations}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-1.5">
                    <span>Indexing Pass:</span>
                    <span className="font-semibold text-emerald-400">Dual-Pass GraphRAG</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Traversal Weight:</span>
                    <span className="font-semibold text-foreground">0.92</span>
                  </div>
                </div>

                <div className="mt-4 pt-2">
                  <span className="text-xs font-semibold text-foreground block mb-2">Relation Triples</span>
                  <div className="space-y-1.5 text-xs">
                    <div className="rounded-md border border-border/40 bg-card p-2 text-muted-foreground">
                      <span className="text-primary font-medium">{selectedEntity.name}</span> → <span className="text-amber-400 font-medium">IMPLEMENTS</span> → <span className="text-emerald-400 font-medium">AEKOF Standard</span>
                    </div>
                    <div className="rounded-md border border-border/40 bg-card p-2 text-muted-foreground">
                      <span className="text-primary font-medium">{selectedEntity.name}</span> → <span className="text-amber-400 font-medium">FUSES_WITH</span> → <span className="text-cyan-400 font-medium">Dense Vector Store</span>
                    </div>
                  </div>
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
