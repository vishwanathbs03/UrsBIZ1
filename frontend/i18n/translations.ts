export type SupportedLanguage = "en" | "kn";

export interface LandingTranslations {
  hero: {
    eyebrow: string;
    headlineStart: string;
    headlineHighlight: string;
    headlineEnd: string;
    subheadline: string;
    ctaPrimary: string;
    ctaSecondary: string;
    badge1: string;
    badge2: string;
    badge3: string;
  };
  console: {
    liveTwin: string;
    healthTitle: string;
    healthScore: string;
    healthBand: string;
    revenueTrajectory: string;
    revenueValue: string;
    topOpportunity: string;
    topOpportunityValue: string;
    priorityAction: string;
    priorityActionValue: string;
    aiInsightTitle: string;
    aiInsightBody: string;
    evidenceVerified: string;
    confidence: string;
  };
  trustStrip: {
    title: string;
    item1: string;
    item2: string;
    item3: string;
    item4: string;
    item5: string;
  };
  oneLayer: {
    title: string;
    subtitle: string;
    c1Number: string;
    c1Title: string;
    c1Desc: string;
    c2Number: string;
    c2Title: string;
    c2Desc: string;
    c3Number: string;
    c3Title: string;
    c3Desc: string;
    c4Number: string;
    c4Title: string;
    c4Desc: string;
  };
  aiSection: {
    badge: string;
    title: string;
    subtitle: string;
    userLabel: string;
    userQuery: string;
    aiLabel: string;
    aiAnswer: string;
    evidenceBadge: string;
    whyBadge: string;
    whyBody: string;
    actionBadge: string;
    actionBody: string;
    cta: string;
  };
  biSection: {
    badge: string;
    title: string;
    subtitle: string;
    healthLabel: string;
    revenueLabel: string;
    growthLabel: string;
    actionsLabel: string;
    riskLabel: string;
    healthValue: string;
    revenueValue: string;
    growthValue: string;
    actionsValue: string;
    riskValue: string;
  };
  predictive: {
    badge: string;
    title: string;
    subtitle: string;
    currentLabel: string;
    currentValue: string;
    projectedLabel: string;
    projectedValue: string;
    growthLabel: string;
    growthValue: string;
    scenarioTitle: string;
    scenarioDesc: string;
    disclaimer: string;
  };
  schemes: {
    badge: string;
    title: string;
    subtitle: string;
    s1Title: string;
    s1Match: string;
    s1Subsidy: string;
    s1Desc: string;
    s2Title: string;
    s2Match: string;
    s2Benefit: string;
    s2Desc: string;
    s3Title: string;
    s3Match: string;
    s3Benefit: string;
    s3Desc: string;
    cta: string;
  };
  actionBoard: {
    badge: string;
    title: string;
    subtitle: string;
    a1Title: string;
    a1Priority: string;
    a1Impact: string;
    a2Title: string;
    a2Priority: string;
    a2Impact: string;
    a3Title: string;
    a3Priority: string;
    a3Impact: string;
    cta: string;
  };
  howItWorks: {
    badge: string;
    title: string;
    subtitle: string;
    step1Num: string;
    step1Title: string;
    step1Desc: string;
    step2Num: string;
    step2Title: string;
    step2Desc: string;
    step3Num: string;
    step3Title: string;
    step3Desc: string;
  };
  finalCta: {
    title: string;
    subtitle: string;
    ctaPrimary: string;
    ctaSecondary: string;
  };
}

export interface FinancialTermEntry {
  label: string;
  desc: string;
}

export interface Translations {
  nav: {
    home: string;
    dashboard: string;
    business: string;
    intelligence: string;
    sales: string;
    analytics: string;
    predictiveAnalytics: string;
    insights: string;
    dataConfidence: string;
    metrics: string;
    advisor: string;
    actionBoard: string;
    decisionWorkbench: string;
    whatIf: string;
    goals: string;
    schemes: string;
    assistant: string;
    reports: string;
    collaboration: string;
    integrations: string;
    notifications: string;
    groupOverview: string;
    groupBusiness: string;
    groupIntelligence: string;
    groupActions: string;
    groupDiscover: string;
    groupAssistant: string;
    groupWorkspace: string;
    badgeNew: string;
    badgeAi: string;
    badgeRbac: string;
    more: string;
  };
  landing: LandingTranslations;
  assistant: {
    title: string;
    subtitle: string;
    copilotBadge: string;
    onlineStatus: string;
    localRuleEngine: string;
    verifiedMode: string;
    exploratoryMode: string;
    verifiedModeTooltip: string;
    exploratoryModeTooltip: string;
    clearChat: string;
    refreshData: string;
    searchChatsPlaceholder: string;
    newChat: string;
    noChatsFound: string;
    messagesCount: string;
    composerPlaceholder: string;
    composingPlaceholder: string;
    sendAria: string;
    groundedHint: string;
    shortcutHint: string;
    followUpsTitle: string;
    suggestedTitle: string;
    businessContextTitle: string;
    liveTwin: string;
    healthScore: string;
    businessDna: string;
    actions: string;
    recommendations: string;
    priorityActions: string;
    roadmap: string;
    quickNav: string;
    backendUnreachableFallback: string;
    sendFailed: string;
    noBusinessProfile: string;
    noBusinessDescription: string;
    createBusinessProfile: string;
    learnMore: string;
    goToBusiness: string;
    errorLoadingTitle: string;
    tryAgain: string;
  };
  chips: {
    growthStrategy: string;
    growthStrategyPrompt: string;
    riskAnalysis: string;
    riskAnalysisPrompt: string;
    revenuePlanning: string;
    revenuePlanningPrompt: string;
    govtSchemes: string;
    govtSchemesPrompt: string;
    hiringTeam: string;
    hiringTeamPrompt: string;
    exportExpansion: string;
    exportExpansionPrompt: string;
  };
  trust: {
    calculatedByRuleEngine: string;
    aiGenerated: string;
    fallbackResponse: string;
    evidenceBacked: string;
    limitedData: string;
    openDomain: string;
    whyThisAnswer: string;
    sourcesUsed: string;
    confidence: string;
    groundingScore: string;
  };
  sections: {
    directAnswer: string;
    whatFound: string;
    whatFoundCaption: string;
    why: string;
    whyCaption: string;
    recommendedActions: string;
    recommendedActionsCaption: string;
    scenario: string;
    scenarioCaption: string;
    risks: string;
    risksCaption: string;
    missingInfo: string;
    missingInfoCaption: string;
    evidence: string;
    evidenceCaption: string;
    assumptions: string;
    assumptionsCaption: string;
    confidenceSection: string;
    confidenceCaption: string;
  };
  common: {
    loading: string;
    error: string;
    cancel: string;
    save: string;
    delete: string;
    back: string;
    copied: string;
    copy: string;
    filter: string;
    all: string;
    search: string;
    view: string;
    details: string;
    status: string;
    actions: string;
    confirm: string;
    submit: string;
    close: string;
    refresh: string;
    date: string;
    amount: string;
    currencySymbol: string;
  };
  financialTerms: {
    dso: FinancialTermEntry;
    workingCapital: FinancialTermEntry;
    cashFlow: FinancialTermEntry;
    grossMargin: FinancialTermEntry;
    netProfit: FinancialTermEntry;
    revenue: FinancialTermEntry;
    operatingExpenses: FinancialTermEntry;
    accountsReceivable: FinancialTermEntry;
    accountsPayable: FinancialTermEntry;
    inventoryTurnover: FinancialTermEntry;
    burnRate: FinancialTermEntry;
    customerConcentration: FinancialTermEntry;
    cashRunway: FinancialTermEntry;
  };
  roles: {
    owner: string;
    administrator: string;
    manager: string;
    analyst: string;
    viewer: string;
  };
  decisions: {
    draft: string;
    proposed: string;
    pendingApproval: string;
    approved: string;
    rejected: string;
    executed: string;
    cancelled: string;
    newDecision: string;
    requestApproval: string;
    approve: string;
    reject: string;
    soleOwnerAutoApproved: string;
  };
  feedbackEvaluation: {
    helpful: string;
    incorrectInformation: string;
    missingEvidence: string;
    outdatedData: string;
    difficultToUnderstand: string;
    qualityScore: string;
    helpfulnessRate: string;
    totalFeedback: string;
    groundedVsFallback: string;
    groundedAnswers: string;
    ruleFallbacks: string;
    unclassified: string;
    zeroRetention: string;
    unvote: string;
  };
  goalsTracker: {
    title: string;
    activeGoals: string;
    targetValue: string;
    currentValue: string;
    deadline: string;
    milestones: string;
    onTrack: string;
    atRisk: string;
    behind: string;
    achieved: string;
  };
  reportsExport: {
    title: string;
    exportReport: string;
    downloadPdf: string;
    downloadCsv: string;
    downloadXlsx: string;
    auditPackage: string;
    checksum: string;
  };
  connectors: {
    title: string;
    tallyPrime: string;
    zohoBooks: string;
    manualLedger: string;
    syncStatus: string;
    connected: string;
    inactive: string;
    beta: string;
    lastSync: string;
  };
  a11y: {
    skipToContent: string;
    openNavigation: string;
    closeNavigation: string;
    toggleTheme: string;
    languageSelect: string;
    currentLanguage: string;
    externalLink: string;
    breadcrumb: string;
    loadingState: string;
  };
}

export const translations: Record<SupportedLanguage, Translations> = {
  en: {
    nav: {
      home: "Home",
      dashboard: "Dashboard",
      business: "Business Profile",
      intelligence: "Health Score",
      sales: "Sales Intelligence",
      analytics: "Analytics",
      predictiveAnalytics: "Forecasts",
      insights: "Insights",
      dataConfidence: "Data Confidence",
      metrics: "Metrics Dictionary",
      advisor: "AI Advisor",
      actionBoard: "Recommendations",
      decisionWorkbench: "Decision Workbench",
      whatIf: "What-If Simulator",
      goals: "Business Goals",
      schemes: "Government Schemes",
      assistant: "AI Business Assistant",
      reports: "Reports",
      collaboration: "Team & Approvals",
      integrations: "Integrations",
      notifications: "Notifications",
      groupOverview: "Overview",
      groupBusiness: "Business",
      groupIntelligence: "Intelligence",
      groupActions: "Actions",
      groupDiscover: "Discover",
      groupAssistant: "Assistant",
      groupWorkspace: "Workspace",
      badgeNew: "NEW",
      badgeAi: "AI",
      badgeRbac: "RBAC",
      more: "More",
    },
    landing: {
      hero: {
        eyebrow: "AI BUSINESS INTELLIGENCE FOR MSMEs",
        headlineStart: "Run your business with ",
        headlineHighlight: "AI-powered",
        headlineEnd: " intelligence.",
        subheadline:
          "Understand your business health, discover government opportunities, predict what comes next, and turn insights into action — all from one unified platform.",
        ctaPrimary: "Get Started Free",
        ctaSecondary: "Explore UrsBiz",
        badge1: "AI Business Copilot",
        badge2: "Business Health Intelligence",
        badge3: "Predictive Scenarios",
      },
      console: {
        liveTwin: "LIVE DIGITAL TWIN ACTIVE",
        healthTitle: "Business Health Score",
        healthScore: "78",
        healthBand: "ESTABLISHED",
        revenueTrajectory: "Projected Trajectory",
        revenueValue: "+24% FY26",
        topOpportunity: "Top Scheme Match",
        topOpportunityValue: "PMEGP (95% Match)",
        priorityAction: "Priority Action",
        priorityActionValue: "Optimize Working Capital Cycle",
        aiInsightTitle: "Grounded AI Copilot Insight",
        aiInsightBody:
          "Your strongest near-term growth lever is reducing DSO from 68 to 45 days, which unlocks ₹3.2L in operating liquidity for inventory expansion.",
        evidenceVerified: "Evidence: SCORE-RISK-01 • RULE-WC-04",
        confidence: "94% Grounded Confidence",
      },
      trustStrip: {
        title: "BUILT FOR ENTERPRISE MSMEs & FOUNDERS",
        item1: "Business Intelligence",
        item2: "AI-Assisted Decisions",
        item3: "Government Schemes Discovery",
        item4: "Predictive Analytics",
        item5: "Strategic Action Planning",
      },
      oneLayer: {
        title: "Everything you need to understand your business.",
        subtitle:
          "Four coordinated intelligence layers that eliminate guesswork and empower decisive business growth.",
        c1Number: "01",
        c1Title: "Understand",
        c1Desc: "Comprehensive business health scoring, working capital position, and operational bottleneck identification.",
        c2Number: "02",
        c2Title: "Discover",
        c2Desc: "Tailored central and state government subsidies, PMEGP grant matching, and market expansion opportunities.",
        c3Number: "03",
        c3Title: "Predict",
        c3Desc: "Forward-looking revenue trends, customer concentration risk, and deterministic scenario forecasts.",
        c4Number: "04",
        c4Title: "Act",
        c4Desc: "Convert deep analytics into concrete, prioritized execution steps tracked on your strategic Action Board.",
      },
      aiSection: {
        badge: "FLAGSHIP AI COPILOT",
        title: "Ask your business anything.",
        subtitle:
          "UrsBiz AI understands your verified business context and turns operational data into grounded, high-trust answers.",
        userLabel: "Executive Question",
        userQuery: "What is our biggest business risk right now and how do we resolve it?",
        aiLabel: "UrsBiz Copilot (Grounded Mode)",
        aiAnswer:
          "Your primary business risk is working capital pressure resulting from a 68-day DSO cycle and 42% revenue reliance on a single customer.",
        evidenceBadge: "Evidence: SCORE-RISK-01 • RULE-WC-04",
        whyBadge: "Why This Answer",
        whyBody: "Calculated deterministically from registered balance sheet ratios and supplier invoices in your Digital Twin.",
        actionBadge: "Recommended Action",
        actionBody: "Shift 15% procurement to secondary vendors and enforce 30-day invoice discounting with major accounts.",
        cta: "Try AI Assistant →",
      },
      biSection: {
        badge: "DIGITAL TWIN ENGINE",
        title: "Your business at a single glance.",
        subtitle: "Real-time metrics calculated from verified financial, operational, and market parameters.",
        healthLabel: "Business Health",
        revenueLabel: "Annual Revenue",
        growthLabel: "Projected Growth",
        actionsLabel: "Priority Actions",
        riskLabel: "Risk Exposure",
        healthValue: "78 / 100",
        revenueValue: "₹12.5 Lakh",
        growthValue: "+18%",
        actionsValue: "13 Pending",
        riskValue: "Moderate (Managed)",
      },
      predictive: {
        badge: "PREDICTIVE MODELING",
        title: "See what could happen next.",
        subtitle:
          "UrsBiz combines business context, historical benchmarks, and deterministic rule engines to simulate forward scenarios.",
        currentLabel: "Current Revenue Run-rate",
        currentValue: "₹12.5L",
        projectedLabel: "Optimized 12-Month Target",
        projectedValue: "₹15.4L",
        growthLabel: "Potential Growth Upside",
        growthValue: "+23.2%",
        scenarioTitle: "Scenario: +15% Working Capital Optimization",
        scenarioDesc: "By improving debtor collection efficiency by 18 days, the business gains ₹2.4L in free cash flow, supporting hiring 2 technicians.",
        disclaimer: "Deterministic forward projections based on active business parameters and verified MSME data models.",
      },
      schemes: {
        badge: "GOVERNMENT SCHEMES ENGINE",
        title: "Find support your business can actually use.",
        subtitle: "Automated eligibility matching across Central & State MSME subsidies, capital grants, and credit guarantees.",
        s1Title: "PMEGP (Prime Minister Employment Generation)",
        s1Match: "95% Match",
        s1Subsidy: "Up to 35% Capital Subsidy",
        s1Desc: "High eligibility for manufacturing & service enterprises looking to expand machinery and production footprint.",
        s2Title: "CGTMSE Collateral-Free Credit",
        s2Match: "91% Match",
        s2Benefit: "Collateral-Free loans up to ₹5 Cr",
        s2Desc: "Credit guarantee fund backing loans from scheduled commercial banks with zero third-party collateral required.",
        s3Title: "ZED Certification Scheme",
        s3Match: "88% Match",
        s3Benefit: "Up to 80% Subsidy on Certification",
        s3Desc: "Zero Defect Zero Effect financial support for quality improvement, testing, and green manufacturing compliance.",
        cta: "Explore Government Schemes →",
      },
      actionBoard: {
        badge: "EXECUTION & ROADMAP",
        title: "Turn insights into action.",
        subtitle: "Move from passive observation to disciplined execution with an integrated executive action board.",
        a1Title: "Improve Working Capital Cycle",
        a1Priority: "High Priority",
        a1Impact: "Impact: +₹2.4L Free Cash Flow",
        a2Title: "Apply for PMEGP Capital Subsidy",
        a2Priority: "High Priority",
        a2Impact: "Impact: 35% Machinery Subsidy",
        a3Title: "Diversify Key Component Sourcing",
        a3Priority: "Medium Priority",
        a3Impact: "Impact: Reduces Supply Risk by 40%",
        cta: "Open Action Board →",
      },
      howItWorks: {
        badge: "SIMPLE 3-STEP WORKFLOW",
        title: "How UrsBiz powers your growth.",
        subtitle: "From setup to actionable business insights in less than three minutes.",
        step1Num: "01",
        step1Title: "Build your business profile",
        step1Desc: "Enter your fundamental MSME data, sector, turnover, and operational details into the digital twin onboarding engine.",
        step2Num: "02",
        step2Title: "Understand your reality",
        step2Desc: "The platform evaluates health across 8 categories, flags hidden vulnerabilities, and matches relevant government schemes.",
        step3Num: "03",
        step3Title: "Act on intelligent recommendations",
        step3Desc: "Consult the AI Copilot for grounded advice, execute priority tasks on the Action Board, and monitor predictive growth.",
      },
      finalCta: {
        title: "Your business already has the data. Now turn it into decisions.",
        subtitle: "Build a clearer picture of your business, discover untapped government opportunities, and lead with confidence.",
        ctaPrimary: "Get Started Free →",
        ctaSecondary: "Explore AI Assistant →",
      },
    },
    assistant: {
      title: "UrsBiz AI Copilot",
      subtitle: "Strategic business intelligence grounded in your verified MSME data",
      copilotBadge: "UrsBiz AI Copilot",
      onlineStatus: "Ollama Active",
      localRuleEngine: "Local Rule Engine Active",
      verifiedMode: "Verified Mode",
      exploratoryMode: "Exploratory Mode",
      verifiedModeTooltip:
        "Verified Business Analysis (Grounded) — Strict evidence-bounded reasoning from your Digital Twin.",
      exploratoryModeTooltip:
        "Exploratory Business Advisor (Open) — Broader strategic brainstorming and scenario exploration.",
      clearChat: "Clear chat",
      refreshData: "Refresh analysis",
      searchChatsPlaceholder: "Search conversation history...",
      newChat: "New Conversation",
      noChatsFound: "No conversations found.",
      messagesCount: "messages",
      composerPlaceholder: "Ask a strategic question about your business (e.g. 'What is our revenue growth target?')...",
      composingPlaceholder: "Analyzing business evidence and composing response...",
      sendAria: "Send question to UrsBiz AI",
      groundedHint: "Grounded in your Business Twin",
      shortcutHint: "Press Enter to send, Shift+Enter for new line",
      followUpsTitle: "Recommended Follow-ups",
      suggestedTitle: "Strategic Prompts",
      businessContextTitle: "Business Intelligence",
      liveTwin: "Digital Twin",
      healthScore: "Health Score",
      businessDna: "Business DNA",
      actions: "Actions",
      recommendations: "Recommendations",
      priorityActions: "Priority",
      roadmap: "Roadmap Progress",
      quickNav: "Quick Navigation",
      backendUnreachableFallback: "Backend unreachable — answering with local rule engine.",
      sendFailed: "Unable to send message. Please try again.",
      noBusinessProfile: "No Business Profile Registered",
      noBusinessDescription:
        "To enable verified AI reasoning with actual business data, create or import your Business Profile.",
      createBusinessProfile: "Create Business Profile",
      learnMore: "Learn More",
      goToBusiness: "Go to Business Profile",
      errorLoadingTitle: "Error Loading Assistant Context",
      tryAgain: "Try Again",
    },
    chips: {
      growthStrategy: "Growth Strategy",
      growthStrategyPrompt: "What is our best growth strategy for the next 12 months based on our current profile?",
      riskAnalysis: "Risk Analysis",
      riskAnalysisPrompt: "What are our primary business risks and vulnerabilities?",
      revenuePlanning: "Revenue Planning",
      revenuePlanningPrompt: "What is our current revenue and how can we achieve our target turnover?",
      govtSchemes: "Government Schemes",
      govtSchemesPrompt: "Which government schemes and subsidies is my business eligible for?",
      hiringTeam: "Hiring & Team",
      hiringTeamPrompt: "Should we hire more employees or expand operations first?",
      exportExpansion: "Export Expansion",
      exportExpansionPrompt: "Is our business ready for export market expansion?",
    },
    trust: {
      calculatedByRuleEngine: "Calculated by UrsBiz",
      aiGenerated: "AI Analysis",
      fallbackResponse: "Deterministic Local Engine",
      evidenceBacked: "Verified Business Evidence",
      limitedData: "Needs Verification",
      openDomain: "Scenario Estimate",
      whyThisAnswer: "Why this answer",
      sourcesUsed: "Evidence & Context Sources",
      confidence: "Grounding Confidence",
      groundingScore: "Grounding Score",
    },
    sections: {
      directAnswer: "Direct Answer",
      whatFound: "Findings Summary",
      whatFoundCaption: "Key data points extracted from your Business Twin",
      why: "Why This Matters",
      whyCaption: "Strategic rationale and business impact",
      recommendedActions: "Recommended Actions",
      recommendedActionsCaption: "Concrete steps to execute",
      scenario: "Scenario Simulation",
      scenarioCaption: "Projected financial and operational outcome",
      risks: "Identified Risks",
      risksCaption: "Vulnerabilities to monitor and mitigate",
      missingInfo: "Data Needs",
      missingInfoCaption: "Additional details needed for higher precision",
      evidence: "Verified Evidence",
      evidenceCaption: "Traceable data points used in this calculation",
      assumptions: "Key Assumptions",
      assumptionsCaption: "Underlying premises for this analysis",
      confidenceSection: "Verification & Confidence",
      confidenceCaption: "Calculated trustworthiness score",
    },
    common: {
      loading: "Loading...",
      error: "An error occurred",
      cancel: "Cancel",
      save: "Save",
      delete: "Delete",
      back: "Back",
      copied: "Copied!",
      copy: "Copy",
      filter: "Filter",
      all: "All",
      search: "Search",
      view: "View",
      details: "Details",
      status: "Status",
      actions: "Actions",
      confirm: "Confirm",
      submit: "Submit",
      close: "Close",
      refresh: "Refresh",
      date: "Date",
      amount: "Amount",
      currencySymbol: "₹",
    },
    financialTerms: {
      dso: {
        label: "Days Sales Outstanding (DSO)",
        desc: "Average number of days required to collect invoice payment after a sale.",
      },
      workingCapital: {
        label: "Working Capital",
        desc: "Operating liquidity available for daily transactions (Current Assets minus Current Liabilities).",
      },
      cashFlow: {
        label: "Cash Flow",
        desc: "Net movement of cash funds transferred into and out of the business ledger.",
      },
      grossMargin: {
        label: "Gross Margin",
        desc: "Percentage of revenue exceeding Cost of Goods Sold (COGS).",
      },
      netProfit: {
        label: "Net Profit",
        desc: "Final earnings remaining after deducting all operational costs, taxes, and interest.",
      },
      revenue: {
        label: "Revenue",
        desc: "Total gross turnover recognized from verified sales orders and customer invoices.",
      },
      operatingExpenses: {
        label: "Operating Expenses (OpEx)",
        desc: "Fixed and variable overhead expenditures required to maintain business operations.",
      },
      accountsReceivable: {
        label: "Accounts Receivable",
        desc: "Pending payments legally owed to the business by customers for goods delivered.",
      },
      accountsPayable: {
        label: "Accounts Payable",
        desc: "Outstanding liabilities owed by the business to suppliers and vendors.",
      },
      inventoryTurnover: {
        label: "Inventory Turnover",
        desc: "Rate at which physical stock is sold and replenished over a standard operating cycle.",
      },
      burnRate: {
        label: "Burn Rate",
        desc: "Net cash depletion rate per month when operating expenditures exceed collections.",
      },
      customerConcentration: {
        label: "Customer Concentration",
        desc: "Share of revenue accounted for by top buyers, indicating structural revenue risk.",
      },
      cashRunway: {
        label: "Cash Runway",
        desc: "Estimated survival duration in months based on available cash reserves and monthly burn.",
      },
    },
    roles: {
      owner: "Owner",
      administrator: "Administrator",
      manager: "Manager",
      analyst: "Analyst",
      viewer: "Viewer",
    },
    decisions: {
      draft: "Draft",
      proposed: "Proposed",
      pendingApproval: "Pending Approval",
      approved: "Approved",
      rejected: "Rejected",
      executed: "Executed",
      cancelled: "Cancelled",
      newDecision: "New Decision",
      requestApproval: "Request Approval",
      approve: "Approve",
      reject: "Reject",
      soleOwnerAutoApproved: "Sole Owner — Auto-Approved",
    },
    feedbackEvaluation: {
      helpful: "Helpful",
      incorrectInformation: "Incorrect Information",
      missingEvidence: "Missing Evidence",
      outdatedData: "Outdated Data",
      difficultToUnderstand: "Difficult to Understand",
      qualityScore: "Quality Score",
      helpfulnessRate: "Helpfulness Rate",
      totalFeedback: "Total Feedback",
      groundedVsFallback: "Grounded vs. Rule Fallback Telemetry",
      groundedAnswers: "Grounded Answers",
      ruleFallbacks: "Rule Engine Fallbacks",
      unclassified: "Unclassified",
      zeroRetention: "Zero-Retention Data Sovereignty",
      unvote: "Remove feedback",
    },
    goalsTracker: {
      title: "Business Goals & Progress Tracker",
      activeGoals: "Active Goals",
      targetValue: "Target Value",
      currentValue: "Current Value",
      deadline: "Deadline",
      milestones: "Milestones",
      onTrack: "On Track",
      atRisk: "At Risk",
      behind: "Behind",
      achieved: "Achieved",
    },
    reportsExport: {
      title: "Reports & Evidence Export Centre",
      exportReport: "Export Report",
      downloadPdf: "Download PDF",
      downloadCsv: "Download CSV",
      downloadXlsx: "Download Excel",
      auditPackage: "Audit Evidence Package",
      checksum: "SHA-256 Checksum",
    },
    connectors: {
      title: "Integrations & Connectors",
      tallyPrime: "Tally Prime ERP",
      zohoBooks: "Zoho Books",
      manualLedger: "Manual Ledger Upload",
      syncStatus: "Sync Status",
      connected: "Connected",
      inactive: "Inactive",
      beta: "Beta",
      lastSync: "Last Synchronized",
    },
    a11y: {
      skipToContent: "Skip to main content",
      openNavigation: "Open navigation menu",
      closeNavigation: "Close navigation menu",
      toggleTheme: "Toggle color theme",
      languageSelect: "Change interface language",
      currentLanguage: "Current language: English",
      externalLink: "(opens in a new window)",
      breadcrumb: "Breadcrumb navigation",
      loadingState: "Loading content, please wait...",
    },
  },
  kn: {
    nav: {
      home: "ಮುಖಪುಟ",
      dashboard: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
      business: "ವ್ಯವಹಾರ ಪ್ರೊಫೈಲ್",
      intelligence: "ಆರೋಗ್ಯ ಸ್ಕೋರ್",
      sales: "ಮಾರಾಟ ಬುದ್ಧಿಮತ್ತೆ",
      analytics: "ವಿಶ್ಲೇಷಣೆ",
      predictiveAnalytics: "ಮುನ್ಸೂಚನೆಗಳು",
      insights: "ಒಳನೋಟಗಳು",
      dataConfidence: "ದತ್ತಾಂಶ ವಿಶ್ವಾಸಾರ್ಹತೆ",
      metrics: "ಮೆಟ್ರಿಕ್ಸ್ ನಿಘಂಟು",
      advisor: "AI ಸಲಹೆಗಾರ",
      actionBoard: "ಶಿಫಾರಸುಗಳು",
      decisionWorkbench: "ನಿರ್ಧಾರ ಕಾರ್ಯಕ್ಷೇತ್ರ",
      whatIf: "ಸನ್ನಿವೇಶ ಸಿಮ್ಯುಲೇಟರ್",
      goals: "ವ್ಯವಹಾರ ಗುರಿಗಳು",
      schemes: "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು",
      assistant: "AI ವ್ಯವಹಾರ ಸಹಾಯಕ",
      reports: "ವರದಿಗಳು",
      collaboration: "ತಂಡ ಮತ್ತು ಅನುಮೋದನೆಗಳು",
      integrations: "ಸಂಯೋಜನೆಗಳು",
      notifications: "ಸೂಚನೆಗಳು",
      groupOverview: "ಅವಲೋಕನ",
      groupBusiness: "ವ್ಯವಹಾರ",
      groupIntelligence: "ಬುದ್ಧಿಮತ್ತೆ",
      groupActions: "ಕ್ರಮಗಳು",
      groupDiscover: "ಅನ್ವೇಷಿಸಿ",
      groupAssistant: "ಸಹಾಯಕ",
      groupWorkspace: "ಕಾರ್ಯಕ್ಷೇತ್ರ",
      badgeNew: "ಹೊಸತು",
      badgeAi: "AI",
      badgeRbac: "RBAC",
      more: "ಇನ್ನಷ್ಟು",
    },
    landing: {
      hero: {
        eyebrow: "MSME ಗಳಿಗಾಗಿ AI ವ್ಯವಹಾರ ಬುದ್ಧಿಮತ್ತೆ",
        headlineStart: "ನಿಮ್ಮ ವ್ಯವಹಾರವನ್ನು ",
        headlineHighlight: "AI-ಚಾಲಿತ",
        headlineEnd: " ಬುದ್ಧಿಮತ್ತೆಯೊಂದಿಗೆ ಮುನ್ನಡೆಸಿ.",
        subheadline:
          "ನಿಮ್ಮ ವ್ಯವಹಾರದ ಆರೋಗ್ಯವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಿ, ಸರ್ಕಾರಿ ಅವಕಾಶಗಳನ್ನು ಅನ್ವೇಷಿಸಿ, ಮುಂದಿನ ಫಲಿತಾಂಶಗಳನ್ನು ಊಹಿಸಿ ಮತ್ತು ಒಳನೋಟಗಳನ್ನು ಕ್ರಮವಾಗಿ ಪರಿವರ್ತಿಸಿ — ಎಲ್ಲವೂ ಒಂದೇ ವೇದಿಕೆಯಲ್ಲಿ.",
        ctaPrimary: "ಉಚಿತವಾಗಿ ಪ್ರಾರಂಭಿಸಿ",
        ctaSecondary: "UrsBiz ಅನ್ವೇಷಿಸಿ",
        badge1: "AI ವ್ಯವಹಾರ ಸಹಾಯಕ",
        badge2: "ವ್ಯವಹಾರ ಆರೋಗ್ಯ ಬುದ್ಧಿಮತ್ತೆ",
        badge3: "ಭವಿಷ್ಯದ ಸನ್ನಿವೇಶಗಳು",
      },
      console: {
        liveTwin: "ಲೈವ್ ಡಿಜಿಟಲ್ ಟ್ವಿನ್ ಸಕ್ರಿಯವಾಗಿದೆ",
        healthTitle: "ವ್ಯವಹಾರ ಆರೋಗ್ಯ ಸ್ಕೋರ್",
        healthScore: "78",
        healthBand: "ಸ್ಥಾಪಿತ",
        revenueTrajectory: "ನಿರೀಕ್ಷಿತ ಆದಾಯದ ಪಥ",
        revenueValue: "+24% FY26",
        topOpportunity: "ಪ್ರಮುಖ ಸರ್ಕಾರಿ ಯೋಜನೆ",
        topOpportunityValue: "PMEGP (95% ಹೊಂದಾಣಿಕೆ)",
        priorityAction: "ಆದ್ಯತೆಯ ಕ್ರಮ",
        priorityActionValue: "ಕಾರ್ಯನಿರತ ಬಂಡವಾಳ ಚಕ್ರ ಸುಧಾರಣೆ",
        aiInsightTitle: "AI ಸಹಾಯಕರ ಆಧಾರಿತ ಒಳನೋಟ",
        aiInsightBody:
          "ನಿಮ್ಮ ಹತ್ತಿರದ ಬೆಳವಣಿಗೆಯ ಅವಕಾಶವೆಂದರೆ DSO ಅನ್ನು 68 ರಿಂದ 45 ದಿನಗಳಿಗೆ ಇಳಿಸುವುದು, ಇದರಿಂದ ₹3.2L ನಗದು ಉಳಿತಾಯವಾಗುತ್ತದೆ.",
        evidenceVerified: "ಪುರಾವೆ: SCORE-RISK-01 • RULE-WC-04",
        confidence: "94% ಆಧಾರಿತ ವಿಶ್ವಾಸಾರ್ಹತೆ",
      },
      trustStrip: {
        title: "ವ್ಯವಹಾರ ಮಾಲೀಕರು ಮತ್ತು MSME ಗಳಿಗಾಗಿ ನಿರ್ಮಿಸಲಾಗಿದೆ",
        item1: "ವ್ಯವಹಾರ ಬುದ್ಧಿಮತ್ತೆ",
        item2: "AI-ಸಹಾಯದ ನಿರ್ಧಾರಗಳು",
        item3: "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಶೋಧ",
        item4: "ಭವಿಷ್ಯದ ವಿಶ್ಲೇಷಣೆ",
        item5: "ಕಾರ್ಯತಂತ್ರದ ಯೋಜನೆ",
      },
      oneLayer: {
        title: "ನಿಮ್ಮ ವ್ಯವಹಾರವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಎಲ್ಲವೂ ಇಲ್ಲಿದೆ.",
        subtitle:
          "ಊಹೆಗಳನ್ನು ತಪ್ಪಿಸಿ ನಿಖರವಾದ ವ್ಯವಹಾರ ಬೆಳವಣಿಗೆಗೆ ಶಕ್ತಿ ನೀಡುವ ನಾಲ್ಕು ಸಮನ್ವಯ ಬುದ್ಧಿಮತ್ತೆ ಹಂತಗಳು.",
        c1Number: "01",
        c1Title: "ಅರ್ಥಮಾಡಿಕೊಳ್ಳಿ",
        c1Desc: "ಸಮಗ್ರ ವ್ಯವಹಾರ ಆರೋಗ್ಯ ಸ್ಕೋರಿಂಗ್, ಕಾರ್ಯನಿರತ ಬಂಡವಾಳದ ಸ್ಥಿತಿ ಮತ್ತು ಕಾರ್ಯಾಚರಣೆಯ ಅಡೆತಡೆಗಳ ಗುರುತಿಸುವಿಕೆ.",
        c2Number: "02",
        c2Title: "ಅನ್ವೇಷಿಸಿ",
        c2Desc: "ಕೇಂದ್ರ ಮತ್ತು ರಾಜ್ಯ ಸರ್ಕಾರದ ಸಬ್ಸಿಡಿಗಳು, PMEGP ಅನುದಾನ ಹೊಂದಾಣಿಕೆ ಮತ್ತು ಮಾರುಕಟ್ಟೆ ವಿಸ್ತರಣೆ ಅವಕಾಶಗಳು.",
        c3Number: "03",
        c3Title: "ಊಹಿಸಿ",
        c3Desc: "ಭವಿಷ್ಯದ ಆದಾಯದ ಪ್ರವೃತ್ತಿಗಳು, ಗ್ರಾಹಕರ ಸಾಂದ್ರತೆಯ ಅಪಾಯ ಮತ್ತು ನಿಯಮ-ಆಧಾರಿತ ಸನ್ನಿವೇಶದ ಮುನ್ಸೂಚನೆಗಳು.",
        c4Number: "04",
        c4Title: "ಕ್ರಮ ಕೈಗೊಳ್ಳಿ",
        c4Desc: "ವಿಶ್ಲೇಷಣೆಗಳನ್ನು ನಿಮ್ಮ ಕಾರ್ಯತಂತ್ರದ ಕ್ರಿಯಾ ಮಂಡಳಿಯಲ್ಲಿ ಆದ್ಯತೆಯ ಕಾರ್ಯಗತಗೊಳಿಸುವ ಹಂತಗಳಾಗಿ ಪರಿವರ್ತಿಸಿ.",
      },
      aiSection: {
        badge: "ಪ್ರಮುಖ AI ಸಹಾಯಕ",
        title: "ನಿಮ್ಮ ವ್ಯವಹಾರದ ಬಗ್ಗೆ ಏನನ್ನಾದರೂ ಕೇಳಿ.",
        subtitle:
          "UrsBiz AI ನಿಮ್ಮ ಪರಿಶೀಲಿಸಿದ ವ್ಯವಹಾರ ಸಂದರ್ಭವನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತದೆ ಮತ್ತು ದತ್ತಾಂಶವನ್ನು ಆಧಾರಿತ, ವಿಶ್ವಾಸಾರ್ಹ ಉತ್ತರಗಳಾಗಿ ಪರಿವರ್ತಿಸುತ್ತದೆ.",
        userLabel: "ಕಾರ್ಯನಿರ್ವಾಹಕ ಪ್ರಶ್ನೆ",
        userQuery: "ನಮ್ಮ ಪ್ರಸ್ತುತ ದೊಡ್ಡ ವ್ಯವಹಾರದ ಅಪಾಯ ಯಾವುದು ಮತ್ತು ಅದನ್ನು ಹೇಗೆ ಪರಿಹರಿಸುವುದು?",
        aiLabel: "UrsBiz AI ಸಹಾಯಕ (ಆಧಾರಿತ ಮೋಡ್)",
        aiAnswer:
          "ನಿಮ್ಮ ಮುಖ್ಯ ಅಪಾಯವೆಂದರೆ 68 ದಿನಗಳ DSO ಚಕ್ರ ಮತ್ತು ಒಬ್ಬ ಗ್ರಾಹಕರ ಮೇಲೆ 42% ಆದಾಯ ಅವಲಂಬನೆ.",
        evidenceBadge: "ಪುರಾವೆ: SCORE-RISK-01 • RULE-WC-04",
        whyBadge: "ಈ ಉತ್ತರಕ್ಕೆ ಕಾರಣ",
        whyBody: "ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಟ್ವಿನ್‌ನಲ್ಲಿ ದಾಖಲಾದ ಬ್ಯಾಲೆನ್ಸ್ ಶೀಟ್ ಮತ್ತು ಸರಬರಾಜುದಾರರ ಇನ್‌ವಾಯ್ಸ್‌ಗಳಿಂದ ಲೆಕ್ಕಹಾಕಲಾಗಿದೆ.",
        actionBadge: "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮ",
        actionBody: "15% ಖರೀದಿಯನ್ನು ದ್ವಿತೀಯ ಸರಬರಾಜುದಾರರಿಗೆ ಬದಲಾಯಿಸಿ ಮತ್ತು 30 ದಿನಗಳ ಇನ್‌ವಾಯ್ಸ್ ರಿಯಾಯಿತಿ ಜಾರಿಗೊಳಿಸಿ.",
        cta: "AI ಸಹಾಯಕ ಬಳಸಿ ನೋಡಿ →",
      },
      biSection: {
        badge: "ಡಿಜಿಟಲ್ ಟ್ವಿನ್ ಎಂಜಿನ್",
        title: "ನಿಮ್ಮ ವ್ಯವಹಾರ ಒಂದೇ ನೋಟದಲ್ಲಿ.",
        subtitle: "ಪರಿಶೀಲಿಸಿದ ಹಣಕಾಸು, ಕಾರ್ಯಾಚರಣೆ ಮತ್ತು ಮಾರುಕಟ್ಟೆ ನಿಯತಾಂಕಗಳಿಂದ ನೈಜ ಸಮಯದಲ್ಲಿ ಲೆಕ್ಕಹಾಕಿದ ಮೆಟ್ರಿಕ್ಸ್.",
        healthLabel: "ವ್ಯವಹಾರ ಆರೋಗ್ಯ",
        revenueLabel: "ವಾರ್ಷಿಕ ಆದಾಯ",
        growthLabel: "ನಿರೀಕ್ಷಿತ ಬೆಳವಣಿಗೆ",
        actionsLabel: "ಆದ್ಯತೆಯ ಕ್ರಮಗಳು",
        riskLabel: "ಅಪಾಯದ ಮಟ್ಟ",
        healthValue: "78 / 100",
        revenueValue: "₹12.5 ಲಕ್ಷ",
        growthValue: "+18%",
        actionsValue: "13 ಬಾಕಿ",
        riskValue: "ಮಧ್ಯಮ (ನಿಯಂತ್ರಿತ)",
      },
      predictive: {
        badge: "ಭವಿಷ್ಯದ ಮಾದರಿ",
        title: "ಮುಂದೆ ಏನಾಗಬಹುದು ಎಂದು ನೋಡಿ.",
        subtitle:
          "UrsBiz ವ್ಯವಹಾರ ಸಂದರ್ಭ, ಐತಿಹಾಸಿಕ ಮಾದರಿಗಳು ಮತ್ತು ನಿಯಮ ಎಂಜಿನ್‌ಗಳನ್ನು ಸಂಯೋಜಿಸಿ ಭವಿಷ್ಯದ ಸನ್ನಿವೇಶಗಳನ್ನು ಊಹಿಸುತ್ತದೆ.",
        currentLabel: "ಪ್ರಸ್ತುತ ಆದಾಯ ದರ",
        currentValue: "₹12.5 ಲಕ್ಷ",
        projectedLabel: "12 ತಿಂಗಳ ನಿರೀಕ್ಷಿತ ಗುರಿ",
        projectedValue: "₹15.4 ಲಕ್ಷ",
        growthLabel: "ಸಾಧ್ಯವಿರುವ ಬೆಳವಣಿಗೆ",
        growthValue: "+23.2%",
        scenarioTitle: "ಸನ್ನಿವೇಶ: +15% ಕಾರ್ಯನಿರತ ಬಂಡವಾಳ ಸುಧಾರಣೆ",
        scenarioDesc: "ವಸೂಲಾತಿ ದಕ್ಷತೆಯನ್ನು 18 ದಿನಗಳಷ್ಟು ಸುಧಾರಿಸುವುದರಿಂದ ವ್ಯವಹಾರವು ₹2.4L ನಗದು ಹಣವನ್ನು ಪಡೆಯುತ್ತದೆ.",
        disclaimer: "ಸಕ್ರಿಯ ವ್ಯವಹಾರ ನಿಯತಾಂಕಗಳು ಮತ್ತು ಪರಿಶೀಲಿಸಿದ MSME ಡೇಟಾ ಆಧಾರಿತ ಮುನ್ಸೂಚನೆಗಳು.",
      },
      schemes: {
        badge: "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಎಂಜಿನ್",
        title: "ನಿಮ್ಮ ವ್ಯವಹಾರಕ್ಕೆ ಸೂಕ್ತವಾದ ಬೆಂಬಲವನ್ನು ಹುಡುಕಿ.",
        subtitle: "ಕೇಂದ್ರ ಮತ್ತು ರಾಜ್ಯ MSME ಸಬ್ಸಿಡಿಗಳು, ಬಂಡವಾಳ ಅನುದಾನಗಳು ಮತ್ತು ಸಾಲ ಖಾತರಿಗಳ ಸ್ವಯಂಚಾಲಿತ ಹೊಂದಾಣಿಕೆ.",
        s1Title: "PMEGP (ಪ್ರಧಾನ ಮಂತ್ರಿ ಉದ್ಯೋಗ ಸೃಜನ ಯೋಜನೆ)",
        s1Match: "95% ಹೊಂದಾಣಿಕೆ",
        s1Subsidy: "35% ವರೆಗೆ ಬಂಡವಾಳ ಸಬ್ಸಿಡಿ",
        s1Desc: "ಉತ್ಪಾದನಾ ಯಂತ್ರೋಪಕರಣ ಮತ್ತು ವಿಸ್ತರಣೆಗೆ ಅತ್ಯುನ್ನತ ಅರ್ಹತೆ.",
        s2Title: "CGTMSE ಜಾಮೀನು ರಹಿತ ಸಾಲ",
        s2Match: "91% ಹೊಂದಾಣಿಕೆ",
        s2Benefit: "₹5 ಕೋಟಿ ವರೆಗೆ ಜಾಮೀನು ರಹಿತ ಸಾಲ",
        s2Desc: "ಯಾವುದೇ ಮೂರನೇ ವ್ಯಕ್ತಿಯ ಭದ್ರತೆಯಿಲ್ಲದೆ ಬ್ಯಾಂಕ್ ಸಾಲಗಳಿಗೆ ಕ್ರೆಡಿಟ್ ಗ್ಯಾರಂಟಿ ಬೆಂಬಲ.",
        s3Title: "ZED ಪ್ರಮಾಣೀಕರಣ ಯೋಜನೆ",
        s3Match: "88% ಹೊಂದಾಣಿಕೆ",
        s3Benefit: "ಪ್ರಮಾಣೀಕರಣ ವೆಚ್ಚದ ಮೇಲೆ 80% ವರೆಗೆ ಸಬ್ಸಿಡಿ",
        s3Desc: "ಗುಣಮಟ್ಟ ಸುಧಾರಣೆ, ಪರೀಕ್ಷೆ ಮತ್ತು ಹಸಿರು ಉತ್ಪಾದನಾ ಅನುಸರಣೆಗೆ ಆರ್ಥಿಕ ನೆರವು.",
        cta: "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಅನ್ವೇಷಿಸಿ →",
      },
      actionBoard: {
        badge: "ಕಾರ್ಯಗತಗೊಳಿಸುವಿಕೆ ಮತ್ತು ರೋಡ್‌ಮ್ಯಾಪ್",
        title: "ಒಳನೋಟಗಳನ್ನು ಕ್ರಿಯೆಯನ್ನಾಗಿ ಪರಿವರ್ತಿಸಿ.",
        subtitle: "ಸಂಯೋಜಿತ ಕಾರ್ಯನಿರ್ವಾಹಕ ಕ್ರಿಯಾ ಮಂಡಳಿಯೊಂದಿಗೆ ನಿಷ್ಕ್ರಿಯತೆಯಿಂದ ಶಿಸ್ತುಬದ್ಧ ಕಾರ್ಯಗತಗೊಳಿಸುವಿಕೆಗೆ ಸಾಗಿ.",
        a1Title: "ಕಾರ್ಯನಿರತ ಬಂಡವಾಳ ಚಕ್ರ ಸುಧಾರಣೆ",
        a1Priority: "ಹೆಚ್ಚಿನ ಆದ್ಯತೆ",
        a1Impact: "ಪ್ರಭಾವ: +₹2.4L ನಗದು ಉಳಿತಾಯ",
        a2Title: "PMEGP ಬಂಡವಾಳ ಸಬ್ಸಿಡಿಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ",
        a2Priority: "ಹೆಚ್ಚಿನ ಆದ್ಯತೆ",
        a2Impact: "ಪ್ರಭಾವ: 35% ಯಂತ್ರೋಪಕರಣ ಸಬ್ಸಿಡಿ",
        a3Title: "ಪ್ರಮುಖ ಸರಬರಾಜುದಾರರ ವೈವಿಧ್ಯೀಕರಣ",
        a3Priority: "ಮಧ್ಯಮ ಆದ್ಯತೆ",
        a3Impact: "ಪ್ರಭಾವ: ಪೂರೈಕೆ ಅಪಾಯ 40% ಇಳಿಕೆ",
        cta: "ಕ್ರಿಯಾ ಮಂಡಳಿ ತೆರೆಯಿರಿ →",
      },
      howItWorks: {
        badge: "ಸರಳ 3-ಹಂತದ ವಿಧಾನ",
        title: "UrsBiz ನಿಮ್ಮ ಬೆಳವಣಿಗೆಗೆ ಹೇಗೆ ನೆರವಾಗುತ್ತದೆ.",
        subtitle: "ಮೂರು ನಿಮಿಷಗಳಿಗಿಂತ ಕಡಿಮೆ ಅವಧಿಯಲ್ಲಿ ಸೆಟಪ್‌ನಿಂದ ಕಾರ್ಯಸಾಧ್ಯ ವ್ಯವಹಾರ ಒಳನೋಟಗಳನ್ನು ಪಡೆಯಿರಿ.",
        step1Num: "01",
        step1Title: "ನಿಮ್ಮ ವ್ಯವಹಾರ ಪ್ರೊಫೈಲ್ ರಚಿಸಿ",
        step1Desc: "ನಿಮ್ಮ ಮೂಲ MSME ಡೇಟಾ, ವಲಯ ಮತ್ತು ವಹಿವಾಟು ವಿವರಗಳನ್ನು ಡಿಜಿಟಲ್ ಟ್ವಿನ್ ಎಂಜಿನ್‌ಗೆ ನಮೂದಿಸಿ.",
        step2Num: "02",
        step2Title: "ನಿಮ್ಮ ವ್ಯವಹಾರವನ್ನು ತಿಳಿಯಿರಿ",
        step2Desc: "ಪ್ಲಾಟ್‌ಫಾರ್ಮ್ 8 ವಿಭಾಗಗಳಲ್ಲಿ ಆರೋಗ್ಯವನ್ನು ಮೌಲ್ಯಮಾಪನ ಮಾಡುತ್ತದೆ ಮತ್ತು ಸೂಕ್ತ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಹೊಂದಿಸುತ್ತದೆ.",
        step3Num: "03",
        step3Title: "ಬುದ್ಧಿವಂತ ಶಿಫಾರಸುಗಳ ಮೇಲೆ ಕ್ರಮ ಕೈಗೊಳ್ಳಿ",
        step3Desc: "ಆಧಾರಿತ ಸಲಹೆಗಾಗಿ AI ಸಹಾಯಕರನ್ನು ಸಂಪರ್ಕಿಸಿ, ಕ್ರಿಯಾ ಮಂಡಳಿಯಲ್ಲಿ ಕಾರ್ಯಗಳನ್ನು ನಿರ್ವಹಿಸಿ.",
      },
      finalCta: {
        title: "ನಿಮ್ಮ ವ್ಯವಹಾರದಲ್ಲಿ ಈಗಾಗಲೇ ದತ್ತಾಂಶವಿದೆ. ಈಗ ಅದನ್ನು ನಿರ್ಧಾರಗಳಾಗಿ ಪರಿವರ್ತಿಸಿ.",
        subtitle: "ನಿಮ್ಮ ವ್ಯವಹಾರದ ಸ್ಪಷ್ಟ ಚಿತ್ರಣವನ್ನು ನಿರ್ಮಿಸಿ, ಸರ್ಕಾರಿ ಅವಕಾಶಗಳನ್ನು ಅನ್ವೇಷಿಸಿ ಮತ್ತು ವಿಶ್ವಾಸದಿಂದ ಮುನ್ನಡೆಯಿರಿ.",
        ctaPrimary: "ಉಚಿತವಾಗಿ ಪ್ರಾರಂಭಿಸಿ →",
        ctaSecondary: "AI ಸಹಾಯಕ ಅನ್ವೇಷಿಸಿ →",
      },
    },
    assistant: {
      title: "UrsBiz AI ಸಹಾಯಕ",
      subtitle: "ನಿಮ್ಮ ಪರಿಶೀಲಿಸಿದ MSME ಡೇಟಾದ ಮೇಲೆ ಆಧಾರಿತ ಕಾರ್ಯತಂತ್ರದ ವ್ಯವಹಾರ ಬುದ್ಧಿಮತ್ತೆ",
      copilotBadge: "UrsBiz AI ಸಹಾಯಕ",
      onlineStatus: "ಆನ್‌ಲೈನ್ ಸಕ್ರಿಯ",
      localRuleEngine: "ಸ್ಥಳೀಯ ನಿಯಮ ಎಂಜಿನ್ ಸಕ್ರಿಯ",
      verifiedMode: "ಪರಿಶೀಲಿತ ಮೋಡ್",
      exploratoryMode: "ಅನ್ವೇಷಣಾ ಮೋಡ್",
      verifiedModeTooltip: "ಪರಿಶೀಲಿತ ವ್ಯವಹಾರ ವಿಶ್ಲೇಷಣೆ — ಡಿಜಿಟಲ್ ಟ್ವಿನ್ ಪುರಾವೆಗಳಿಗೆ ಬದ್ಧವಾದ ತಾರ್ಕಿಕತೆ.",
      exploratoryModeTooltip: "ಅನ್ವೇಷಣಾ ವ್ಯವಹಾರ ಸಲಹೆಗಾರ — ವಿಶಾಲ ಕಾರ್ಯತಂತ್ರದ ಸಮಾಲೋಚನೆ.",
      clearChat: "ಚಾಟ್ ಅಳಿಸಿ",
      refreshData: "ವಿಶ್ಲೇಷಣೆ ನವೀಕರಿಸಿ",
      searchChatsPlaceholder: "ಹಿಂದಿನ ಸಂಭಾಷಣೆ ಹುಡುಕಿ...",
      newChat: "ಹೊಸ ಸಂಭಾಷಣೆ",
      noChatsFound: "ಯಾವುದೇ ಸಂಭಾಷಣೆ ಕಂಡುಬಂದಿಲ್ಲ.",
      messagesCount: "ಸಂದೇಶಗಳು",
      composerPlaceholder: "ನಿಮ್ಮ ವ್ಯವಹಾರದ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ (ಉದಾ: 'ನಮ್ಮ ಆದಾಯದ ಗುರಿ ತಲುಪುವುದು ಹೇಗೆ?')...",
      composingPlaceholder: "ವ್ಯವಹಾರ ಪುರಾವೆಗಳನ್ನು ವಿಶ್ಲೇಷಿಸಿ ಉತ್ತರ ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ...",
      sendAria: "ಪ್ರಶ್ನೆಯನ್ನು UrsBiz AI ಗೆ ಕಳುಹಿಸಿ",
      groundedHint: "ವ್ಯವಹಾರ ಡಿಜಿಟಲ್ ಟ್ವಿನ್ ಆಧಾರಿತ",
      shortcutHint: "ಕಳುಹಿಸಲು Enter ಒತ್ತಿರಿ, ಹೊಸ ಸಾಲಿಗೆ Shift+Enter",
      followUpsTitle: "ಮುಂದಿನ ಶಿಫಾರಸು ಪ್ರಶ್ನೆಗಳು",
      suggestedTitle: "ಕಾರ್ಯತಂತ್ರದ ಪ್ರಶ್ನೆಗಳು",
      businessContextTitle: "ವ್ಯವಹಾರ ಬುದ್ಧಿಮತ್ತೆ",
      liveTwin: "ಡಿಜಿಟಲ್ ಟ್ವಿನ್",
      healthScore: "ಆರೋಗ್ಯ ಸ್ಕೋರ್",
      businessDna: "ವ್ಯವಹಾರ DNA",
      actions: "ಕ್ರಮಗಳು",
      recommendations: "ಶಿಫಾರಸುಗಳು",
      priorityActions: "ಆದ್ಯತೆ",
      roadmap: "ರೋಡ್‌ಮ್ಯಾಪ್ ಪ್ರಗತಿ",
      quickNav: "ತ್ವರಿತ ನ್ಯಾವಿಗೇಷನ್",
      backendUnreachableFallback: "ಬ್ಯಾಕೆಂಡ್ ಲಭ್ಯವಿಲ್ಲ — ಸ್ಥಳೀಯ ನಿಯಮ ಎಂಜಿನ್‌ನೊಂದಿಗೆ ಉತ್ತರಿಸಲಾಗುತ್ತಿದೆ.",
      sendFailed: "ಸಂದೇಶ ಕಳುಹಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಪುನಃ ಪ್ರಯತ್ನಿಸಿ.",
      noBusinessProfile: "ಯಾವುದೇ ವ್ಯವಹಾರ ಪ್ರೊಫೈಲ್ ಇಲ್ಲ",
      noBusinessDescription: "ನಿಜವಾದ ವ್ಯವಹಾರ ಡೇಟಾದೊಂದಿಗೆ AI ಬಳಸಲು ನಿಮ್ಮ ವ್ಯವಹಾರ ಪ್ರೊಫೈಲ್ ರಚಿಸಿ.",
      createBusinessProfile: "ಪ್ರೊಫೈಲ್ ರಚಿಸಿ",
      learnMore: "ಇನ್ನಷ್ಟು ತಿಳಿಯಿರಿ",
      goToBusiness: "ಪ್ರೊಫೈಲ್‌ಗೆ ಹೋಗಿ",
      errorLoadingTitle: "ಸಂದರ್ಭ ಲೋಡ್ ಮಾಡುವಲ್ಲಿ ದೋಷ",
      tryAgain: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
    },
    chips: {
      growthStrategy: "ಬೆಳವಣಿಗೆಯ ತಂತ್ರ",
      growthStrategyPrompt: "ನಮ್ಮ ಪ್ರಸ್ತುತ ಪ್ರೊಫೈಲ್ ಆಧರಿಸಿ ಮುಂದಿನ 12 ತಿಂಗಳುಗಳ ಅತ್ಯುತ್ತಮ ಬೆಳವಣಿಗೆಯ ತಂತ್ರವೇನು?",
      riskAnalysis: "ಅಪಾಯ ವಿಶ್ಲೇಷಣೆ",
      riskAnalysisPrompt: "ನಮ್ಮ ಪ್ರಮುಖ ವ್ಯವಹಾರ ಅಪಾಯಗಳು ಮತ್ತು ದೌರ್ಬಲ್ಯಗಳು ಯಾವುವು?",
      revenuePlanning: "ಆದಾಯ ಯೋಜನೆ",
      revenuePlanningPrompt: "ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು ಮತ್ತು ಗುರಿಯನ್ನು ತಲುಪುವುದು ಹೇಗೆ?",
      govtSchemes: "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು",
      govtSchemesPrompt: "ನನ್ನ ವ್ಯವಹಾರಕ್ಕೆ ಯಾವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಮತ್ತು ಸಬ್ಸಿಡಿಗಳು ಲಭ್ಯವಿವೆ?",
      hiringTeam: "ನೇಮಕಾತಿ ಮತ್ತು ತಂಡ",
      hiringTeamPrompt: "ನಾವು ಹೆಚ್ಚು ಉದ್ಯೋಗಿಗಳನ್ನು ನೇಮಿಸಿಕೊಳ್ಳಬೇಕೇ ಅಥವಾ ಕಾರ್ಯಾಚರಣೆ ವಿಸ್ತರಿಸಬೇಕೇ?",
      exportExpansion: "ರಫ್ತು ವಿಸ್ತರಣೆ",
      exportExpansionPrompt: "ನಮ್ಮ ವ್ಯವಹಾರವು ರಫ್ತು ಮಾರುಕಟ್ಟೆ ವಿಸ್ತರಣೆಗೆ ಸಿದ್ಧವಾಗಿದೆಯೇ?",
    },
    trust: {
      calculatedByRuleEngine: "UrsBiz ಮೂಲಕ ಲೆಕ್ಕಹಾಕಲಾಗಿದೆ",
      aiGenerated: "AI ವಿಶ್ಲೇಷಣೆ",
      fallbackResponse: "ಸ್ಥಳೀಯ ನಿಯಮ ಎಂಜಿನ್",
      evidenceBacked: "ಪರಿಶೀಲಿತ ವ್ಯವಹಾರ ಪುರಾವೆ",
      limitedData: "ಪರಿಶೀಲನೆ ಅಗತ್ಯವಿದೆ",
      openDomain: "ಸನ್ನಿವೇಶ ಅಂದಾಜು",
      whyThisAnswer: "ಈ ಉತ್ತರಕ್ಕೆ ಕಾರಣ",
      sourcesUsed: "ಬಳಸಿದ ಪುರಾವೆ ಮೂಲಗಳು",
      confidence: "ವಿಶ್ವಾಸಾರ್ಹತೆ",
      groundingScore: "ಆಧಾರಿತ ಸ್ಕೋರ್",
    },
    sections: {
      directAnswer: "ನೇರ ಉತ್ತರ",
      whatFound: "ಕಂಡುಬಂದ ಫಲಿತಾಂಶಗಳು",
      whatFoundCaption: "ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಟ್ವಿನ್‌ನಿಂದ ಪಡೆದ ಪ್ರಮುಖ ಡೇಟಾ",
      why: "ಏಕೆ ಮುಖ್ಯ",
      whyCaption: "ಕಾರ್ಯತಂತ್ರದ ಕಾರಣ ಮತ್ತು ವ್ಯವಹಾರದ ಮೇಲಿನ ಪ್ರಭಾವ",
      recommendedActions: "ಶಿಫಾರಸು ಮಾಡಿದ ಕ್ರಮಗಳು",
      recommendedActionsCaption: "ಕಾರ್ಯಗತಗೊಳಿಸಬೇಕಾದ ಹಂತಗಳು",
      scenario: "ಸನ್ನಿವೇಶ ಸಿಮ್ಯುಲೇಶನ್",
      scenarioCaption: "ನಿರೀಕ್ಷಿತ ಹಣಕಾಸು ಮತ್ತು ಕಾರ್ಯಾಚರಣೆಯ ಫಲಿತಾಂಶ",
      risks: "ಗುರುತಿಸಲಾದ ಅಪಾಯಗಳು",
      risksCaption: "ಗಮನಿಸಬೇಕಾದ ದೌರ್ಬಲ್ಯಗಳು",
      missingInfo: "ಅಗತ್ಯವಿರುವ ಮಾಹಿತಿ",
      missingInfoCaption: "ಹೆಚ್ಚಿನ ನಿಖರತೆಗೆ ಅಗತ್ಯವಿರುವ ವಿವರಗಳು",
      evidence: "ಪರಿಶೀಲಿಸಿದ ಪುರಾವೆ",
      evidenceCaption: "ಈ ಲೆಕ್ಕಾಚಾರದಲ್ಲಿ ಬಳಸಲಾದ ಡೇಟಾ",
      assumptions: "ಪ್ರಮುಖ ಊಹೆಗಳು",
      assumptionsCaption: "ಈ ವಿಶ್ಲೇಷಣೆಯ ಆಧಾರಗಳು",
      confidenceSection: "ಪರಿಶೀಲನೆ ಮತ್ತು ವಿಶ್ವಾಸ",
      confidenceCaption: "ಲೆಕ್ಕಹಾಕಿದ ವಿಶ್ವಾಸಾರ್ಹತೆಯ ಸ್ಕೋರ್",
    },
    common: {
      loading: "ಲೋಡ್ ಆಗುತ್ತಿದೆ...",
      error: "ದೋಷ ಸಂಭವಿಸಿದೆ",
      cancel: "ರದ್ದುಮಾಡಿ",
      save: "ಉಳಿಸಿ",
      delete: "ಅಳಿಸಿ",
      back: "ಹಿಂದೆ",
      copied: "ನಕಲಿಸಲಾಗಿದೆ!",
      copy: "ನಕಲಿಸಿ",
      filter: "ಫಿಲ್ಟರ್",
      all: "ಎಲ್ಲವೂ",
      search: "ಹುಡುಕಿ",
      view: "ವೀಕ್ಷಿಸಿ",
      details: "ವಿವರಗಳು",
      status: "ಸ್ಥಿತಿ",
      actions: "ಕ್ರಮಗಳು",
      confirm: "ದೃಢೀಕರಿಸಿ",
      submit: "ಸಲ್ಲಿಸಿ",
      close: "ಮುಚ್ಚಿ",
      refresh: "ನವೀಕರಿಸಿ",
      date: "ದಿನಾಂಕ",
      amount: "ಮೊತ್ತ",
      currencySymbol: "₹",
    },
    financialTerms: {
      dso: {
        label: "ವಸೂಲಾತಿ ಬಾಕಿ ದಿನಗಳು (DSO)",
        desc: "ಮಾರಾಟದ ನಂತರ ಗ್ರಾಹಕರಿಂದ ಹಣ ವಸೂಲಿ ಮಾಡಲು ಬೇಕಾಗುವ ಸರಾಸರಿ ದಿನಗಳ ಸಂಖ್ಯೆ.",
      },
      workingCapital: {
        label: "ಕಾರ್ಯನಿರತ ಬಂಡವಾಳ",
        desc: "ದೈನಂದಿನ ಕಾರ್ಯಾಚರಣೆಗೆ ಲಭ್ಯವಿರುವ ದ್ರವ್ಯತೆ (ಪ್ರಸ್ತುತ ಆಸ್ತಿಗಳು ಮೈನಸ್ ಪ್ರಸ್ತುತ ಬಾಧ್ಯತೆಗಳು).",
      },
      cashFlow: {
        label: "ನಗದು ಹರಿವು",
        desc: "ವ್ಯವಹಾರದ ಲೆಡ್ಜರ್‌ಗೆ ಒಳಬರುವ ಮತ್ತು ಹೊರಹೋಗುವ ನಗದು ನಿಧಿಗಳ ನಿವ್ವಳ ಚಲನೆ.",
      },
      grossMargin: {
        label: "ಒಟ್ಟು ಲಾಭಾಂಶ",
        desc: "ಮಾರಾಟವಾದ ಸರಕುಗಳ ವೆಚ್ಚವನ್ನು (COGS) ಕಳೆದ ನಂತರ ಉಳಿಯುವ ಆದಾಯದ ಶೇಕಡಾವಾರು ಪ್ರಮಾಣ.",
      },
      netProfit: {
        label: "ನಿವ್ವಳ ಲಾಭ",
        desc: "ಎಲ್ಲಾ ಕಾರ್ಯಾಚರಣೆಯ ವೆಚ್ಚಗಳು, ತೆರಿಗೆಗಳು ಮತ್ತು ಬಡ್ಡಿಯನ್ನು ಕಳೆದ ನಂತರ ಉಳಿಯುವ ಅಂತಿಮ ಗಳಿಕೆ.",
      },
      revenue: {
        label: "ಆದಾಯ",
        desc: "ಪರಿಶೀಲಿಸಿದ ಮಾರಾಟ ಆದೇಶಗಳು ಮತ್ತು ಇನ್‌ವಾಯ್ಸ್‌ಗಳಿಂದ ಗುರುತಿಸಲಾದ ಒಟ್ಟು ವಹಿವಾಟು.",
      },
      operatingExpenses: {
        label: "ಕಾರ್ಯಾಚರಣೆಯ ವೆಚ್ಚಗಳು (OpEx)",
        desc: "ವ್ಯವಹಾರದ ದೈನಂದಿನ ಕಾರ್ಯಾಚರಣೆಯನ್ನು ನಿರ್ವಹಿಸಲು ಅಗತ್ಯವಿರುವ ಸ್ಥಿರ ಮತ್ತು ವ್ಯತ್ಯಾಸಗೊಳ್ಳುವ ವೆಚ್ಚಗಳು.",
      },
      accountsReceivable: {
        label: "ಸ್ವೀಕರಿಸಬೇಕಾದ ಬಾಕಿ",
        desc: "ವಿತರಿಸಿದ ಸರಕುಗಳಿಗಾಗಿ ಗ್ರಾಹಕರಿಂದ ವ್ಯವಹಾರಕ್ಕೆ ಕಾನೂನುಬದ್ಧವಾಗಿ ಬರಬೇಕಾದ ಬಾಕಿ ಪಾವತಿಗಳು.",
      },
      accountsPayable: {
        label: "ಪಾವತಿಸಬೇಕಾದ ಬಾಕಿ",
        desc: "ಸರಬರಾಜುದಾರರಿಗೆ ಮತ್ತು ಮಾರಾಟಗಾರರಿಗೆ ವ್ಯವಹಾರವು ಪಾವತಿಸಬೇಕಾದ ಬಾಕಿ ಹೊಣೆಗಾರಿಕೆಗಳು.",
      },
      inventoryTurnover: {
        label: "ದಾಸ್ತಾನು ವಹಿವಾಟು ದರ",
        desc: "ಪ್ರಮಾಣಿತ ಕಾರ್ಯಾಚರಣಾ ಚಕ್ರದಲ್ಲಿ ಭೌತಿಕ ಸ್ಟಾಕ್ ಮಾರಾಟವಾಗಿ ಮರುಪೂರಣಗೊಳ್ಳುವ ದರ.",
      },
      burnRate: {
        label: "ಮಾಸಿಕ ನಗದು ವೆಚ್ಚ ದರ",
        desc: "ಕಾರ್ಯಾಚರಣೆಯ ವೆಚ್ಚಗಳು ವಸೂಲಾತಿಯನ್ನು ಮೀರಿದಾಗ ನಗದು ಮೀಸಲು ಖಾಲಿಯಾಗುವ ಮಾಸಿಕ ದರ.",
      },
      customerConcentration: {
        label: "ಗ್ರಾಹಕರ ಸಾಂದ್ರತೆ",
        desc: "ಪ್ರಮುಖ ಖರೀದಿದಾರರಿಂದ ಬರುವ ಆದಾಯದ ಪಾಲು (ರಚನಾತ್ಮಕ ಆದಾಯದ ಅಪಾಯವನ್ನು ಸೂಚಿಸುತ್ತದೆ).",
      },
      cashRunway: {
        label: "ನಗದು ಜೀವಿತಾವಧಿ",
        desc: "ಲಭ್ಯವಿರುವ ನಗದು ಮೀಸಲು ಮತ್ತು ಮಾಸಿಕ ವೆಚ್ಚ ದರದ ಆಧಾರದ ಮೇಲೆ ಅಂದಾಜು ಉಳಿವಿನ ತಿಂಗಳುಗಳು.",
      },
    },
    roles: {
      owner: "ಮಾಲೀಕ",
      administrator: "ನಿರ್ವಾಹಕ",
      manager: "ವ್ಯವಸ್ಥಾಪಕ",
      analyst: "ವಿಶ್ಲೇಷಕ",
      viewer: "ವೀಕ್ಷಕ",
    },
    decisions: {
      draft: "ಕರಡು",
      proposed: "ಪ್ರಸ್ತಾಪಿತ",
      pendingApproval: "ಅನುಮೋದನೆ ಬಾಕಿ",
      approved: "ಅನುಮೋದಿತ",
      rejected: "ತಿರಸ್ಕೃತ",
      executed: "ಕಾರ್ಯಗತಗೊಳಿಸಲಾಗಿದೆ",
      cancelled: "ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ",
      newDecision: "ಹೊಸ ನಿರ್ಧಾರ",
      requestApproval: "ಅನುಮೋದನೆ ಕೋರಿ",
      approve: "ಅನುಮೋದಿಸಿ",
      reject: "ತಿರಸ್ಕರಿಸಿ",
      soleOwnerAutoApproved: "ಏಕಮಾತ್ರ ಮಾಲೀಕ — ಸ್ವಯಂ ಅನುಮೋದಿತ",
    },
    feedbackEvaluation: {
      helpful: "ಸಹಾಯಕ",
      incorrectInformation: "ತಪ್ಪಾದ ಮಾಹಿತಿ",
      missingEvidence: "ಪುರಾವೆ ಕೊರತೆ",
      outdatedData: "ಹಳೆಯ ಡೇಟಾ",
      difficultToUnderstand: "ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಕಷ್ಟ",
      qualityScore: "ಗುಣಮಟ್ಟದ ಸ್ಕೋರ್",
      helpfulnessRate: "ಸಹಾಯಕತೆಯ ಪ್ರಮಾಣ",
      totalFeedback: "ಒಟ್ಟು ಪ್ರತಿಕ್ರಿಯೆಗಳು",
      groundedVsFallback: "ಆಧಾರಿತ vs ನಿಯಮ ಎಂಜಿನ್ ಟೆಲಿಮೆಟ್ರಿ",
      groundedAnswers: "ಆಧಾರಿತ ಉತ್ತರಗಳು",
      ruleFallbacks: "ನಿಯಮ ಎಂಜಿನ್ ಉತ್ತರಗಳು",
      unclassified: "ವರ್ಗೀಕರಿಸದ",
      zeroRetention: "ಶೂನ್ಯ-ಧಾರಣ ದತ್ತಾಂಶ ಸಾರ್ವಭೌಮತ್ವ",
      unvote: "ಪ್ರತಿಕ್ರಿಯೆ ತೆಗೆದುಹಾಕಿ",
    },
    goalsTracker: {
      title: "ವ್ಯವಹಾರ ಗುರಿಗಳು ಮತ್ತು ಪ್ರಗತಿ ಟ್ರ್ಯಾಕರ್",
      activeGoals: "ಸಕ್ರಿಯ ಗುರಿಗಳು",
      targetValue: "ಗುರಿ ಮೌಲ್ಯ",
      currentValue: "ಪ್ರಸ್ತುತ ಮೌಲ್ಯ",
      deadline: "ಅಂತಿಮ ಗಡುವು",
      milestones: "ಮೈಲಿಗಲ್ಲುಗಳು",
      onTrack: "ಸರಿಯಾದ ಹಾದಿಯಲ್ಲಿದೆ",
      atRisk: "ಅಪಾಯದಲ್ಲಿದೆ",
      behind: "ಹಿಂದುಳಿದಿದೆ",
      achieved: "ಸಾಧಿಸಲಾಗಿದೆ",
    },
    reportsExport: {
      title: "ವರದಿಗಳು ಮತ್ತು ಪುರಾವೆ ರಫ್ತು ಕೇಂದ್ರ",
      exportReport: "ವರದಿ ರಫ್ತು ಮಾಡಿ",
      downloadPdf: "PDF ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
      downloadCsv: "CSV ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
      downloadXlsx: "Excel ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ",
      auditPackage: "ಆಡಿಟ್ ಪುರಾವೆ ಪ್ಯಾಕೇಜ್",
      checksum: "SHA-256 ಚೆಕ್‌ಸಮ್",
    },
    connectors: {
      title: "ಸಂಯೋಜನೆಗಳು ಮತ್ತು ಕನೆಕ್ಟರ್‌ಗಳು",
      tallyPrime: "ಟ್ಯಾಲಿ ಪ್ರೈಮ್ ಇಆರ್‌ಪಿ",
      zohoBooks: "ಜೋಹೋ ಬುಕ್ಸ್",
      manualLedger: "ಮ್ಯಾನುಯಲ್ ಲೆಡ್ಜರ್ ಅಪ್‌ಲೋಡ್",
      syncStatus: "ಸಿಂಕ್ ಸ್ಥಿತಿ",
      connected: "ಸಂಪರ್ಕಗೊಂಡಿದೆ",
      inactive: "ನಿಷ್ಕ್ರಿಯ",
      beta: "ಬೀಟಾ",
      lastSync: "ಕೊನೆಯ ಸಿಂಕ್",
    },
    a11y: {
      skipToContent: "ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ತೆರಳಿ",
      openNavigation: "ನ್ಯಾವಿಗೇಷನ್ ಮೆನು ತೆರೆಯಿರಿ",
      closeNavigation: "ನ್ಯಾವಿಗೇಷನ್ ಮೆನು ಮುಚ್ಚಿ",
      toggleTheme: "ಬಣ್ಣದ ಥೀಮ್ ಬದಲಾಯಿಸಿ",
      languageSelect: "ಇಂಟರ್ಫೇಸ್ ಭಾಷೆಯನ್ನು ಬದಲಾಯಿಸಿ",
      currentLanguage: "ಪ್ರಸ್ತುತ ಭಾಷೆ: ಕನ್ನಡ",
      externalLink: "(ಹೊಸ ವಿಂಡೋದಲ್ಲಿ ತೆರೆಯುತ್ತದೆ)",
      breadcrumb: "ಬ್ರೆಡ್‌ಕ್ರಂಬ್ ನ್ಯಾವಿಗೇಷನ್",
      loadingState: "ವಿಷಯ ಲೋಡ್ ಆಗುತ್ತಿದೆ, ದಯವಿಟ್ಟು ಕಾಯಿರಿ...",
    },
  },
};
