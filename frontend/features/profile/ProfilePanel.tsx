"use client";

/**
 * ProfilePanel (Sprint 23).
 *
 * Slide-over panel mounted from `NavbarAuth` when the user clicks
 * their name chip. Body:
 *
 *   1. Header — initial avatar + full name + email (read-only).
 *   2. Businesses section — every business the user owns, with
 *      an active pill on the current one, a 'Switch' button on
 *      the others, and a 'Delete' icon button per row (disabled
 *      when it is the user's only business).
 *   3. 'Add a business' inline form — six required fields. On
 *      submit, redirects to /business so the wizard can fill out
 *      the remaining 7 sections.
 *   4. Footer — 'Sign out' button.
 *
 * The panel does NOT own its open state; the parent (NavbarAuth)
 * passes ``open`` + ``onOpenChange`` so the trigger and the
 * surface stay in lockstep.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";

import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import {
  useBusinessesQuery,
  useCreateBusinessMinimal,
  useDeleteBusinessById,
  useSetActiveBusiness,
} from "@/features/profile/use-businesses";
import type { BusinessListItem } from "@/types/business";

interface ProfilePanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProfilePanel({ open, onOpenChange }: ProfilePanelProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Profile">
        <ProfileBody onClose={() => onOpenChange(false)} />
      </SheetContent>
    </Sheet>
  );
}

// --------------------------------------------------------------------------- //
// Body
// --------------------------------------------------------------------------- //

interface ProfileBodyProps {
  onClose: () => void;
}

function ProfileBody({ onClose }: ProfileBodyProps) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const businesses = useBusinessesQuery();
  const setActive = useSetActiveBusiness();
  const createMinimal = useCreateBusinessMinimal();
  const deleteBusiness = useDeleteBusinessById();

  const [adding, setAdding] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<BusinessListItem | null>(
    null,
  );

  if (!user) {
    // The panel is only rendered when authenticated (see NavbarAuth).
    return null;
  }
  const initial = user.full_name.trim().charAt(0).toUpperCase() || "?";

  const onSignOut = async () => {
    setSigningOut(true);
    try {
      await logout();
      onClose();
      router.replace("/");
      router.refresh();
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          aria-hidden="true"
          className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-base font-semibold text-primary"
        >
          {initial}
        </div>
        <div>
          <p className="text-base font-semibold text-foreground">
            {user.full_name}
          </p>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
      </div>

      {/* Businesses */}
      <section className="flex flex-col gap-3">
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Your businesses
          </h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAdding((v) => !v)}
            aria-expanded={adding}
            aria-controls="add-business-form"
          >
            <Plus className="size-4" aria-hidden="true" />
            Add a business
          </Button>
        </header>

        {adding ? (
          <AddBusinessForm
            onCancel={() => setAdding(false)}
            onSubmit={async (payload) => {
              await createMinimal.mutateAsync(payload);
              setAdding(false);
              onClose();
              router.push("/business");
            }}
            pending={createMinimal.isPending}
          />
        ) : null}

        <ul className="flex flex-col gap-2" aria-label="Business list">
          {(businesses.data?.items ?? []).map((biz) => {
            const isActive = biz.id === user.active_business_id;
            const isOnly = (businesses.data?.count ?? 0) <= 1;
            return (
              <li
                key={biz.id}
                className="flex items-center justify-between gap-3 rounded-md border border-border bg-background p-3"
              >
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-foreground">
                      {biz.legal_name}
                    </span>
                    {isActive ? (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                        <CheckCircle2 className="size-3" aria-hidden="true" />
                        Active
                      </span>
                    ) : null}
                  </div>
                  <span className="truncate text-xs text-muted-foreground">
                    {biz.industry}
                    {biz.city ? ` · ${biz.city}` : ""}
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {isActive ? null : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setActive.mutate(biz.id)}
                      disabled={setActive.isPending}
                    >
                      Switch
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setDeleteTarget(biz)}
                    disabled={isOnly}
                    aria-label={`Delete ${biz.legal_name}`}
                    title={isOnly ? "You must keep at least one business" : undefined}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      {/* Footer — sign out */}
      <div className="mt-auto border-t border-border pt-4">
        <Button
          variant="outline"
          className="w-full"
          onClick={onSignOut}
          disabled={signingOut}
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </Button>
      </div>

      {/* Delete confirm — kept inline; a full Dialog component is out
          of scope for this iteration. */}
      {deleteTarget ? (
        <DeleteConfirm
          business={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={async () => {
            await deleteBusiness.mutateAsync(deleteTarget.id);
            setDeleteTarget(null);
          }}
          pending={deleteBusiness.isPending}
        />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Inline 'Add a business' form
// --------------------------------------------------------------------------- //

interface AddBusinessFormProps {
  onCancel: () => void;
  onSubmit: (payload: {
    legal_name: string;
    industry: string;
    established_year: number;
    employee_count: number;
    annual_revenue: number;
    revenue_currency: string;
  }) => Promise<void>;
  pending: boolean;
}

function AddBusinessForm({ onCancel, onSubmit, pending }: AddBusinessFormProps) {
  const [legalName, setLegalName] = React.useState("");
  const [industry, setIndustry] = React.useState("");
  const [year, setYear] = React.useState<number | "">("");
  const [employeeCount, setEmployeeCount] = React.useState<number | "">("");
  const [annualRevenue, setAnnualRevenue] = React.useState<number | "">("");
  const [currency, setCurrency] = React.useState("INR");

  const ready =
    legalName.trim() !== "" &&
    industry.trim() !== "" &&
    year !== "" &&
    employeeCount !== "" &&
    annualRevenue !== "";

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ready) return;
    await onSubmit({
      legal_name: legalName.trim(),
      industry: industry.trim(),
      established_year: Number(year),
      employee_count: Number(employeeCount),
      annual_revenue: Number(annualRevenue),
      revenue_currency: currency.toUpperCase(),
    });
  };

  return (
    <form
      id="add-business-form"
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-md border border-border bg-muted/40 p-3"
    >
      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-foreground">Legal name</span>
        <input
          required
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
          className="rounded border border-input bg-background px-2 py-1 text-sm"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-foreground">Industry</span>
        <input
          required
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="rounded border border-input bg-background px-2 py-1 text-sm"
        />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-foreground">Established year</span>
          <input
            required
            type="number"
            min={1800}
            max={new Date().getFullYear()}
            value={year}
            onChange={(e) =>
              setYear(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="rounded border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-foreground">Employees</span>
          <input
            required
            type="number"
            min={0}
            value={employeeCount}
            onChange={(e) =>
              setEmployeeCount(
                e.target.value === "" ? "" : Number(e.target.value),
              )
            }
            className="rounded border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <label className="col-span-2 flex flex-col gap-1 text-xs">
          <span className="font-medium text-foreground">Annual revenue</span>
          <input
            required
            type="number"
            min={0}
            step="0.01"
            value={annualRevenue}
            onChange={(e) =>
              setAnnualRevenue(
                e.target.value === "" ? "" : Number(e.target.value),
              )
            }
            className="rounded border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-foreground">Currency</span>
          <input
            required
            maxLength={3}
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            className="rounded border border-input bg-background px-2 py-1 text-sm uppercase"
          />
        </label>
      </div>
      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={!ready || pending}>
          {pending ? "Adding…" : "Add business"}
        </Button>
      </div>
    </form>
  );
}

// --------------------------------------------------------------------------- //
// Delete confirm
// --------------------------------------------------------------------------- //

interface DeleteConfirmProps {
  business: BusinessListItem;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
  pending: boolean;
}

function DeleteConfirm({
  business,
  onCancel,
  onConfirm,
  pending,
}: DeleteConfirmProps) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60">
      <div
        role="dialog"
        aria-modal="true"
        className="mx-4 w-full max-w-sm rounded-md border border-border bg-card p-5 shadow-2xl"
      >
        <h4 className="text-base font-semibold text-foreground">
          Delete {business.legal_name}?
        </h4>
        <p className="mt-2 text-sm text-muted-foreground">
          This permanently removes the business and every nested row
          (products, certifications, goals, ...). This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onConfirm}
            disabled={pending}
          >
            {pending ? "Deleting…" : "Delete"}
          </Button>
        </div>
      </div>
    </div>
  );
}
