import { apiClient } from "./client";
import type { AuditLogListResponse, User, UserRole } from "../../types/api";

export interface AdminUserListParams {
  limit?: number;
  offset?: number;
}

export interface AuditLogQueryParams {
  user_id?: string;
  action?: string;
  status?: string;
  since?: string;
  limit?: number;
  offset?: number;
}

// Backs the Admin-only "User Management" page — every one of these is
// already live server-side, gated by Permission.USER_MANAGE (admin only)
// or Permission.AUDIT_LOG_READ, there was just no frontend consuming them.
export const adminApi = {
  listUsers: async (params: AdminUserListParams = {}): Promise<User[]> => {
    const response = await apiClient.get<User[]>("/auth/admin/users", { params });
    return response.data;
  },

  updateRole: async (userId: string, role: UserRole): Promise<User> => {
    const response = await apiClient.patch<User>(`/auth/admin/users/${userId}/role`, { role });
    return response.data;
  },

  updateActiveStatus: async (userId: string, isActive: boolean): Promise<User> => {
    const response = await apiClient.patch<User>(`/auth/admin/users/${userId}/active`, { is_active: isActive });
    return response.data;
  },

  auditLog: async (params: AuditLogQueryParams = {}): Promise<AuditLogListResponse> => {
    const response = await apiClient.get<AuditLogListResponse>("/auth/audit-log", { params });
    return response.data;
  },
};
