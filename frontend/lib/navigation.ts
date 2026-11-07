import {
  LayoutDashboard,
  Building2,
  KanbanSquare,
  Sparkles,
  BarChart3,
  FileText,
  Lightbulb,
  Bell,
  TrendingUp,
  Bot,
  Compass,
  Landmark,
  Activity,
  Home,
  ShoppingBag,
  Scale,
  Sliders,
  ShieldCheck,
  BookOpen,
  Target,
  Users,
  Plug,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavLink {
  href: string;
  label: string;
  labelKey?: string;
  icon: LucideIcon;
  /** Badge text (e.g., 'AI', 'NEW', count). */
  badge?: string;
  badgeKey?: string;
  /** Whether the badge should have a glowing neon style. */
  neonBadge?: boolean;
  /** Hidden from main navigation (still routable). */
  hidden?: boolean;
}

export interface NavGroup {
  id: string;
  label: string;
  labelKey?: string;
  links: NavLink[];
}

/**
 * Categorized Navigation Groups conforming to the Phase 1 UI redesign specification
 * and Phase 6.29 bilingual localization standard.
 */
export const navGroups: NavGroup[] = [
  {
    id: "overview",
    label: "Overview",
    labelKey: "nav.groupOverview",
    links: [
      {
        href: "/dashboard",
        label: "Dashboard",
        labelKey: "nav.dashboard",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    id: "business",
    label: "Business",
    labelKey: "nav.groupBusiness",
    links: [
      {
        href: "/business",
        label: "Business Profile",
        labelKey: "nav.business",
        icon: Building2,
      },
      {
        href: "/intelligence",
        label: "Health Score",
        labelKey: "nav.intelligence",
        icon: Activity,
      },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence",
    labelKey: "nav.groupIntelligence",
    links: [
      {
        href: "/sales",
        label: "Sales Intelligence",
        labelKey: "nav.sales",
        icon: ShoppingBag,
      },
      {
        href: "/analytics",
        label: "Analytics",
        labelKey: "nav.analytics",
        icon: BarChart3,
      },
      {
        href: "/predictive-analytics",
        label: "Forecasts",
        labelKey: "nav.predictiveAnalytics",
        icon: TrendingUp,
      },
      {
        href: "/insights",
        label: "Insights",
        labelKey: "nav.insights",
        icon: Lightbulb,
      },
      {
        href: "/data-confidence",
        label: "Data Confidence",
        labelKey: "nav.dataConfidence",
        icon: ShieldCheck,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
      {
        href: "/metrics",
        label: "Metrics Dictionary",
        labelKey: "nav.metrics",
        icon: BookOpen,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
    ],
  },
  {
    id: "actions",
    label: "Actions",
    labelKey: "nav.groupActions",
    links: [
      {
        href: "/advisor",
        label: "AI Advisor",
        labelKey: "nav.advisor",
        icon: Compass,
      },
      {
        href: "/action-board",
        label: "Recommendations",
        labelKey: "nav.actionBoard",
        icon: KanbanSquare,
      },
      {
        href: "/decision-workbench",
        label: "Decision Workbench",
        labelKey: "nav.decisionWorkbench",
        icon: Scale,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
      {
        href: "/what-if",
        label: "What-If Simulator",
        labelKey: "nav.whatIf",
        icon: Sliders,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
      {
        href: "/goals",
        label: "Business Goals",
        labelKey: "nav.goals",
        icon: Target,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
    ],
  },
  {
    id: "discover",
    label: "Discover",
    labelKey: "nav.groupDiscover",
    links: [
      {
        href: "/schemes",
        label: "Government Schemes",
        labelKey: "nav.schemes",
        icon: Landmark,
      },
    ],
  },
  {
    id: "assistant",
    label: "Assistant",
    labelKey: "nav.groupAssistant",
    links: [
      {
        href: "/assistant",
        label: "AI Business Assistant",
        labelKey: "nav.assistant",
        icon: Bot,
        badge: "AI",
        badgeKey: "nav.badgeAi",
        neonBadge: true,
      },
    ],
  },
  {
    id: "workspace",
    label: "Workspace",
    labelKey: "nav.groupWorkspace",
    links: [
      {
        href: "/reports",
        label: "Reports",
        labelKey: "nav.reports",
        icon: FileText,
      },
      {
        href: "/collaboration",
        label: "Team & Approvals",
        labelKey: "nav.collaboration",
        icon: Users,
        badge: "RBAC",
        badgeKey: "nav.badgeRbac",
        neonBadge: true,
      },
      {
        href: "/integrations",
        label: "Integrations",
        labelKey: "nav.integrations",
        icon: Plug,
        badge: "NEW",
        badgeKey: "nav.badgeNew",
        neonBadge: true,
      },
      {
        href: "/notifications",
        label: "Notifications",
        labelKey: "nav.notifications",
        icon: Bell,
      },
    ],
  },
];

/** Flattened main navigation list for backwards compatibility */
export const mainNavLinks: NavLink[] = [
  { href: "/", label: "Home", labelKey: "nav.home", icon: Home },
  { href: "/dashboard", label: "Dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/business", label: "Business Profile", labelKey: "nav.business", icon: Building2 },
  { href: "/intelligence", label: "Health Score", labelKey: "nav.intelligence", icon: Activity },
  { href: "/sales", label: "Sales Intelligence", labelKey: "nav.sales", icon: ShoppingBag },
  { href: "/analytics", label: "Analytics", labelKey: "nav.analytics", icon: BarChart3 },
  { href: "/predictive-analytics", label: "Forecasts", labelKey: "nav.predictiveAnalytics", icon: TrendingUp },
  { href: "/insights", label: "Insights", labelKey: "nav.insights", icon: Lightbulb },
  { href: "/data-confidence", label: "Data Confidence", labelKey: "nav.dataConfidence", icon: ShieldCheck, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/metrics", label: "Metrics Dictionary", labelKey: "nav.metrics", icon: BookOpen, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/advisor", label: "AI Advisor", labelKey: "nav.advisor", icon: Compass },
  { href: "/action-board", label: "Recommendations", labelKey: "nav.actionBoard", icon: KanbanSquare },
  { href: "/decision-workbench", label: "Decision Workbench", labelKey: "nav.decisionWorkbench", icon: Scale, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/what-if", label: "What-If Simulator", labelKey: "nav.whatIf", icon: Sliders, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/goals", label: "Business Goals", labelKey: "nav.goals", icon: Target, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/schemes", label: "Government Schemes", labelKey: "nav.schemes", icon: Landmark },
  { href: "/assistant", label: "AI Business Assistant", labelKey: "nav.assistant", icon: Bot, badge: "AI", badgeKey: "nav.badgeAi", neonBadge: true },
  { href: "/reports", label: "Reports", labelKey: "nav.reports", icon: FileText },
  { href: "/collaboration", label: "Team & Approvals", labelKey: "nav.collaboration", icon: Users, badge: "RBAC", badgeKey: "nav.badgeRbac", neonBadge: true },
  { href: "/integrations", label: "Integrations", labelKey: "nav.integrations", icon: Plug, badge: "NEW", badgeKey: "nav.badgeNew", neonBadge: true },
  { href: "/notifications", label: "Notifications", labelKey: "nav.notifications", icon: Bell },
];

export const marketingLinks: NavLink[] = [
  { href: "/", label: "Product", labelKey: "nav.home", icon: Sparkles, hidden: true },
];

export function isActiveLink(currentPath: string, linkHref: string): boolean {
  if (linkHref === "/") {
    return currentPath === "/";
  }
  return currentPath === linkHref || currentPath.startsWith(`${linkHref}/`);
}
