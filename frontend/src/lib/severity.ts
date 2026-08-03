// NOVA — Confidence & Priority Utilities
// Replaces legacy severity.ts (security scanner severity levels).
// NOVA uses confidence scores (0.0–1.0) and knowledge priority tiers.

export type ConfidenceTier = "VERY_HIGH" | "HIGH" | "MEDIUM" | "LOW" | "UNCERTAIN";

export const CONFIDENCE_ORDER: ConfidenceTier[] = [
  "VERY_HIGH",
  "HIGH",
  "MEDIUM",
  "LOW",
  "UNCERTAIN",
];

export function confidenceTier(score: number | null | undefined): ConfidenceTier {
  if (score == null) return "UNCERTAIN";
  if (score >= 0.9) return "VERY_HIGH";
  if (score >= 0.75) return "HIGH";
  if (score >= 0.5) return "MEDIUM";
  if (score >= 0.25) return "LOW";
  return "UNCERTAIN";
}

interface ConfidenceStyle {
  label: string;
  text: string;
  bg: string;
  ring: string;
  dot: string;
  hex: string;
}

export const CONFIDENCE_STYLES: Record<ConfidenceTier, ConfidenceStyle> = {
  VERY_HIGH: {
    label: "Very High",
    text: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    ring: "ring-emerald-500/25",
    dot: "bg-emerald-500",
    hex: "#10b981",
  },
  HIGH: {
    label: "High",
    text: "text-teal-600 dark:text-teal-400",
    bg: "bg-teal-500/10",
    ring: "ring-teal-500/25",
    dot: "bg-teal-500",
    hex: "#14b8a6",
  },
  MEDIUM: {
    label: "Medium",
    text: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-500/10",
    ring: "ring-amber-500/25",
    dot: "bg-amber-500",
    hex: "#f59e0b",
  },
  LOW: {
    label: "Low",
    text: "text-orange-600 dark:text-orange-400",
    bg: "bg-orange-500/10",
    ring: "ring-orange-500/25",
    dot: "bg-orange-500",
    hex: "#f97316",
  },
  UNCERTAIN: {
    label: "Uncertain",
    text: "text-muted-foreground",
    bg: "bg-muted",
    ring: "ring-border",
    dot: "bg-muted-foreground",
    hex: "#6b7280",
  },
};

export function confidenceStyle(score: number | null | undefined): ConfidenceStyle {
  return CONFIDENCE_STYLES[confidenceTier(score)];
}

// Fixed categorical palette for charts — never cycled or reassigned.
export const CATEGORICAL_PALETTE = [
  { name: "indigo", light: "#4f46e5", dark: "#6366f1" },
  { name: "cyan", light: "#0891b2", dark: "#22d3ee" },
  { name: "emerald", light: "#059669", dark: "#34d399" },
  { name: "violet", light: "#7c3aed", dark: "#a78bfa" },
  { name: "amber", light: "#d97706", dark: "#fbbf24" },
  { name: "rose", light: "#e11d48", dark: "#fb7185" },
  { name: "teal", light: "#0d9488", dark: "#2dd4bf" },
  { name: "blue", light: "#2563eb", dark: "#60a5fa" },
] as const;
