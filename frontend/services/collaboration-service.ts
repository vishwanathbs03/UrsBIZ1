"use client";

/**
 * Frontend client service for MSME Collaboration & Approval Workflow (RBAC) (Phase 6.26).
 *
 * Connects to authoritative backend endpoints under:
 *   /api/v1/collaboration:
 *     GET    /members
 *     PUT    /members/{id}
 *     DELETE /members/{id}
 *     POST   /invitations
 *     GET    /invitations
 *     DELETE /invitations/{id}
 *     POST   /invitations/accept
 *     POST   /transfer-ownership
 *   /api/v1/approvals:
 *     POST   /
 *     GET    /
 *     GET    /summary
 *     GET    /{id}
 *     POST   /{id}/review
 *     POST   /{id}/cancel
 */

import { apiClient } from "./api-client";

export type BusinessRole = "Owner" | "Administrator" | "Manager" | "Analyst" | "Viewer";

export type ApprovalEntityType = "DECISION" | "RECOMMENDATION" | "BUDGET" | "DISCOUNT" | "GOAL";

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";

export interface MemberOut {
  id: number;
  business_id: number;
  user_id: number;
  user_email: string;
  user_full_name: string;
  role: BusinessRole;
  status: string;
  joined_at: string;
  invited_by_email?: string | null;
}

export interface MemberListResponse {
  business_id: number;
  total_members: number;
  current_user_role: BusinessRole;
  members: MemberOut[];
}

export interface InvitationOut {
  id: number;
  business_id: number;
  email: string;
  role: BusinessRole;
  status: string;
  token?: string | null;
  expires_at: string;
  created_at: string;
  invited_by_user_id?: number | null;
  invitation_url?: string | null;
}

export interface InvitationListResponse {
  business_id: number;
  invitations: InvitationOut[];
}

export interface InvitationCreateRequest {
  email: string;
  role: BusinessRole;
}

export interface InvitationAcceptRequest {
  token: string;
}

export interface InvitationAcceptResponse {
  success: boolean;
  message: string;
  business_id: number;
  business_name: string;
  role: BusinessRole;
}

export interface TransferOwnershipRequest {
  new_owner_user_id: number;
  reason?: string | null;
}

export interface TransferOwnershipResponse {
  success: boolean;
  message: string;
  business_id: number;
  previous_owner_id: number;
  new_owner_id: number;
}

export interface ApprovalAuditOut {
  id: number;
  action: string;
  previous_status?: string | null;
  new_status?: string | null;
  notes?: string | null;
  user_id?: number | null;
  user_email?: string | null;
  created_at: string;
}

export interface ApprovalRequestOut {
  id: number;
  business_id: number;
  requester_user_id: number;
  requester_name?: string | null;
  requester_email?: string | null;
  entity_type: ApprovalEntityType;
  entity_id: string;
  title: string;
  description?: string | null;
  financial_impact_amount?: number | null;
  status: ApprovalStatus;
  approver_user_id?: number | null;
  approver_name?: string | null;
  decision_notes?: string | null;
  requested_at: string;
  reviewed_at?: string | null;
  audits: ApprovalAuditOut[];
}

export interface ApprovalRequestCreate {
  entity_type: ApprovalEntityType;
  entity_id: string;
  title: string;
  description?: string | null;
  financial_impact_amount?: number | null;
}

export interface ApprovalReviewRequest {
  action: "APPROVE" | "REJECT";
  decision_notes?: string | null;
}

export interface ApprovalListResponse {
  business_id: number;
  total: number;
  requests: ApprovalRequestOut[];
}

export interface ApprovalSummaryResponse {
  business_id: number;
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  cancelled: number;
}

class CollaborationService {
  /**
   * List all team members and their roles for the active business.
   */
  async listMembers(): Promise<MemberListResponse> {
    return apiClient.get<MemberListResponse>("/api/v1/collaboration/members");
  }

  /**
   * Invite a new collaborator.
   */
  async createInvitation(req: InvitationCreateRequest): Promise<InvitationOut> {
    return apiClient.post<InvitationOut>("/api/v1/collaboration/invitations", req);
  }

  /**
   * List pending invitations.
   */
  async listInvitations(): Promise<InvitationListResponse> {
    return apiClient.get<InvitationListResponse>("/api/v1/collaboration/invitations");
  }

  /**
   * Revoke a pending invitation.
   */
  async revokeInvitation(invitationId: number): Promise<{ success: boolean; message: string }> {
    return apiClient.delete<{ success: boolean; message: string }>(
      `/api/v1/collaboration/invitations/${invitationId}`
    );
  }

  /**
   * Accept an invitation with a secure token.
   */
  async acceptInvitation(token: string): Promise<InvitationAcceptResponse> {
    return apiClient.post<InvitationAcceptResponse>("/api/v1/collaboration/invitations/accept", {
      token,
    });
  }

  /**
   * Update a collaborator's role.
   */
  async updateMemberRole(memberId: number, role: BusinessRole): Promise<MemberOut> {
    return apiClient.put<MemberOut>(`/api/v1/collaboration/members/${memberId}`, { role });
  }

  /**
   * Remove a collaborator from the business.
   */
  async removeMember(memberId: number): Promise<{ success: boolean; message: string }> {
    return apiClient.delete<{ success: boolean; message: string }>(
      `/api/v1/collaboration/members/${memberId}`
    );
  }

  /**
   * Transfer sole ownership of the business to an active collaborator.
   */
  async transferOwnership(req: TransferOwnershipRequest): Promise<TransferOwnershipResponse> {
    return apiClient.post<TransferOwnershipResponse>(
      "/api/v1/collaboration/transfer-ownership",
      req
    );
  }

  /**
   * List approval requests with optional status filter.
   */
  async listApprovalRequests(status?: string): Promise<ApprovalListResponse> {
    const url = status && status !== "ALL"
      ? `/api/v1/approvals?status=${encodeURIComponent(status)}`
      : "/api/v1/approvals";
    return apiClient.get<ApprovalListResponse>(url);
  }

  /**
   * Get summary counts of approvals.
   */
  async getApprovalSummary(): Promise<ApprovalSummaryResponse> {
    return apiClient.get<ApprovalSummaryResponse>("/api/v1/approvals/summary");
  }

  /**
   * Retrieve a single approval request with its complete audit history.
   */
  async getApprovalRequest(requestId: number): Promise<ApprovalRequestOut> {
    return apiClient.get<ApprovalRequestOut>(`/api/v1/approvals/${requestId}`);
  }

  /**
   * Submit an entity for managerial approval.
   */
  async submitApprovalRequest(req: ApprovalRequestCreate): Promise<ApprovalRequestOut> {
    return apiClient.post<ApprovalRequestOut>("/api/v1/approvals", req);
  }

  /**
   * Approve or reject a pending approval request.
   */
  async reviewApprovalRequest(
    requestId: number,
    req: ApprovalReviewRequest
  ): Promise<ApprovalRequestOut> {
    return apiClient.post<ApprovalRequestOut>(`/api/v1/approvals/${requestId}/review`, req);
  }

  /**
   * Cancel a pending approval request.
   */
  async cancelApprovalRequest(requestId: number): Promise<ApprovalRequestOut> {
    return apiClient.post<ApprovalRequestOut>(`/api/v1/approvals/${requestId}/cancel`, {});
  }
}

export const collaborationService = new CollaborationService();
