/**
 * BusinessWizard — multi-step creation flow for the Business Digital Twin.
 *
 * Steps (matches `app/schemas/business.py` section ordering):
 *   1. Basic Info          (BasicSection — required)
 *   2. Capacity            (CapacitySection — optional)
 *   3. Products            (ProductCreate[] — optional, 0+)
 *   4. Digital Presence    (DigitalPresenceCreate | null — optional)
 *   5. Certifications      (CertificationCreate[] — optional, 0+)
 *   6. Export History      (ExportHistoryCreate[] — optional, 0+)
 *   7. Goals               (BusinessGoalCreate[] — optional, 0+)
 *   8. Challenges          (BusinessChallengeCreate[] — optional, 0+)
 *   9. Review              (read-only summary + final submit)
 *
 * Submits the assembled payload through `useCreateBusiness()`. On success
 * the mutation invalidates the `["business"]` query namespace, so every
 * analytics surface re-fetches against the freshly persisted Business row.
 *
 * This component owns state, layout, and validation. It does NOT touch
 * routing — the parent decides when to mount it.
 */

"use client";

import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CircleAlert,
  Factory,
  Globe2,
  Lightbulb,
  Package,
  Send,
  ShieldCheck,
  Target,
  TrendingUp,
} from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { ApiError } from "@/services/api-client";
import { useCreateBusiness } from "./use-business-data";
import type {
  BasicSection,
  BusinessChallengeCreate,
  BusinessCreate,
  BusinessGoalCreate,
  BusinessType,
  CapacitySection,
  CertificationCreate,
  DigitalPresenceCreate,
  ExportHistoryCreate,
  ProductCreate,
} from "@/types/business";
import { cn } from "@/lib/utils";

// --------------------------------------------------------------------------- //
// Step definitions
// --------------------------------------------------------------------------- //

interface StepDef {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;
}

const STEPS: StepDef[] = [
  { key: "basic",     label: "Basic Info",       icon: Building2  },
  { key: "capacity",  label: "Capacity",         icon: Factory    },
  { key: "products",  label: "Products",         icon: Package    },
  { key: "presence",  label: "Digital Presence", icon: Globe2     },
  { key: "certs",     label: "Certifications",   icon: ShieldCheck},
  { key: "exports",   label: "Export History",   icon: TrendingUp },
  { key: "goals",     label: "Goals",            icon: Target     },
  { key: "challenges",label: "Challenges",       icon: CircleAlert},
  { key: "review",    label: "Review",           icon: Lightbulb  },
];

// --------------------------------------------------------------------------- //
// Local wizard state — a single draft object that becomes the POST body
// --------------------------------------------------------------------------- //

interface DraftState {
  basic: BasicSection;
  capacity: CapacitySection;
  products: ProductCreate[];
  presence: DigitalPresenceCreate;
  certs: CertificationCreate[];
  exports: ExportHistoryCreate[];
  goals: BusinessGoalCreate[];
  challenges: BusinessChallengeCreate[];
}

const BUSINESS_TYPES: { value: BusinessType; label: string }[] = [
  { value: "sole_proprietorship", label: "Sole proprietorship" },
  { value: "partnership",         label: "Partnership" },
  { value: "llc",                 label: "LLC" },
  { value: "private_limited",     label: "Private limited" },
  { value: "public_limited",      label: "Public limited" },
  { value: "cooperative",         label: "Cooperative" },
  { value: "other",               label: "Other" },
];

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "CNY", "AUD", "CAD"];

const currentYear = new Date().getFullYear();

function emptyDraft(): DraftState {
  return {
    basic: {
      legal_name: "",
      trade_name: null,
      industry: "",
      sub_industry: null,
      business_type: null,
      established_year: currentYear,
      employee_count: 0,
      annual_revenue: 0,
      revenue_currency: "USD",
      description: null,
      country: null,
      state_region: null,
      city: null,
    },
    capacity: {
      production_capacity: null,
      production_capacity_unit: null,
      capacity_utilization_pct: null,
      monthly_production_units: null,
    },
    products: [],
    presence: {
      website_url: null,
      linkedin_url: null,
      facebook_url: null,
      instagram_url: null,
      twitter_url: null,
      youtube_url: null,
      has_ecommerce: false,
      ecommerce_platform: null,
      uses_digital_marketing: false,
      uses_cloud_systems: false,
    },
    certs: [],
    exports: [],
    goals: [],
    challenges: [],
  };
}

// --------------------------------------------------------------------------- //
// Top-level wizard
// --------------------------------------------------------------------------- //

export function BusinessWizard() {
  // Dev-only render trace — stripped from production bundles.
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.log("[BUSWIZ] render");
  }
  const [stepIndex, setStepIndex] = useState(0);
  const [draft, setDraft] = useState<DraftState>(emptyDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const create = useCreateBusiness();

  const step = STEPS[stepIndex]!;
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === STEPS.length - 1;

  const updateBasic = (patch: Partial<BasicSection>) =>
    setDraft((d) => ({ ...d, basic: { ...d.basic, ...patch } }));
  const updateCapacity = (patch: Partial<CapacitySection>) =>
    setDraft((d) => ({ ...d, capacity: { ...d.capacity, ...patch } }));
  const updatePresence = (patch: Partial<DigitalPresenceCreate>) =>
    setDraft((d) => ({ ...d, presence: { ...d.presence, ...patch } }));

  // ---- Per-step validation ----
  const validateStep = (idx: number): boolean => {
    const next: Record<string, string> = { ...errors };
    delete next.__form;

    if (idx === 0) {
      const b = draft.basic;
      if (!b.legal_name.trim()) next.legal_name = "Business name is required.";
      else delete next.legal_name;
      if (!b.industry.trim()) next.industry = "Industry is required.";
      else delete next.industry;
      if (b.established_year < 1800 || b.established_year > currentYear)
        next.established_year = `Year must be between 1800 and ${currentYear}.`;
      else delete next.established_year;
      if (b.employee_count < 0) next.employee_count = "Must be 0 or more.";
      else delete next.employee_count;
      if (b.annual_revenue < 0) next.annual_revenue = "Must be 0 or more.";
      else delete next.annual_revenue;
    }
    setErrors(next);
    return !next.legal_name && !next.industry && !next.established_year
        && !next.employee_count && !next.annual_revenue;
  };

  const goNext = () => {
    setServerError(null);
    if (!isLast && !validateStep(stepIndex)) return;
    if (!isLast) setStepIndex((i) => i + 1);
  };
  const goBack = () => {
    setServerError(null);
    if (!isFirst) setStepIndex((i) => i - 1);
  };

  const buildPayload = (): BusinessCreate => ({
    basic: draft.basic,
    capacity:
      draft.capacity.production_capacity ||
      draft.capacity.production_capacity_unit ||
      draft.capacity.capacity_utilization_pct !== null ||
      draft.capacity.monthly_production_units !== null
        ? draft.capacity
        : null,
    products: draft.products.filter((p) => p.name.trim().length > 0),
    digital_presence:
      draft.presence.website_url ||
      draft.presence.linkedin_url ||
      draft.presence.facebook_url ||
      draft.presence.instagram_url ||
      draft.presence.twitter_url ||
      draft.presence.youtube_url ||
      draft.presence.has_ecommerce ||
      draft.presence.ecommerce_platform ||
      draft.presence.uses_digital_marketing ||
      draft.presence.uses_cloud_systems
        ? draft.presence
        : null,
    certifications: draft.certs.filter((c) => c.name.trim().length > 0),
    export_history: draft.exports.filter((e) => e.destination_country.trim().length > 0),
    goals: draft.goals.filter((g) => g.title.trim().length > 0),
    challenges: draft.challenges.filter((c) => c.title.trim().length > 0),
  });

  const onSubmit = () => {
    setServerError(null);
    const payload = buildPayload();
    create.mutate(payload, {
      onSuccess: () => setSuccess(true),
      onError: (err) => {
        if (err instanceof ApiError) {
          // H7.1 Part 5 — distinguish the failure class so the UI tells
          // the user what actually happened instead of a generic message.
          if (err.isTimeout || err.isNetworkError) {
            setServerError(
              "Could not reach the server. Check your connection and try again.",
            );
          } else if (err.isUnauthenticated) {
            setServerError(
              "Your session has expired. Please log in again to save your profile.",
            );
          } else if (err.isValidationError) {
            setServerError(
              typeof err.body === "object" && err.body && "detail" in err.body
                ? String((err.body as { detail: unknown }).detail)
                : "Some details failed validation. Review the highlighted fields.",
            );
          } else if (err.isConflict) {
            setServerError(
              "A business profile already exists for this account. Reload to edit it.",
            );
          } else if (err.isServerError) {
            setServerError(
              "The server hit an internal error while saving. Please retry in a moment.",
            );
          } else {
            setServerError(err.message || "Could not save your business profile.");
          }
        } else {
          setServerError(err.message || "Could not save your business profile.");
        }
      },
    });
  };

  // ---- Success screen ----
  if (success) {
    return (
      <PageContainer width="default">
        <DashboardCard
          badge="Done"
          title="Your business profile is live"
          caption="We're running a quick analysis so every analytics surface has fresh data."
          >
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <Check className="size-6" aria-hidden="true" />
            </div>
            <p className="text-sm text-muted-foreground">
              {draft.basic.legal_name} has been saved with{" "}
              {draft.products.length} product(s) and {draft.certs.length} certification(s).
            </p>
            <Button asChild>
              <a href="/analysis">Run analysis</a>
            </Button>
          </div>
        </DashboardCard>
      </PageContainer>
    );
  }

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6">
        <StepRail current={stepIndex} onJump={(i) => {
          // Only allow jumping backwards, or to the next step (which is validated).
          if (i < stepIndex) {
            setServerError(null);
            setStepIndex(i);
          }
        }} />

        {serverError && (
          <Alert variant="error" title="We couldn't save your profile">
            {serverError}
          </Alert>
        )}

        {step.key === "basic"      && <BasicStep      draft={draft} update={updateBasic} errors={errors} />}
        {step.key === "capacity"   && <CapacityStep   draft={draft} update={updateCapacity} />}
        {step.key === "products"   && <ProductsStep   draft={draft} setDraft={setDraft} />}
        {step.key === "presence"   && <PresenceStep   draft={draft} update={updatePresence} />}
        {step.key === "certs"      && <CertsStep      draft={draft} setDraft={setDraft} />}
        {step.key === "exports"    && <ExportsStep    draft={draft} setDraft={setDraft} />}
        {step.key === "goals"      && <GoalsStep      draft={draft} setDraft={setDraft} />}
        {step.key === "challenges" && <ChallengesStep draft={draft} setDraft={setDraft} />}
        {step.key === "review"     && <ReviewStep     draft={draft} payload={buildPayload()} />}

        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={goBack} disabled={isFirst || create.isPending}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back
          </Button>
          <div className="text-xs text-muted-foreground">
            Step {stepIndex + 1} of {STEPS.length}
          </div>
          {isLast ? (
            <Button onClick={onSubmit} disabled={create.isPending}>
              {create.isPending ? "Saving…" : "Create profile"}
              <Send className="size-4" aria-hidden="true" />
            </Button>
          ) : (
            <Button onClick={goNext} disabled={create.isPending}>
              Next
              <ArrowRight className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- //
// Step rail — the clickable step pills
// --------------------------------------------------------------------------- //

function StepRail({
  current,
  onJump,
}: {
  current: number;
  onJump: (i: number) => void;
}) {
  return (
    <DashboardCard
      badge="Wizard"
      title="Create your business profile"
      caption="Nine steps. The required section is Basic Info; everything else can stay empty and be filled in later."
    >
      <ol className="flex flex-wrap items-center gap-2">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isCurrent = i === current;
          const isDone = i < current;
          return (
            <li key={s.key}>
              <button
                type="button"
                onClick={() => onJump(i)}
                disabled={i > current}
                aria-current={isCurrent ? "step" : undefined}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  isCurrent && "border-primary bg-primary text-primary-foreground",
                  !isCurrent && isDone && "border-emerald-500/40 bg-emerald-50 text-emerald-700",
                  !isCurrent && !isDone && "border-border bg-secondary text-muted-foreground",
                  i > current && "cursor-not-allowed opacity-50",
                )}
              >
                {isDone ? <Check className="size-3" aria-hidden="true" /> : <Icon className="size-3" aria-hidden="true" />}
                {s.label}
              </button>
            </li>
          );
        })}
      </ol>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 1 — Basic Info
// --------------------------------------------------------------------------- //

function BasicStep({
  draft,
  update,
  errors,
}: {
  draft: DraftState;
  update: (patch: Partial<BasicSection>) => void;
  errors: Record<string, string>;
}) {
  const b = draft.basic;
  return (
    <DashboardCard
      badge="Step 1"
      title="Basic information"
      caption="The minimum every business needs. Everything is editable later."
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField id="legal_name" label="Business name" required error={errors.legal_name}>
          <Input
            id="legal_name"
            value={b.legal_name}
            onChange={(e) => update({ legal_name: e.target.value })}
            placeholder="Acme Manufacturing Co."
            invalid={Boolean(errors.legal_name)}
          />
        </FormField>
        <FormField id="trade_name" label="Trade name" hint="Optional DBA / brand name.">
          <Input
            id="trade_name"
            value={b.trade_name ?? ""}
            onChange={(e) => update({ trade_name: e.target.value || null })}
            placeholder="Acme"
          />
        </FormField>
        <FormField id="industry" label="Industry" required error={errors.industry}>
          <Input
            id="industry"
            value={b.industry}
            onChange={(e) => update({ industry: e.target.value })}
            placeholder="Manufacturing"
            invalid={Boolean(errors.industry)}
          />
        </FormField>
        <FormField id="sub_industry" label="Sub-industry">
          <Input
            id="sub_industry"
            value={b.sub_industry ?? ""}
            onChange={(e) => update({ sub_industry: e.target.value || null })}
            placeholder="Industrial fasteners"
          />
        </FormField>
        <FormField id="business_type" label="Business type">
          <select
            id="business_type"
            value={b.business_type ?? ""}
            onChange={(e) => update({ business_type: (e.target.value || null) as BusinessType | null })}
            className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
          >
            <option value="">Select…</option>
            {BUSINESS_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </FormField>
        <FormField id="established_year" label="Established year" required error={errors.established_year}>
          <Input
            id="established_year"
            type="number"
            min={1800}
            max={currentYear}
            value={b.established_year}
            onChange={(e) => update({ established_year: Number(e.target.value) || 0 })}
            invalid={Boolean(errors.established_year)}
          />
        </FormField>
        <FormField id="employee_count" label="Employee count" required error={errors.employee_count}>
          <Input
            id="employee_count"
            type="number"
            min={0}
            value={b.employee_count}
            onChange={(e) => update({ employee_count: Number(e.target.value) || 0 })}
            invalid={Boolean(errors.employee_count)}
          />
        </FormField>
        <FormField id="annual_revenue" label="Annual revenue" required error={errors.annual_revenue}>
          <div className="flex gap-2">
            <Input
              id="annual_revenue"
              type="number"
              min={0}
              value={b.annual_revenue}
              onChange={(e) => update({ annual_revenue: Number(e.target.value) || 0 })}
              invalid={Boolean(errors.annual_revenue)}
            />
            <select
              aria-label="Currency"
              value={b.revenue_currency}
              onChange={(e) => update({ revenue_currency: e.target.value })}
              className="h-10 rounded-md border border-input bg-background px-2 text-sm"
            >
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </FormField>
        <FormField id="country" label="Country">
          <Input
            id="country"
            value={b.country ?? ""}
            onChange={(e) => update({ country: e.target.value || null })}
            placeholder="US"
          />
        </FormField>
        <FormField id="state_region" label="State / region">
          <Input
            id="state_region"
            value={b.state_region ?? ""}
            onChange={(e) => update({ state_region: e.target.value || null })}
          />
        </FormField>
        <FormField id="city" label="City">
          <Input
            id="city"
            value={b.city ?? ""}
            onChange={(e) => update({ city: e.target.value || null })}
          />
        </FormField>
        <FormField id="description" label="Description" className="md:col-span-2" hint="A short paragraph about what the business does.">
          <textarea
            id="description"
            value={b.description ?? ""}
            onChange={(e) => update({ description: e.target.value || null })}
            rows={3}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
          />
        </FormField>
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 2 — Capacity
// --------------------------------------------------------------------------- //

function CapacityStep({
  draft,
  update,
}: {
  draft: DraftState;
  update: (patch: Partial<CapacitySection>) => void;
}) {
  const c = draft.capacity;
  return (
    <DashboardCard
      badge="Step 2"
      title="Capacity"
      caption="Production scale, utilisation, monthly volume. All optional."
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField id="production_capacity" label="Production capacity">
          <Input
            id="production_capacity"
            value={c.production_capacity ?? ""}
            onChange={(e) => update({ production_capacity: e.target.value || null })}
            placeholder="e.g. 100,000 units / month"
          />
        </FormField>
        <FormField id="production_capacity_unit" label="Capacity unit">
          <Input
            id="production_capacity_unit"
            value={c.production_capacity_unit ?? ""}
            onChange={(e) => update({ production_capacity_unit: e.target.value || null })}
            placeholder="units / month"
          />
        </FormField>
        <FormField id="capacity_utilization_pct" label="Utilisation (%)">
          <Input
            id="capacity_utilization_pct"
            type="number"
            min={0}
            max={100}
            value={c.capacity_utilization_pct ?? ""}
            onChange={(e) => update({ capacity_utilization_pct: e.target.value === "" ? null : Number(e.target.value) })}
          />
        </FormField>
        <FormField id="monthly_production_units" label="Monthly production (units)">
          <Input
            id="monthly_production_units"
            type="number"
            min={0}
            value={c.monthly_production_units ?? ""}
            onChange={(e) => update({ monthly_production_units: e.target.value === "" ? null : Number(e.target.value) })}
          />
        </FormField>
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 3 — Products (repeatable)
// --------------------------------------------------------------------------- //

function ProductsStep({
  draft,
  setDraft,
}: {
  draft: DraftState;
  setDraft: React.Dispatch<React.SetStateAction<DraftState>>;
}) {
  const blank = (): ProductCreate => ({
    name: "", category: null, hs_code: null, description: null,
    unit_price: null, currency: "USD", monthly_volume: null, is_exported: false,
  });
  return (
    <DashboardCard
      badge="Step 3"
      title="Products"
      caption="Add the products / services you sell. You can add more later."
      trailing={
        <Button size="sm" variant="outline" onClick={() => setDraft((d) => ({ ...d, products: [...d.products, blank()] }))}>
          + Add product
        </Button>
      }
    >
      {draft.products.length === 0 ? (
        <p className="text-sm text-muted-foreground">No products yet. Click “Add product” when you’re ready.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {draft.products.map((p, i) => (
            <RepeatableRow
              key={i}
              index={i}
              onRemove={() => setDraft((d) => ({ ...d, products: d.products.filter((_, j) => j !== i) }))}
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField id={`prod_name_${i}`} label="Name" required>
                  <Input
                    id={`prod_name_${i}`}
                    value={p.name}
                    onChange={(e) => setDraft((d) => ({
                      ...d, products: d.products.map((x, j) => j === i ? { ...x, name: e.target.value } : x),
                    }))}
                  />
                </FormField>
                <FormField id={`prod_category_${i}`} label="Category">
                  <Input
                    id={`prod_category_${i}`}
                    value={p.category ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, products: d.products.map((x, j) => j === i ? { ...x, category: e.target.value || null } : x),
                    }))}
                  />
                </FormField>
                <FormField id={`prod_hs_${i}`} label="HS code">
                  <Input
                    id={`prod_hs_${i}`}
                    value={p.hs_code ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, products: d.products.map((x, j) => j === i ? { ...x, hs_code: e.target.value || null } : x),
                    }))}
                  />
                </FormField>
                <FormField id={`prod_unit_${i}`} label="Unit price">
                  <Input
                    id={`prod_unit_${i}`}
                    type="number"
                    min={0}
                    value={p.unit_price ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, products: d.products.map((x, j) =>
                        j === i ? { ...x, unit_price: e.target.value === "" ? null : Number(e.target.value) } : x,
                      ),
                    }))}
                  />
                </FormField>
                <label className="col-span-1 inline-flex items-center gap-2 text-sm md:col-span-2">
                  <input
                    type="checkbox"
                    checked={p.is_exported}
                    onChange={(e) => setDraft((d) => ({
                      ...d, products: d.products.map((x, j) => j === i ? { ...x, is_exported: e.target.checked } : x),
                    }))}
                    className="size-4"
                  />
                  Exported
                </label>
              </div>
            </RepeatableRow>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 4 — Digital Presence
// --------------------------------------------------------------------------- //

function PresenceStep({
  draft,
  update,
}: {
  draft: DraftState;
  update: (patch: Partial<DigitalPresenceCreate>) => void;
}) {
  const p = draft.presence;
  return (
    <DashboardCard
      badge="Step 4"
      title="Digital presence"
      caption="Your website and social channels. Leave blank to skip."
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField id="website_url" label="Website">
          <Input id="website_url" value={p.website_url ?? ""}
            onChange={(e) => update({ website_url: e.target.value || null })}
            placeholder="https://example.com" />
        </FormField>
        <FormField id="linkedin_url" label="LinkedIn">
          <Input id="linkedin_url" value={p.linkedin_url ?? ""}
            onChange={(e) => update({ linkedin_url: e.target.value || null })} />
        </FormField>
        <FormField id="facebook_url" label="Facebook">
          <Input id="facebook_url" value={p.facebook_url ?? ""}
            onChange={(e) => update({ facebook_url: e.target.value || null })} />
        </FormField>
        <FormField id="instagram_url" label="Instagram">
          <Input id="instagram_url" value={p.instagram_url ?? ""}
            onChange={(e) => update({ instagram_url: e.target.value || null })} />
        </FormField>
        <FormField id="twitter_url" label="X / Twitter">
          <Input id="twitter_url" value={p.twitter_url ?? ""}
            onChange={(e) => update({ twitter_url: e.target.value || null })} />
        </FormField>
        <FormField id="youtube_url" label="YouTube">
          <Input id="youtube_url" value={p.youtube_url ?? ""}
            onChange={(e) => update({ youtube_url: e.target.value || null })} />
        </FormField>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={p.has_ecommerce}
            onChange={(e) => update({ has_ecommerce: e.target.checked })} />
          Has e-commerce
        </label>
        <FormField id="ecommerce_platform" label="E-commerce platform">
          <Input id="ecommerce_platform" value={p.ecommerce_platform ?? ""}
            onChange={(e) => update({ ecommerce_platform: e.target.value || null })}
            placeholder="Shopify, WooCommerce, …" />
        </FormField>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={p.uses_digital_marketing}
            onChange={(e) => update({ uses_digital_marketing: e.target.checked })} />
          Uses digital marketing
        </label>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={p.uses_cloud_systems}
            onChange={(e) => update({ uses_cloud_systems: e.target.checked })} />
          Uses cloud systems
        </label>
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 5 — Certifications (repeatable)
// --------------------------------------------------------------------------- //

function CertsStep({
  draft, setDraft,
}: { draft: DraftState; setDraft: React.Dispatch<React.SetStateAction<DraftState>> }) {
  const blank = (): CertificationCreate => ({
    name: "", issuing_body: null, issued_date: null, expiry_date: null, certificate_number: null,
  });
  return (
    <DashboardCard
      badge="Step 5"
      title="Certifications"
      caption="ISO 9001, organic, fair-trade, etc."
      trailing={
        <Button size="sm" variant="outline" onClick={() => setDraft((d) => ({ ...d, certs: [...d.certs, blank()] }))}>
          + Add certification
        </Button>
      }
    >
      {draft.certs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No certifications yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {draft.certs.map((c, i) => (
            <RepeatableRow key={i} index={i}
              onRemove={() => setDraft((d) => ({ ...d, certs: d.certs.filter((_, j) => j !== i) }))}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField id={`cert_name_${i}`} label="Name" required>
                  <Input id={`cert_name_${i}`} value={c.name}
                    onChange={(e) => setDraft((d) => ({
                      ...d, certs: d.certs.map((x, j) => j === i ? { ...x, name: e.target.value } : x),
                    }))} />
                </FormField>
                <FormField id={`cert_body_${i}`} label="Issuing body">
                  <Input id={`cert_body_${i}`} value={c.issuing_body ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, certs: d.certs.map((x, j) => j === i ? { ...x, issuing_body: e.target.value || null } : x),
                    }))} />
                </FormField>
                <FormField id={`cert_issued_${i}`} label="Issued date">
                  <Input id={`cert_issued_${i}`} type="date" value={c.issued_date ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, certs: d.certs.map((x, j) => j === i ? { ...x, issued_date: e.target.value || null } : x),
                    }))} />
                </FormField>
                <FormField id={`cert_expiry_${i}`} label="Expiry date">
                  <Input id={`cert_expiry_${i}`} type="date" value={c.expiry_date ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, certs: d.certs.map((x, j) => j === i ? { ...x, expiry_date: e.target.value || null } : x),
                    }))} />
                </FormField>
              </div>
            </RepeatableRow>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 6 — Export History (repeatable)
// --------------------------------------------------------------------------- //

function ExportsStep({
  draft, setDraft,
}: { draft: DraftState; setDraft: React.Dispatch<React.SetStateAction<DraftState>> }) {
  const blank = (): ExportHistoryCreate => ({
    destination_country: "", product_category: null, first_export_date: null,
    annual_export_value: null, currency: "USD", iec_number: null,
  });
  return (
    <DashboardCard
      badge="Step 6"
      title="Export history"
      caption="Countries you have already shipped to, with annual value and IEC number."
      trailing={
        <Button size="sm" variant="outline" onClick={() => setDraft((d) => ({ ...d, exports: [...d.exports, blank()] }))}>
          + Add export record
        </Button>
      }
    >
      {draft.exports.length === 0 ? (
        <p className="text-sm text-muted-foreground">No export records yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {draft.exports.map((e, i) => (
            <RepeatableRow key={i} index={i}
              onRemove={() => setDraft((d) => ({ ...d, exports: d.exports.filter((_, j) => j !== i) }))}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField id={`exp_country_${i}`} label="Destination country" required>
                  <Input id={`exp_country_${i}`} value={e.destination_country}
                    onChange={(ev) => setDraft((d) => ({
                      ...d, exports: d.exports.map((x, j) => j === i ? { ...x, destination_country: ev.target.value } : x),
                    }))} />
                </FormField>
                <FormField id={`exp_cat_${i}`} label="Product category">
                  <Input id={`exp_cat_${i}`} value={e.product_category ?? ""}
                    onChange={(ev) => setDraft((d) => ({
                      ...d, exports: d.exports.map((x, j) => j === i ? { ...x, product_category: ev.target.value || null } : x),
                    }))} />
                </FormField>
                <FormField id={`exp_value_${i}`} label="Annual value">
                  <Input id={`exp_value_${i}`} type="number" min={0} value={e.annual_export_value ?? ""}
                    onChange={(ev) => setDraft((d) => ({
                      ...d, exports: d.exports.map((x, j) =>
                        j === i ? { ...x, annual_export_value: ev.target.value === "" ? null : Number(ev.target.value) } : x,
                      ),
                    }))} />
                </FormField>
                <FormField id={`exp_iec_${i}`} label="IEC number">
                  <Input id={`exp_iec_${i}`} value={e.iec_number ?? ""}
                    onChange={(ev) => setDraft((d) => ({
                      ...d, exports: d.exports.map((x, j) => j === i ? { ...x, iec_number: ev.target.value || null } : x),
                    }))} />
                </FormField>
              </div>
            </RepeatableRow>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 7 — Goals (repeatable)
// --------------------------------------------------------------------------- //

function GoalsStep({
  draft, setDraft,
}: { draft: DraftState; setDraft: React.Dispatch<React.SetStateAction<DraftState>> }) {
  const blank = (): BusinessGoalCreate => ({
    title: "", description: null, timeframe: null, priority: "medium", target_date: null,
  });
  return (
    <DashboardCard
      badge="Step 7"
      title="Business goals"
      caption="What are you trying to achieve in the next 6–12 months?"
      trailing={
        <Button size="sm" variant="outline" onClick={() => setDraft((d) => ({ ...d, goals: [...d.goals, blank()] }))}>
          + Add goal
        </Button>
      }
    >
      {draft.goals.length === 0 ? (
        <p className="text-sm text-muted-foreground">No goals yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {draft.goals.map((g, i) => (
            <RepeatableRow key={i} index={i}
              onRemove={() => setDraft((d) => ({ ...d, goals: d.goals.filter((_, j) => j !== i) }))}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField id={`goal_title_${i}`} label="Title" required>
                  <Input id={`goal_title_${i}`} value={g.title}
                    onChange={(e) => setDraft((d) => ({
                      ...d, goals: d.goals.map((x, j) => j === i ? { ...x, title: e.target.value } : x),
                    }))} />
                </FormField>
                <FormField id={`goal_timeframe_${i}`} label="Timeframe">
                  <Input id={`goal_timeframe_${i}`} value={g.timeframe ?? ""}
                    placeholder="6 months, 1 year…"
                    onChange={(e) => setDraft((d) => ({
                      ...d, goals: d.goals.map((x, j) => j === i ? { ...x, timeframe: e.target.value || null } : x),
                    }))} />
                </FormField>
                <FormField id={`goal_priority_${i}`} label="Priority">
                  <select id={`goal_priority_${i}`} value={g.priority}
                    onChange={(e) => setDraft((d) => ({
                      ...d, goals: d.goals.map((x, j) =>
                        j === i ? { ...x, priority: e.target.value as "low" | "medium" | "high" } : x,
                      ),
                    }))}
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </FormField>
                <FormField id={`goal_target_${i}`} label="Target date">
                  <Input id={`goal_target_${i}`} type="date" value={g.target_date ?? ""}
                    onChange={(e) => setDraft((d) => ({
                      ...d, goals: d.goals.map((x, j) => j === i ? { ...x, target_date: e.target.value || null } : x),
                    }))} />
                </FormField>
              </div>
            </RepeatableRow>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 8 — Challenges (repeatable)
// --------------------------------------------------------------------------- //

function ChallengesStep({
  draft, setDraft,
}: { draft: DraftState; setDraft: React.Dispatch<React.SetStateAction<DraftState>> }) {
  const blank = (): BusinessChallengeCreate => ({
    title: "", description: null, severity: "medium", category: null,
  });
  return (
    <DashboardCard
      badge="Step 8"
      title="Business challenges"
      caption="Pain points that are blocking growth."
      trailing={
        <Button size="sm" variant="outline" onClick={() => setDraft((d) => ({ ...d, challenges: [...d.challenges, blank()] }))}>
          + Add challenge
        </Button>
      }
    >
      {draft.challenges.length === 0 ? (
        <p className="text-sm text-muted-foreground">No challenges yet.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {draft.challenges.map((c, i) => (
            <RepeatableRow key={i} index={i}
              onRemove={() => setDraft((d) => ({ ...d, challenges: d.challenges.filter((_, j) => j !== i) }))}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <FormField id={`chal_title_${i}`} label="Title" required>
                  <Input id={`chal_title_${i}`} value={c.title}
                    onChange={(e) => setDraft((d) => ({
                      ...d, challenges: d.challenges.map((x, j) => j === i ? { ...x, title: e.target.value } : x),
                    }))} />
                </FormField>
                <FormField id={`chal_severity_${i}`} label="Severity">
                  <select id={`chal_severity_${i}`} value={c.severity}
                    onChange={(e) => setDraft((d) => ({
                      ...d, challenges: d.challenges.map((x, j) =>
                        j === i ? { ...x, severity: e.target.value as "low" | "medium" | "high" | "critical" } : x,
                      ),
                    }))}
                    className="h-10 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </FormField>
                <FormField id={`chal_category_${i}`} label="Category" className="md:col-span-2">
                  <Input id={`chal_category_${i}`} value={c.category ?? ""}
                    placeholder="cash flow, hiring, supply chain, …"
                    onChange={(e) => setDraft((d) => ({
                      ...d, challenges: d.challenges.map((x, j) => j === i ? { ...x, category: e.target.value || null } : x),
                    }))} />
                </FormField>
              </div>
            </RepeatableRow>
          ))}
        </div>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Step 9 — Review (read-only summary)
// --------------------------------------------------------------------------- //

function ReviewStep({ draft, payload }: { draft: DraftState; payload: BusinessCreate }) {
  const counts = useMemo(() => ({
    basicFields: Object.values(draft.basic).filter((v) => v !== null && v !== "" && v !== 0).length,
    products: draft.products.length,
    certs: draft.certs.length,
    exports: draft.exports.length,
    goals: draft.goals.length,
    challenges: draft.challenges.length,
    hasPresence:
      Boolean(draft.presence.website_url) ||
      Boolean(draft.presence.linkedin_url) ||
      draft.presence.has_ecommerce,
  }), [draft]);

  return (
    <DashboardCard
      badge="Step 9"
      title="Review &amp; submit"
      caption="Last look. You can edit anything later from the business page."
    >
      <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
        <ReviewRow label="Business name" value={payload.basic.legal_name || "—"} />
        <ReviewRow label="Industry"      value={payload.basic.industry || "—"} />
        <ReviewRow label="Type"          value={payload.basic.business_type ?? "—"} />
        <ReviewRow label="Established"   value={String(payload.basic.established_year)} />
        <ReviewRow label="Employees"     value={String(payload.basic.employee_count)} />
        <ReviewRow
          label="Annual revenue"
          value={`${payload.basic.annual_revenue} ${payload.basic.revenue_currency}`}
        />
        <ReviewRow label="Location"      value={[payload.basic.city, payload.basic.state_region, payload.basic.country].filter(Boolean).join(", ") || "—"} />
        <ReviewRow label="Products"      value={String(counts.products)} />
        <ReviewRow label="Certifications"value={String(counts.certs)} />
        <ReviewRow label="Exports"       value={String(counts.exports)} />
        <ReviewRow label="Goals"         value={String(counts.goals)} />
        <ReviewRow label="Challenges"    value={String(counts.challenges)} />
        <ReviewRow label="Digital presence" value={counts.hasPresence ? "provided" : "—"} />
      </dl>
    </DashboardCard>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-secondary/30 px-3 py-2">
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Small shared piece: a card-shaped wrapper for a single repeatable row
// --------------------------------------------------------------------------- //

function RepeatableRow({
  index, onRemove, children,
}: { index: number; onRemove: () => void; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-secondary/20 p-3">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Item {index + 1}
        </span>
        <Button size="sm" variant="ghost" onClick={onRemove}>
          Remove
        </Button>
      </div>
      {children}
    </div>
  );
}
