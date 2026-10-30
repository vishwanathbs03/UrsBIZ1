"use client";

/**
 * BusinessSurface — client-only view for /business.
 *
 * Three states:
 *   1. loading   -> skeleton
 *   2. no row    -> BusinessWizard (create)
 *   3. has row   -> BusinessOverview with Edit -> toggle back to wizard
 *
 * The page does NOT touch routing directly. "Edit" lives in component
 * state and just toggles the wizard open over the overview.
 */

import { useState } from "react";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { BusinessOverview } from "@/features/business/BusinessOverview";
import { BusinessWizard } from "@/features/business/BusinessWizard";
import { useBusinessQuery } from "@/features/business/use-business-data";
import { ApiError } from "@/services/api-client";

export function BusinessSurface() {
  const { data, isLoading, error } = useBusinessQuery();
  const [editing, setEditing] = useState(false);

  if (isLoading) {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-4">
          <DashboardSkeleton rows={3} />
          <DashboardSkeleton rows={5} />
          <DashboardSkeleton rows={4} />
        </div>
      </PageContainer>
    );
  }

  if (error) {
    if (error instanceof ApiError && error.status === 404) {
      return <BusinessWizard />;
    }
    // Any other error: the user has no business row to edit AND
    // the backend is failing, so the wizard is still the right
    // entry point. The wizard will surface its own server error
    // if POST also fails.
    return <BusinessWizard />;
  }

  if (!data) {
    return <BusinessWizard />;
  }

  if (editing) {
    return <BusinessWizard />;
  }

  return <BusinessOverview onEdit={() => setEditing(true)} />;
}
