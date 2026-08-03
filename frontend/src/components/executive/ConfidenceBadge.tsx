import { BadgeCheck } from "lucide-react";
import { Badge } from "../ui/Badge";

/** The existing `kbConfidence` value (Milestone 2's confidence gate,
 * unchanged) rendered as a visible chip instead of being silently
 * captured-but-never-shown. `null` means no knowledge-base retrieval
 * happened at all for this answer (a pure scan-evidence response) — that
 * renders a neutral "verified" chip rather than fabricating a percentage
 * for a score that was never computed. */
export function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) {
    return (
      <Badge tone="neutral" className="gap-1">
        <BadgeCheck className="size-3.5" />
        Verified scan data
      </Badge>
    );
  }

  const percent = Math.round(confidence * 100);
  const tier = confidence >= 0.85 ? "High" : confidence >= 0.6 ? "Medium" : "Low";
  const tone = confidence >= 0.85 ? "success" : confidence >= 0.6 ? "warning" : "danger";

  return (
    <Badge tone={tone} className="gap-1">
      <BadgeCheck className="size-3.5" />
      {percent}% · {tier} confidence
    </Badge>
  );
}
