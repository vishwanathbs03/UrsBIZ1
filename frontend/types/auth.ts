/**
 * Shared authentication-related types.
 *
 * Mirrors the backend Pydantic schemas in `app/schemas/auth.py`.
 */

export interface User {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  /**
   * Sprint 23 — the business row that "owns" the user's session
   * context. ``null`` when the user has not created a business
   * yet, or when all their businesses have been deleted.
   */
  active_business_id: number | null;
}

export interface UpdateActiveBusinessPayload {
  /**
   * ``null`` clears the active id. A positive integer must be one
   * of the user's owned businesses (the backend returns 403 if
   * it is owned by someone else).
   */
  active_business_id: number | null;
}

export interface AuthSuccess {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // seconds
  user: User;
}

export interface ApiErrorBody {
  detail?: string | Array<{ loc?: string[]; msg?: string; type?: string }>;
}
