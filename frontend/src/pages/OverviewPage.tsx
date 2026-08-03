import { Hero } from "../components/landing/Hero";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { StatHighlights } from "../components/landing/StatHighlights";
import { SystemPillars } from "../components/landing/SystemPillars";

export default function OverviewPage() {
  return (
    <div className="space-y-10">
      <Hero />

      <RevealSection className="space-y-3">
        <RevealItem>
          <h2 className="text-lg font-semibold tracking-tight text-foreground">NOVA at a glance</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            NOVA transforms your enterprise knowledge into a precision retrieval engine — ingesting documents,
            codebases, and web sources into a unified vector corpus and symbolic knowledge graph, then delivering
            grounded, explainable answers through the AEKOF five-stage evidence cascade with full confidence calibration.
          </p>
        </RevealItem>
        <RevealItem>
          <StatHighlights />
        </RevealItem>
      </RevealSection>

      <RevealSection className="space-y-3">
        <RevealItem>
          <h2 className="text-lg font-semibold tracking-tight text-foreground">How it fits together</h2>
        </RevealItem>
        <RevealItem>
          <SystemPillars />
        </RevealItem>
      </RevealSection>
    </div>
  );
}
