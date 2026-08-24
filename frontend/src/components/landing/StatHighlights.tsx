import { memo } from "react";
import { Activity, Brain, Database, Layers } from "lucide-react";
import { StatTile } from "../ui/StatTile";
import { useKnowledgeDocuments } from "../../hooks/useKnowledge";

/**
 * Top-line NOVA knowledge stats for the Overview / Dashboard landing page.
 * Shows live document, chunk, and processing activity counts.
 */
export const StatHighlights = memo(function StatHighlights() {
  const { data } = useKnowledgeDocuments({ limit: 100 });

  const docs = data?.documents ?? [];
  const totalDocs = data?.total ?? docs.length;
  const indexed = docs.filter((d) => d.status === "indexed").length;
  const processing = docs.filter((d) => d.status === "processing").length;
  const totalChunks = docs.reduce((acc, d) => acc + (d.chunk_count ?? 0), 0);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile label="Knowledge Sources" value={totalDocs} icon={<Database className="size-5" />} />
      <StatTile label="Indexed Documents" value={indexed} icon={<Brain className="size-5" />} />
      <StatTile label="Processing Now" value={processing} icon={<Activity className="size-5" />} />
      <StatTile label="Total Vector Chunks" value={totalChunks} icon={<Layers className="size-5" />} />
    </div>
  );
});
