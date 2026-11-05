"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  ShieldCheck,
  Building2,
  Lock,
  Shield,
  CheckCircle,
  HelpCircle,
  Info,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import {
  collaborationService,
  type BusinessRole,
  type ApprovalSummaryResponse,
} from "@/services";
import { useAuth } from "@/hooks/use-auth";
import { TeamManagement } from "./TeamManagement";
import { ApprovalQueue } from "./ApprovalQueue";

const ROLE_COLOR_MAP: Record<BusinessRole, string> = {
  Owner: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-800",
  Administrator: "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border-purple-300 dark:border-purple-800",
  Manager: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-800",
  Analyst: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
  Viewer: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700",
};

export function CollaborationView() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"team" | "approvals">("team");
  const [currentRole, setCurrentRole] = useState<BusinessRole>("Viewer");
  const [summary, setSummary] = useState<ApprovalSummaryResponse | null>(null);
  const [showRoleMatrix, setShowRoleMatrix] = useState(false);

  const fetchRoleAndSummary = async () => {
    try {
      const [membersRes, summaryRes] = await Promise.all([
        collaborationService.listMembers(),
        collaborationService.getApprovalSummary(),
      ]);
      setCurrentRole(membersRes.current_user_role);
      setSummary(summaryRes);
    } catch (err) {
      // Graceful fallback to Viewer if member resolution fails
      setCurrentRole("Viewer");
    }
  };

  useEffect(() => {
    fetchRoleAndSummary();
  }, [user]);

  return (
    <div className="space-y-6">
      {/* Header with Active Role Indicator */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <PageHeader
          title="Team & Approvals (RBAC)"
          description="Multi-user MSME collaboration with role-based access control and dual-control approval governance."
        />

        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-2.5">
            <Shield className="w-4 h-4 text-primary" />
            <div className="text-xs">
              <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">
                Your Active Role
              </span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Badge variant="outline" className={`text-xs px-2 py-0.2 ${ROLE_COLOR_MAP[currentRole]}`}>
                  {currentRole}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-6">
          <button
            onClick={() => setActiveTab("team")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
              activeTab === "team"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
            }`}
          >
            <Users className="w-4 h-4" />
            Team Members
          </button>

          <button
            onClick={() => setActiveTab("approvals")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
              activeTab === "approvals"
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Approval Workflows
            {summary && summary.pending > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-amber-500 text-white font-bold">
                {summary.pending}
              </span>
            )}
          </button>
        </div>

        <button
          onClick={() => setShowRoleMatrix(!showRoleMatrix)}
          className="text-xs text-primary hover:underline flex items-center gap-1 pb-3"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          <span>{showRoleMatrix ? "Hide Permissions Matrix" : "View Role Hierarchy"}</span>
        </button>
      </div>

      {/* Role Hierarchy Quick Reference Matrix */}
      {showRoleMatrix && (
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Lock className="w-4 h-4 text-primary" />
              UrsBiz 5-Role Permission Hierarchy
            </h3>
            <span className="text-[11px] text-slate-500">Strict server-side validation</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
            <div className="p-3 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/40 dark:bg-amber-950/20">
              <strong className="text-amber-800 dark:text-amber-300 block mb-1">1. Owner (Rank 50)</strong>
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Primary MSME proprietor. Sole authority to delete business or transfer ownership.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50/40 dark:bg-purple-950/20">
              <strong className="text-purple-800 dark:text-purple-300 block mb-1">2. Administrator (40)</strong>
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Full operational control. Invites and manages team, approves financial decisions.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-blue-200 dark:border-blue-900/40 bg-blue-50/40 dark:bg-blue-950/20">
              <strong className="text-blue-800 dark:text-blue-300 block mb-1">3. Manager (30)</strong>
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Operational execution. Manages goals, uploads sales data, reviews approvals.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/40 dark:bg-emerald-950/20">
              <strong className="text-emerald-800 dark:text-emerald-300 block mb-1">4. Analyst (20)</strong>
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Business intelligence. Proposes decisions, runs what-if models, drafts reports.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
              <strong className="text-slate-800 dark:text-slate-300 block mb-1">5. Viewer (10)</strong>
              <p className="text-[11px] text-slate-600 dark:text-slate-400">
                Read-only auditor. Can view dashboard, progress and download reports.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Tab Content */}
      {activeTab === "team" ? (
        <TeamManagement
          currentRole={currentRole}
          onRefreshData={fetchRoleAndSummary}
        />
      ) : (
        <ApprovalQueue
          currentRole={currentRole}
          currentUserId={user?.id}
        />
      )}
    </div>
  );
}
