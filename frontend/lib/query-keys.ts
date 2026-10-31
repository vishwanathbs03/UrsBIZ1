/**
 * Centralised TanStack Query keys for the dashboard's
 * five upstream payloads plus the action-board pair.
 *
 * Why centralise: when we add mutation / invalidation
 * later ("Refresh" button → invalidate these), having one
 * source of truth prevents drift between the keys used
 * to read and the keys used to invalidate.
 */

export const queryKeys = {
  // Per-business analytical payloads.
  intelligence: () => ["business", "intelligence"] as const,
  scores: () => ["business", "scores"] as const,
  dna: () => ["business", "dna"] as const,
  rules: () => ["business", "rules"] as const,
  decision: () => ["business", "decision"] as const,
  // The bundled "dashboard" namespace — handy for the
  // "Refresh" button which invalidates everything at once.
  dashboardAll: () => ["business", "dashboard"] as const,
  actionBoardAll: () => ["business", "action-board"] as const,
  // Analytics page payloads.
  twin: () => ["business", "twin"] as const,
  roadmap: () => ["business", "roadmap"] as const,
  recommendations: () => ["business", "recommendations"] as const,
  analyticsAll: () => ["business", "analytics"] as const,
  // Advisor (Sprint 7 Part 5 & Sprint 12).
  advisor: () => ["business", "advisor"] as const,
  advisorAggregate: () => ["business", "advisor-aggregate"] as const,
  // Business Digital Twin profile (Sprint 8 — business CRUD hook).
  business: () => ["business", "profile"] as const,
  // Sprint 23 — every business the user owns (the profile panel
  // primary data source). Invalidated on add / delete / switch
  // because the list shape and the active id both change.
  businesses: () => ["business", "list"] as const,
};
