"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  UserPlus,
  Shield,
  Trash2,
  Mail,
  Copy,
  Check,
  Clock,
  AlertCircle,
  MoreVertical,
  ArrowRightLeft,
  KeyRound,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  collaborationService,
  type MemberOut,
  type InvitationOut,
  type BusinessRole,
} from "@/services";
import { InviteMemberModal } from "./InviteMemberModal";

interface TeamManagementProps {
  currentRole: BusinessRole;
  onRefreshData?: () => void;
}

const ROLE_BADGES: Record<BusinessRole, string> = {
  Owner: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-800",
  Administrator: "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border-purple-300 dark:border-purple-800",
  Manager: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-800",
  Analyst: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
  Viewer: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700",
};

export function TeamManagement({ currentRole, onRefreshData }: TeamManagementProps) {
  const [members, setMembers] = useState<MemberOut[]>([]);
  const [invitations, setInvitations] = useState<InvitationOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [copiedTokenId, setCopiedTokenId] = useState<number | null>(null);
  const [transferUserId, setTransferUserId] = useState<number | null>(null);
  const [transferring, setTransferring] = useState(false);

  const canManageTeam = currentRole === "Owner" || currentRole === "Administrator";

  const loadTeamData = async () => {
    setLoading(true);
    setError(null);
    try {
      const membersRes = await collaborationService.listMembers();
      setMembers(membersRes.members);

      if (canManageTeam) {
        const invsRes = await collaborationService.listInvitations();
        setInvitations(invsRes.invitations);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load team data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeamData();
  }, [currentRole]);

  const handleRoleChange = async (memberId: number, newRole: BusinessRole) => {
    try {
      await collaborationService.updateMemberRole(memberId, newRole);
      loadTeamData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to update role.");
    }
  };

  const handleRemoveMember = async (memberId: number, memberName: string) => {
    if (!confirm(`Are you sure you want to remove ${memberName} from this business workspace?`)) return;
    try {
      await collaborationService.removeMember(memberId);
      loadTeamData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to remove member.");
    }
  };

  const handleRevokeInvitation = async (invitationId: number) => {
    if (!confirm("Revoke this pending invitation?")) return;
    try {
      await collaborationService.revokeInvitation(invitationId);
      loadTeamData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to revoke invitation.");
    }
  };

  const handleCopyInviteLink = (inv: InvitationOut) => {
    if (!inv.invitation_url) return;
    const url = `${window.location.origin}${inv.invitation_url}`;
    navigator.clipboard.writeText(url);
    setCopiedTokenId(inv.id);
    setTimeout(() => setCopiedTokenId(null), 2000);
  };

  const handleTransferOwnership = async () => {
    if (!transferUserId) return;
    const targetMember = members.find((m) => m.user_id === transferUserId);
    if (!targetMember) return;

    const confirmed = confirm(
      `CRITICAL GOVERNANCE ACTION:\n\nYou are about to transfer sole business ownership to ${targetMember.user_full_name} (${targetMember.user_email}).\n\nYour own role will become Administrator. This action cannot be reversed without the new owner's explicit transfer.\n\nProceed?`
    );
    if (!confirmed) return;

    setTransferring(true);
    try {
      await collaborationService.transferOwnership({ new_owner_user_id: transferUserId });
      setTransferUserId(null);
      loadTeamData();
      if (onRefreshData) onRefreshData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to transfer ownership.");
    } finally {
      setTransferring(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner & Invite Action */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-primary/5 via-slate-50 to-primary/5 dark:from-primary/10 dark:via-slate-900 dark:to-primary/10 border border-slate-200 dark:border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Team Roster & Collaborator Roles
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Role-Based Access Control (RBAC) enforces principle of least privilege across all business actions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadTeamData}
            disabled={loading}
            className="gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          {canManageTeam && (
            <Button
              size="sm"
              onClick={() => setIsInviteModalOpen(true)}
              className="gap-1.5 shadow-sm"
            >
              <UserPlus className="w-4 h-4" />
              Invite Collaborator
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 rounded-xl">
          <AlertCircle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Members Table */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Active Collaborators ({members.length})
          </h3>
          <span className="text-xs text-slate-500">
            Your Role: <strong className="text-primary">{currentRole}</strong>
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800 uppercase tracking-wider font-semibold">
              <tr>
                <th className="px-6 py-3">User</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Joined Date</th>
                {canManageTeam && <th className="px-6 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {members.map((m) => {
                const isOwner = m.role === "Owner";
                return (
                  <tr key={m.id || m.user_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                        {m.user_full_name}
                      </div>
                      <div className="text-xs text-slate-500">{m.user_email}</div>
                    </td>

                    <td className="px-6 py-4">
                      {canManageTeam && !isOwner && currentRole === "Owner" ? (
                        <select
                          value={m.role}
                          onChange={(e) => handleRoleChange(m.id, e.target.value as BusinessRole)}
                          className="text-xs py-1 px-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-1 focus:ring-primary"
                        >
                          <option value="Administrator">Administrator</option>
                          <option value="Manager">Manager</option>
                          <option value="Analyst">Analyst</option>
                          <option value="Viewer">Viewer</option>
                        </select>
                      ) : (
                        <Badge variant="outline" className={`text-xs px-2.5 py-0.5 ${ROLE_BADGES[m.role] || ""}`}>
                          {m.role}
                        </Badge>
                      )}
                    </td>

                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        {m.status}
                      </span>
                    </td>

                    <td className="px-6 py-4 text-slate-500">
                      {new Date(m.joined_at).toLocaleDateString()}
                    </td>

                    {canManageTeam && (
                      <td className="px-6 py-4 text-right">
                        {!isOwner && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRemoveMember(m.id, m.user_full_name)}
                            className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 p-1.5 h-auto"
                            title="Remove Collaborator"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pending Invitations Section */}
      {canManageTeam && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Pending Invitations ({invitations.length})
              </h3>
              <p className="text-xs text-slate-500">
                Invitations expire 7 days after generation
              </p>
            </div>
          </div>

          {invitations.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No pending invitations for this business.
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {invitations.map((inv) => (
                <div
                  key={inv.id}
                  className="px-6 py-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                >
                  <div>
                    <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <Mail className="w-3.5 h-3.5 text-slate-400" />
                      {inv.email}
                      <Badge variant="outline" className={`text-[10px] px-2 py-0.2 ${ROLE_BADGES[inv.role]}`}>
                        {inv.role}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Expires: {new Date(inv.expires_at).toLocaleDateString()}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {inv.invitation_url && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopyInviteLink(inv)}
                        className="text-xs h-8 gap-1.5"
                      >
                        {copiedTokenId === inv.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        <span>{copiedTokenId === inv.id ? "Copied" : "Copy Link"}</span>
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRevokeInvitation(inv.id)}
                      className="text-xs h-8 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                    >
                      Revoke
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Transfer Ownership Section (Primary Owner Only) */}
      {currentRole === "Owner" && members.length > 1 && (
        <div className="p-6 rounded-2xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20 space-y-4">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-200 font-bold text-sm">
            <ArrowRightLeft className="w-4 h-4 text-amber-600" />
            Transfer Business Ownership
          </div>
          <p className="text-xs text-amber-800 dark:text-amber-300">
            Designate an active Administrator or Manager as the new primary owner of this business. As former owner, your account will be demoted to Administrator.
          </p>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <select
              value={transferUserId || ""}
              onChange={(e) => setTransferUserId(Number(e.target.value) || null)}
              className="text-xs p-2 rounded-xl border border-amber-300 dark:border-amber-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 min-w-[260px]"
            >
              <option value="">Select successor collaborator...</option>
              {members
                .filter((m) => m.role !== "Owner")
                .map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user_full_name} ({m.role} - {m.user_email})
                  </option>
                ))}
            </select>

            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!transferUserId || transferring}
              onClick={handleTransferOwnership}
              className="text-xs border-amber-400 text-amber-900 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
            >
              {transferring ? "Transferring..." : "Confirm Ownership Transfer"}
            </Button>
          </div>
        </div>
      )}

      <InviteMemberModal
        isOpen={isInviteModalOpen}
        onClose={() => setIsInviteModalOpen(false)}
        onSuccess={loadTeamData}
        currentUserRole={currentRole}
      />
    </div>
  );
}
