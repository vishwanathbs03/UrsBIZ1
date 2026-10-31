import { HeroSection } from "@/components/marketing/HeroSection";
import { TrustStripSection } from "@/components/marketing/TrustStripSection";
import { OneLayerSection } from "@/components/marketing/OneLayerSection";
import { AiAssistantSpotlightSection } from "@/components/marketing/AiAssistantSpotlightSection";
import { BiMetricsSection } from "@/components/marketing/BiMetricsSection";
import { PredictiveSection } from "@/components/marketing/PredictiveSection";
import { SchemesSection } from "@/components/marketing/SchemesSection";
import { ActionBoardSection } from "@/components/marketing/ActionBoardSection";
import { HowItWorksSection } from "@/components/marketing/HowItWorksSection";
import { FinalCtaSection } from "@/components/marketing/FinalCtaSection";

export default function HomePage() {
  return (
    <>
      {/* 1. Dark Enterprise Hero with Console Preview */}
      <HeroSection />

      {/* 2. Value / Trust Strip */}
      <TrustStripSection />

      {/* 3. "Everything you need to understand your business" (01 Understand, 02 Discover, 03 Predict, 04 Act) */}
      <OneLayerSection />

      {/* 4. Flagship AI Assistant Grounded Spotlight */}
      <AiAssistantSpotlightSection />

      {/* 5. Business Intelligence Snapshot */}
      <BiMetricsSection />

      {/* 6. Predictive Forward Modeling */}
      <PredictiveSection />

      {/* 7. Government Schemes Discovery Engine */}
      <SchemesSection />

      {/* 8. Action Board & Execution */}
      <ActionBoardSection />

      {/* 9. Simple 3-Step "How It Works" */}
      <HowItWorksSection />

      {/* 10. Final High-Impact Closing CTA */}
      <FinalCtaSection />
    </>
  );
}
