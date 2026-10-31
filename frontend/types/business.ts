/**
 * TypeScript types for the Business Digital Twin payload.
 *
 * Mirrors the Pydantic schemas in `backend/app/schemas/business.py`
 * 1:1 — field names, types, and Literal unions match the wire format
 * so the service modules can hand the parsed JSON straight through.
 *
 * Snake_case field names are preserved (per project convention).
 * Optional scalars use `string | null` (not `string | undefined`).
 */

// --------------------------------------------------------------------------- //
// Enums / Literal unions
// --------------------------------------------------------------------------- //

export type BusinessType =
  | "sole_proprietorship"
  | "partnership"
  | "llc"
  | "private_limited"
  | "public_limited"
  | "cooperative"
  | "other";

export type PriorityLevel = "low" | "medium" | "high";

export type SeverityLevel = "low" | "medium" | "high" | "critical";

export type ProfileStatus = "draft" | "in_progress" | "complete";

export type CompletenessSection =
  | "basic"
  | "products"
  | "capacity"
  | "digital_presence"
  | "compliance"
  | "export_history"
  | "goals"
  | "challenges";

// --------------------------------------------------------------------------- //
// Section 1 — Basic information
// --------------------------------------------------------------------------- //

export interface BasicSection {
  legal_name: string;
  trade_name: string | null;
  industry: string;
  sub_industry: string | null;
  business_type: BusinessType | null;
  established_year: number;
  employee_count: number;
  annual_revenue: number;
  revenue_currency: string;
  description: string | null;
  country: string | null;
  state_region: string | null;
  city: string | null;
}

// --------------------------------------------------------------------------- //
// Section 2 — Products
// --------------------------------------------------------------------------- //

export interface Product {
  id: number;
  business_id: number;
  name: string;
  category: string | null;
  hs_code: string | null;
  description: string | null;
  unit_price: number | null;
  currency: string;
  monthly_volume: number | null;
  is_exported: boolean;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Section 3 — Capacity
// --------------------------------------------------------------------------- //

export interface CapacitySection {
  production_capacity: string | null;
  production_capacity_unit: string | null;
  capacity_utilization_pct: number | null;
  monthly_production_units: number | null;
}

// --------------------------------------------------------------------------- //
// Section 4 — Digital presence
// --------------------------------------------------------------------------- //

export interface DigitalPresence {
  id: number;
  business_id: number;
  website_url: string | null;
  linkedin_url: string | null;
  facebook_url: string | null;
  instagram_url: string | null;
  twitter_url: string | null;
  youtube_url: string | null;
  has_ecommerce: boolean;
  ecommerce_platform: string | null;
  uses_digital_marketing: boolean;
  uses_cloud_systems: boolean;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Section 5 — Certifications
// --------------------------------------------------------------------------- //

export interface Certification {
  id: number;
  business_id: number;
  name: string;
  issuing_body: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  certificate_number: string | null;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Section 6 — Export history
// --------------------------------------------------------------------------- //

export interface ExportHistory {
  id: number;
  business_id: number;
  destination_country: string;
  product_category: string | null;
  first_export_date: string | null;
  annual_export_value: number | null;
  currency: string;
  iec_number: string | null;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Section 7 — Business goals
// --------------------------------------------------------------------------- //

export interface BusinessGoal {
  id: number;
  business_id: number;
  title: string;
  description: string | null;
  timeframe: string | null;
  priority: PriorityLevel;
  target_date: string | null;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Section 8 — Business challenges
// --------------------------------------------------------------------------- //

export interface BusinessChallenge {
  id: number;
  business_id: number;
  title: string;
  description: string | null;
  severity: SeverityLevel;
  category: string | null;
  created_at: string;
  updated_at: string;
}

// --------------------------------------------------------------------------- //
// Full business tree
// --------------------------------------------------------------------------- //

export interface BusinessOut {
  id: number;
  owner_id: number;
  legal_name: string;
  trade_name: string | null;
  industry: string;
  sub_industry: string | null;
  business_type: string | null;
  established_year: number;
  employee_count: number;
  annual_revenue: number;
  revenue_currency: string;
  description: string | null;
  country: string | null;
  state_region: string | null;
  city: string | null;
  production_capacity: string | null;
  production_capacity_unit: string | null;
  capacity_utilization_pct: number | null;
  monthly_production_units: number | null;
  is_completed: boolean;
  created_at: string;
  updated_at: string;
  products: Product[];
  certifications: Certification[];
  digital_presence: DigitalPresence | null;
  export_history: ExportHistory[];
  goals: BusinessGoal[];
  challenges: BusinessChallenge[];
}

// --------------------------------------------------------------------------- //
// Aggregate payload — POST /business
// --------------------------------------------------------------------------- //

export interface BusinessCreate {
  basic: BasicSection;
  capacity: CapacitySection | null;
  products: ProductCreate[];
  digital_presence: DigitalPresenceCreate | null;
  certifications: CertificationCreate[];
  export_history: ExportHistoryCreate[];
  goals: BusinessGoalCreate[];
  challenges: BusinessChallengeCreate[];
}

// --------------------------------------------------------------------------- //
// Partial update — PUT /business
// --------------------------------------------------------------------------- //

export interface BusinessUpdate {
  basic: BasicSection | null;
  capacity: CapacitySection | null;
  products: ProductCreate[] | null;
  digital_presence: DigitalPresenceCreate | null;
  certifications: CertificationCreate[] | null;
  export_history: ExportHistoryCreate[] | null;
  goals: BusinessGoalCreate[] | null;
  challenges: BusinessChallengeCreate[] | null;
}

// --------------------------------------------------------------------------- //
// Create-only shapes for nested collections
// --------------------------------------------------------------------------- //

export interface ProductCreate {
  name: string;
  category: string | null;
  hs_code: string | null;
  description: string | null;
  unit_price: number | null;
  currency: string;
  monthly_volume: number | null;
  is_exported: boolean;
}

export interface DigitalPresenceCreate {
  website_url: string | null;
  linkedin_url: string | null;
  facebook_url: string | null;
  instagram_url: string | null;
  twitter_url: string | null;
  youtube_url: string | null;
  has_ecommerce: boolean;
  ecommerce_platform: string | null;
  uses_digital_marketing: boolean;
  uses_cloud_systems: boolean;
}

export interface CertificationCreate {
  name: string;
  issuing_body: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  certificate_number: string | null;
}

export interface ExportHistoryCreate {
  destination_country: string;
  product_category: string | null;
  first_export_date: string | null;
  annual_export_value: number | null;
  currency: string;
  iec_number: string | null;
}

export interface BusinessGoalCreate {
  title: string;
  description: string | null;
  timeframe: string | null;
  priority: PriorityLevel;
  target_date: string | null;
}

export interface BusinessChallengeCreate {
  title: string;
  description: string | null;
  severity: SeverityLevel;
  category: string | null;
}

// --------------------------------------------------------------------------- //
// Profile completeness
// --------------------------------------------------------------------------- //

export interface CompletenessMissingField {
  section: CompletenessSection;
  field: string;
  label: string;
}

export interface ProfileCompleteness {
  score: number;
  completed: boolean;
  total_fields: number;
  completed_fields: number;
  missing: CompletenessMissingField[];
}

export interface BusinessMeta {
  profile_completion: number;
  profile_status: ProfileStatus;
  last_updated: string;
}

// --------------------------------------------------------------------------- //
// Envelope returned by GET /business
// --------------------------------------------------------------------------- //

export interface BusinessWithCompleteness {
  business: BusinessOut;
  completeness: ProfileCompleteness;
  meta: BusinessMeta;
}

export interface BusinessSummary {
  id: number;
  legal_name: string;
  industry: string;
  country: string | null;
  annual_revenue: number;
  revenue_currency: string;
  is_completed: boolean;
  updated_at: string;
}

export interface DeleteResponse {
  detail: string;
  id: number;
}

// --------------------------------------------------------------------------- //
// Sprint 23 — profile panel shapes
// --------------------------------------------------------------------------- //

/**
 * Lightweight card returned by ``GET /business/list``. Mirrors
 * the backend ``BusinessListItem`` Pydantic schema. The panel
 * uses this to render the per-row Switch / Delete affordances.
 */
export interface BusinessListItem {
  id: number;
  legal_name: string;
  trade_name: string | null;
  industry: string;
  city: string | null;
  is_completed: boolean;
  created_at: string;
}

/** Envelope returned by ``GET /business/list``. */
export interface BusinessListResponse {
  items: BusinessListItem[];
  /** Convenience copy of the user's active business id (also on User). */
  active_business_id: number | null;
  count: number;
}

/**
 * Inline 'Add a business' form payload — only the six required
 * fields of the wizard's ``BasicSection``. The remaining 7
 * sections are filled out on the regular ``/business`` wizard.
 */
export interface BusinessMinimalCreate {
  legal_name: string;
  industry: string;
  established_year: number;
  employee_count: number;
  annual_revenue: number;
  revenue_currency: string;
}
