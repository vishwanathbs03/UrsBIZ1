"use client";

import React, { useState, useEffect } from "react";
import { X, Mail, Shield, Check, Copy, AlertCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  collaborationService,
  type BusinessRole,
  type InvitationOut,
} from "@/services";

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentUserRole?: BusinessRole;
}

const ROLE_DEFINITIONS: {
  role: BusinessRole;
  title: string;
  badgeColor: string;
  description: string;
  allowed: string[];
  restricted: string[];
}[] = [
  {
    role: "Administrator",
    title: "Administrator",
    badgeColor: "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border-purple-300 dark:border-purple-800",
    description: "Full management access to team members, settings, and business approvals.",
    allowed: ["Manage team collaborators", "Approve financial decisions", "Manage business goals", "Upload sales data", "Download reports"],
    restricted: ["Cannot delete business", "Cannot transfer primary ownership"],
  },
  {
    role: "Manager",
    title: "Manager",
    badgeColor: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-800",
    description: "Operational leadership managing goals, inventory, and reviewing operational requests.",
    allowed: ["Manage business goals", "Upload and confirm sales data", "Approve operational decisions", "Download reports"],
    restricted: ["Cannot invite or manage team members", "Cannot delete reports or ledger records"],
  },
  {
    role: "Analyst",
    title: "Analyst",
    badgeColor: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
    description: "Business intelligence and modeling: runs simulations, evaluates scenarios, and drafts proposals.",
    allowed: ["Propose decisions & budgets", "Run What-If simulations", "Generate reports", "View analytics & health scores"],
    restricted: ["Cannot approve financial decisions", "Cannot upload sales data", "Cannot delete data"],
  },
  {
    role: "Viewer",
    title: "Viewer",
    badgeColor: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700",
    description: "Read-only stakeholder access for passive monitoring and auditing.",
    allowed: ["View dashboard & analytics", "View goals & progress", "Download generated reports"],
    restricted: ["Cannot create or edit goals", "Cannot upload data", "Cannot delete records", "Cannot approve decisions"],
  },
];

export function InviteMemberModal({
  isOpen,
  onClose,
  onSuccess,
  currentUserRole = "Owner",
}: InviteMemberModalProps) {
  const [email, setEmail] = useState("");
  const [selectedRole, setSelectedRole] = useState<BusinessRole>("Manager");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdInvite, setCreatedInvite] = useState<InvitationOut | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleResetAndClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  // Filter available roles based on caller's role (escalation prevention)
  const allowedRoles = ROLE_DEFINITIONS.filter((def) => {
    if (currentUserRole === "Owner") return true;
    if (currentUserRole === "Administrator") return def.role !== "Administrator";
    return false;
  });

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please provide a valid email address.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await collaborationService.createInvitation({
        email: email.trim(),
        role: selectedRole,
      });
      setCreatedInvite(res);
      onSuccess();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to create invitation.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (!createdInvite?.invitation_url) return;
    const fullUrl = `${window.location.origin}${createdInvite.invitation_url}`;
    navigator.clipboard.writeText(fullUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleResetAndClose = () => {
    setEmail("");
    setSelectedRole("Manager");
    setError(null);
    setCreatedInvite(null);
    setCopied(false);
    onClose();
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Invite Team Member" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-xl rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Invite Team Member
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Assign role-based access for multi-user collaboration
              </p>
            </div>
          </div>
          <button
            onClick={handleResetAndClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="flex items-center gap-2 p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 rounded-xl">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {createdInvite ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50">
                <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-medium mb-1">
                  <Check className="w-4 h-4" />
                  Invitation Successfully Created!
                </div>
                <p className="text-xs text-emerald-700 dark:text-emerald-400">
                  An invitation has been generated for <strong>{createdInvite.email}</strong> as <strong>{createdInvite.role}</strong>. It expires in 7 days.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                  Invitation Acceptance Link
                </label>
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={
                      typeof window !== "undefined"
                        ? `${window.location.origin}${createdInvite.invitation_url}`
                        : createdInvite.invitation_url || ""
                    }
                    className="font-mono text-xs bg-slate-50 dark:bg-slate-950"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCopyLink}
                    className="flex-shrink-0 flex items-center gap-1.5"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </Button>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Share this secure link with the invited collaborator to activate their access.
                </p>
              </div>

              <div className="pt-2 flex justify-end">
                <Button onClick={handleResetAndClose}>
                  Done
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSendInvite} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                  <Input
                    type="email"
                    required
                    placeholder="collaborator@business.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                  Select Role & Permission Boundary
                </label>
                <div className="space-y-3">
                  {allowedRoles.map((def) => {
                    const isSelected = selectedRole === def.role;
                    return (
                      <div
                        key={def.role}
                        onClick={() => setSelectedRole(def.role)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                            : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-950"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                              {def.title}
                            </span>
                            <Badge variant="outline" className={`text-[10px] px-2 py-0.5 ${def.badgeColor}`}>
                              {def.role}
                            </Badge>
                          </div>
                          <div
                            className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                              isSelected
                                ? "border-primary bg-primary text-white"
                                : "border-slate-300 dark:border-slate-600"
                            }`}
                          >
                            {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
                          {def.description}
                        </p>
                        <div className="text-[11px] grid grid-cols-2 gap-1 text-slate-600 dark:text-slate-400">
                          <div>
                            <span className="text-emerald-600 dark:text-emerald-400 font-medium">✓ Allows: </span>
                            {def.allowed.slice(0, 2).join(", ")}
                          </div>
                          <div>
                            <span className="text-amber-600 dark:text-amber-400 font-medium">✗ Blocks: </span>
                            {def.restricted[0]}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-200 dark:border-slate-800">
                <Button type="button" variant="outline" onClick={handleResetAndClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading} className="gap-2">
                  {loading ? "Generating..." : "Generate Invitation"}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
