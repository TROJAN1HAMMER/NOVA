import { useCallback } from "react";
import { LandingBackground } from "../components/public-landing/LandingBackground";
import { LandingNavbar } from "../components/public-landing/LandingNavbar";
import { LandingHeroSection } from "../components/public-landing/LandingHeroSection";
import { TrustStripSection } from "../components/public-landing/TrustStripSection";
import { ArchitectureShiftSection } from "../components/public-landing/ArchitectureShiftSection";
import { CoreCapabilitiesSection } from "../components/public-landing/CoreCapabilitiesSection";
import { TrustDecisionSection } from "../components/public-landing/TrustDecisionSection";
import { ContradictionDemoSection } from "../components/public-landing/ContradictionDemoSection";
import { TemporalPostureSection } from "../components/public-landing/TemporalPostureSection";
import { SecurityArchitectureSection } from "../components/public-landing/SecurityArchitectureSection";
import { FinancialEnterpriseSection } from "../components/public-landing/FinancialEnterpriseSection";
import { TechnicalFoundationSection } from "../components/public-landing/TechnicalFoundationSection";
import { FinalCTASection } from "../components/public-landing/FinalCTASection";
import { LandingFooter } from "../components/public-landing/LandingFooter";

/**
 * Public Landing Page (`/`).
 * Complete Enterprise Security Intelligence redesign.
 * Features deep navy/black palette, interactive NOVA reasoning visual,
 * architecture shift breakdown, 6 core capabilities, 8D Trust vs Safety Policy,
 * illustrative contradiction inspector, temporal posture sparklines, and tech foundation.
 */
export default function LandingPage() {
  const handleScrollToSection = useCallback((sectionId: string) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  return (
    <div className="relative min-h-screen w-full bg-[#07090e] font-sans text-slate-100 selection:bg-sky-500/30 selection:text-sky-200">
      {/* Ambient Animated Dark Background */}
      <LandingBackground />

      {/* Enterprise Header Navbar */}
      <LandingNavbar onScrollToSection={handleScrollToSection} />

      {/* Main Content Sections */}
      <main className="relative z-10">
        <LandingHeroSection onExploreClick={() => handleScrollToSection("architecture-shift")} />
        <TrustStripSection />
        <ArchitectureShiftSection />
        <CoreCapabilitiesSection />
        <TrustDecisionSection />
        <ContradictionDemoSection />
        <TemporalPostureSection />
        <SecurityArchitectureSection />
        <FinancialEnterpriseSection />
        <TechnicalFoundationSection />
        <FinalCTASection />
      </main>

      {/* Enterprise Footer */}
      <LandingFooter />
    </div>
  );
}
