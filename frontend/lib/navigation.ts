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
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavLink {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Badge text (e.g., 'AI', 'NEW', count). */
  badge?: string;
  /** Whether the badge should have a glowing neon style. */
  neonBadge?: boolean;
  /** Hidden from main navigation (still routable). */
  hidden?: boolean;
}

export interface NavGroup {
  id: string;
  label: string;
  links: NavLink[];
}

/**
 * Categorized Navigation Groups conforming to the Phase 1 UI redesign specification.
 */
export const navGroups: NavGroup[] = [
  {
    id: "overview",
    label: "Overview",
    links: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    id: "business",
    label: "Business",
    links: [
      { href: "/business", label: "Business Profile", icon: Building2 },
      { href: "/intelligence", label: "Health Score", icon: Activity },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence",
    links: [
      { href: "/sales", label: "Sales Intelligence", icon: ShoppingBag, badge: "NEW", neonBadge: true },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/predictive-analytics", label: "Forecasts", icon: TrendingUp },
      { href: "/insights", label: "Insights", icon: Lightbulb },
    ],
  },
  {
    id: "actions",
    label: "Actions",
    links: [
      { href: "/advisor", label: "AI Advisor", icon: Compass },
      { href: "/action-board", label: "Recommendations", icon: KanbanSquare },
    ],
  },
  {
    id: "discover",
    label: "Discover",
    links: [{ href: "/schemes", label: "Government Schemes", icon: Landmark }],
  },
  {
    id: "assistant",
    label: "Assistant",
    links: [
      {
        href: "/assistant",
        label: "AI Business Assistant",
        icon: Bot,
        badge: "AI",
        neonBadge: true,
      },
    ],
  },
  {
    id: "workspace",
    label: "Workspace",
    links: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/notifications", label: "Notifications", icon: Bell },
    ],
  },
];

/** Flattened main navigation list for backwards compatibility */
export const mainNavLinks: NavLink[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/business", label: "Business Profile", icon: Building2 },
  { href: "/intelligence", label: "Health Score", icon: Activity },
  { href: "/sales", label: "Sales Intelligence", icon: ShoppingBag, badge: "NEW", neonBadge: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/predictive-analytics", label: "Forecasts", icon: TrendingUp },
  { href: "/insights", label: "Insights", icon: Lightbulb },
  { href: "/advisor", label: "AI Advisor", icon: Compass },
  { href: "/action-board", label: "Recommendations", icon: KanbanSquare },
  { href: "/schemes", label: "Government Schemes", icon: Landmark },
  { href: "/assistant", label: "AI Business Assistant", icon: Bot, badge: "AI", neonBadge: true },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/notifications", label: "Notifications", icon: Bell },
];

export const marketingLinks: NavLink[] = [
  { href: "/", label: "Product", icon: Sparkles, hidden: true },
];

export function isActiveLink(currentPath: string, linkHref: string): boolean {
  if (linkHref === "/") {
    return currentPath === "/";
  }
  return currentPath === linkHref || currentPath.startsWith(`${linkHref}/`);
}
