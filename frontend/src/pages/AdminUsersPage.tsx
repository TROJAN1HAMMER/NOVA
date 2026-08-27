import { useState } from "react";
import { ChevronLeft, ChevronRight, ScrollText, Sliders, Users } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { EmptyState } from "../components/ui/EmptyState";
import { Spinner } from "../components/ui/Spinner";
import { SkeletonTable } from "../components/ui/Skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { SystemSettingsPanel } from "../components/admin/SystemSettingsPanel";
import { useAdminUsers, useAuditLog, useUpdateUserActiveStatus, useUpdateUserRole } from "../hooks/useAdmin";
import { useToast } from "../hooks/useToast";
import { ALL_ROLES, ROLE_DISPLAY_NAMES } from "../lib/rbac";
import { cn, formatDateTime } from "../lib/utils";
import type { UserRole } from "../types/api";

const AUDIT_LOG_PAGE_SIZE = 20;

type AdminTab = "users" | "settings" | "audit";

export default function AdminUsersPage() {
  const [activeTab, setActiveTab] = useState<AdminTab>("users");

  const { data: users, isLoading, isError } = useAdminUsers({ limit: 200 });
  const updateRole = useUpdateUserRole();
  const updateActive = useUpdateUserActiveStatus();
  const toast = useToast();

  const [auditOffset, setAuditOffset] = useState(0);
  const { data: auditLog, isLoading: loadingAuditLog } = useAuditLog({
    limit: AUDIT_LOG_PAGE_SIZE,
    offset: auditOffset,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration"
        description="Manage user accounts, RBAC permissions, RAG hyperparameters, and review security audit logs."
      />

      {/* Admin Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-border/80 pb-3">
        <button
          onClick={() => setActiveTab("users")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150",
            activeTab === "users"
              ? "bg-primary/10 text-primary border border-primary/20 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <Users className="size-4" />
          <span>User Management</span>
          {users && (
            <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {users.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150",
            activeTab === "settings"
              ? "bg-primary/10 text-primary border border-primary/20 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <Sliders className="size-4" />
          <span>System Configuration</span>
        </button>

        <button
          onClick={() => setActiveTab("audit")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150",
            activeTab === "audit"
              ? "bg-primary/10 text-primary border border-primary/20 shadow-xs"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <ScrollText className="size-4" />
          <span>Platform Audit Log</span>
          {auditLog && (
            <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {auditLog.total}
            </span>
          )}
        </button>
      </div>

      {/* Tab 1: User Management */}
      {activeTab === "users" && (
        <div>
          {isError && (
            <Card className="mb-4 border-danger/30 bg-danger/5 p-4 text-sm text-danger">
              Failed to load users. Check your connection and try again.
            </Card>
          )}

          {isLoading ? (
            <SkeletonTable rows={6} columns={5} className="mb-6" />
          ) : users && users.length === 0 ? (
            <EmptyState icon={<Users className="size-10" />} title="No users found" />
          ) : (
            <RevealSection>
              <RevealItem>
                <Card className="mb-6">
                  <CardHeader title="Users" description={`${users?.length ?? 0} account(s)`} />

                  <Table>
                    <TableHead>
                      <tr>
                        <TableHeaderCell>Email</TableHeaderCell>
                        <TableHeaderCell>Full name</TableHeaderCell>
                        <TableHeaderCell>Role</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell className="text-right">Actions</TableHeaderCell>
                      </tr>
                    </TableHead>
                    <TableBody>
                      {users?.map((user) => {
                        const isUpdatingThisRole =
                          updateRole.isPending && updateRole.variables?.userId === user.id;
                        const isUpdatingThisActive =
                          updateActive.isPending && updateActive.variables?.userId === user.id;
                        return (
                          <TableRow key={user.id}>
                            <TableCell className="font-medium">{user.email}</TableCell>
                            <TableCell className="text-muted-foreground">{user.full_name || "—"}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Select
                                  className="h-9 w-52"
                                  value={user.role}
                                  disabled={isUpdatingThisRole}
                                  onChange={(e) => {
                                    const role = e.target.value as UserRole;
                                    updateRole.mutate(
                                      { userId: user.id, role },
                                      {
                                        onSuccess: () =>
                                          toast.success(
                                            "Role updated",
                                            `${user.email} is now ${ROLE_DISPLAY_NAMES[role]}.`,
                                          ),
                                        onError: () =>
                                          toast.error("Failed to update role", "Please try again."),
                                      },
                                    );
                                  }}
                                >
                                  {ALL_ROLES.map((role) => (
                                    <option key={role} value={role}>
                                      {ROLE_DISPLAY_NAMES[role]}
                                    </option>
                                  ))}
                                </Select>
                                {isUpdatingThisRole && <Spinner className="size-4" />}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge tone={user.is_active ? "success" : "neutral"}>
                                {user.is_active ? "Active" : "Inactive"}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="outline"
                                size="sm"
                                isLoading={isUpdatingThisActive}
                                onClick={() => {
                                  const nextActive = !user.is_active;
                                  updateActive.mutate(
                                    { userId: user.id, isActive: nextActive },
                                    {
                                      onSuccess: () =>
                                        toast.success(
                                          nextActive ? "User activated" : "User deactivated",
                                          user.email,
                                        ),
                                      onError: () =>
                                        toast.error("Failed to update status", "Please try again."),
                                    },
                                  );
                                }}
                              >
                                {user.is_active ? "Deactivate" : "Activate"}
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </Card>
              </RevealItem>
            </RevealSection>
          )}
        </div>
      )}

      {/* Tab 2: System Configuration */}
      {activeTab === "settings" && <SystemSettingsPanel />}

      {/* Tab 3: Platform Audit Log */}
      {activeTab === "audit" && (
        <RevealSection>
          <RevealItem>
            <Card>
              <CardHeader
                title="Audit Log"
                description="Recent authentication and administrative actions across NOVA."
              />
              {loadingAuditLog ? (
                <div className="flex justify-center p-8">
                  <Spinner />
                </div>
              ) : !auditLog || auditLog.entries.length === 0 ? (
                <div className="p-5">
                  <EmptyState icon={<ScrollText className="size-10" />} title="No audit log entries" />
                </div>
              ) : (
                <>
                  <Table>
                    <TableHead>
                      <tr>
                        <TableHeaderCell>Action</TableHeaderCell>
                        <TableHeaderCell>User</TableHeaderCell>
                        <TableHeaderCell>Resource</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell>Time</TableHeaderCell>
                      </tr>
                    </TableHead>
                    <TableBody>
                      {auditLog.entries.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell className="font-medium">{entry.action}</TableCell>
                          <TableCell className="text-muted-foreground">{entry.user_email ?? "—"}</TableCell>
                          <TableCell className="text-muted-foreground">
                            {entry.resource_type
                              ? `${entry.resource_type}${entry.resource_id ? ` / ${entry.resource_id}` : ""}`
                              : "—"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              tone={
                                entry.status === "success"
                                  ? "success"
                                  : entry.status === "denied"
                                    ? "danger"
                                    : "neutral"
                              }
                            >
                              {entry.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {formatDateTime(entry.created_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <div className="flex items-center justify-between border-t border-border p-4">
                    <p className="text-xs text-muted-foreground">
                      Showing {auditOffset + 1}–{auditOffset + auditLog.entries.length} of {auditLog.total}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={auditOffset === 0}
                        onClick={() => setAuditOffset((offset) => Math.max(0, offset - AUDIT_LOG_PAGE_SIZE))}
                      >
                        <ChevronLeft className="size-4" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={auditOffset + AUDIT_LOG_PAGE_SIZE >= auditLog.total}
                        onClick={() => setAuditOffset((offset) => offset + AUDIT_LOG_PAGE_SIZE)}
                      >
                        Next
                        <ChevronRight className="size-4" />
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </Card>
          </RevealItem>
        </RevealSection>
      )}
    </div>
  );
}
