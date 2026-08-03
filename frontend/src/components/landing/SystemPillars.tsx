import { memo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, GitMerge, ShieldAlert, Sparkles, type LucideIcon } from "lucide-react";
import { Card, CardContent } from "../ui/Card";

interface Pillar {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Where "Learn more" goes — each pillar's own dedicated page, not the generic
   *  architecture explorer (that link already exists elsewhere on this page). */
  to: string;
}

const PILLARS: Pillar[] = [
  {
    icon: GitMerge,
    title: "Scan Pipeline",
    description:
      "Every push fans out across 6 parallel scanners — Semgrep, AST-Grep, Joern, dependency analysis, secrets detection, and configuration scanning — then merges into one de-duplicated finding set.",
    to: "/scans",
  },
  {
    icon: Sparkles,
    title: "AI Explanation Layer",
    description:
      "An LLM-backed layer turns raw findings into plain-English root-cause explanations, concrete remediation snippets, and an executive-ready narrative summary.",
    to: "/assistant",
  },
  {
    icon: ShieldAlert,
    title: "Banking Risk Score",
    description:
      "Findings are weighted by severity, exploitability, and asset criticality into a single 0-100 Banking Risk Score you can track per repository over time.",
    to: "/risk",
  },
];

/** Three compact callout cards summarizing the core system pillars, each linking through to
 *  its own dedicated page (Scan Queue, AI Assistant, Risk Dashboard). */
export const SystemPillars = memo(function SystemPillars() {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {PILLARS.map(({ icon: Icon, title, description, to }) => (
        <Card key={title} interactive>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                <Icon className="size-4" />
              </span>
              <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{description}</p>
            <button
              type="button"
              onClick={() => navigate(to)}
              className="mt-4 inline-flex items-center gap-1 rounded-sm text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              Learn more
              <ArrowRight className="size-3.5" />
            </button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
});
