import { Brain, Layers, Clock, UserCheck, ShieldCheck } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

export default function MemoryPage() {
  const memoryLayers = [
    {
      level: "Layer 1",
      title: "Short-Term Conversational Memory",
      icon: Clock,
      description: "Active 10-turn conversation sliding window buffer per user session.",
      status: "Active (10/10 turns)",
      tone: "success" as const,
    },
    {
      level: "Layer 2",
      title: "Long-Term Semantic Memory",
      icon: Brain,
      description: "Celery async worker summarizes older turns into session context vectors.",
      status: "Compressed & Indexed",
      tone: "primary" as const,
    },
    {
      level: "Layer 3",
      title: "User Preference Memory",
      icon: UserCheck,
      description: "User role, department parameters, and language preference settings.",
      status: "Synchronized",
      tone: "neutral" as const,
    },
    {
      level: "Layer 4",
      title: "Task Execution Memory",
      icon: Layers,
      description: "Multi-turn agent execution plan and step state tracker.",
      status: "Idle",
      tone: "neutral" as const,
    },
    {
      level: "Layer 5",
      title: "Organizational Axiom Memory",
      icon: ShieldCheck,
      description: "High-frequency domain concepts & active Stage 0 FAQ rules.",
      status: "Active (0ms Match)",
      tone: "success" as const,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hierarchical 5-Layer Enterprise Memory Engine"
        description="Inspect short-term turn buffers, long-term semantic context summaries, and organizational axiom memory."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {memoryLayers.map((layer) => {
          const Icon = layer.icon;
          return (
            <Card key={layer.level} className="relative overflow-hidden border-border/60 hover:border-primary/40 transition-colors">
              <CardHeader
                title={layer.title}
                description={layer.level}
                action={<Badge tone={layer.tone}>{layer.status}</Badge>}
              />
              <CardContent>
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="size-4 text-primary" />
                  <span className="text-xs font-semibold text-foreground">{layer.level}</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{layer.description}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
