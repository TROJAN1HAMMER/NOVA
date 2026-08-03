import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, type AdminUserListParams, type AuditLogQueryParams } from "../lib/api/admin";
import { queryKeys } from "../lib/queryClient";
import type { UserRole } from "../types/api";

export function useAdminUsers(params: AdminUserListParams = {}) {
  return useQuery({
    queryKey: queryKeys.adminUsers(params),
    queryFn: () => adminApi.listUsers(params),
  });
}

export function useUpdateUserRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) => adminApi.updateRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
}

export function useUpdateUserActiveStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      adminApi.updateActiveStatus(userId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
}

export function useAuditLog(params: AuditLogQueryParams = {}) {
  return useQuery({
    queryKey: queryKeys.auditLog(params),
    queryFn: () => adminApi.auditLog(params),
  });
}
