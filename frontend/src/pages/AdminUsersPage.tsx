import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  ScrollText,
  Sliders,
  Users,
  Search,
  ShieldCheck,
  UserCheck,
  Activity,
  Key,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardHeader, CardContent } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { EmptyState } from "../components/ui/EmptyState";
import { Spinner } from "../components/ui/Spinner";
import { SkeletonTable } from "../components/ui/Skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell } from "../components/ui/Table";
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
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");

  const { data: users, isLoading, isError } = useAdminUsers({ limit: 200 });
  const updateRole = useUpdateUserRole();
  const updateActive = useUpdateUserActiveStatus();
  const toast = useToast();

  const [auditOffset, setAuditOffset] = useState(0);
  const { data: auditLog, isLoading: loadingAuditLog } = useAuditLog({
    limit: AUDIT_LOG_PAGE_SIZE,
    offset: auditOffset,
  });

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    return users.filter((u) => {
      const matchesSearch =
        u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (u.full_name && u.full_name.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesRole = roleFilter === "all" || u.role === roleFilter;
      return matchesSearch && matchesRole;
    });
  }, [users, searchQuery, roleFilter]);

  const adminCount = useMemo(() => users?.filter((u) => u.role === "admin").length ?? 0, [users]);
  const activeCount = useMemo(() => users?.filter((u) => u.is_active).length ?? 0, [users]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration & Governance Control"
        description="Manage user accounts, RBAC permissions, RAG hyperparameters, and review real-time security audit logs."
      />

      {/* Animated Top Summary Stats */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="grid grid-cols-1 gap-4 sm:grid-cols-4"
      >
        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-primary/15 via-card to-card border-primary/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Users className="size-4 text-primary" /> Active Accounts
            </span>
            <Badge tone="success">{activeCount} Online</Badge>
          </div>
          <div className="text-3xl font-bold text-foreground font-mono">{users?.length ?? 0}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Total registered users</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-emerald-500/15 via-card to-card border-emerald-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <ShieldCheck className="size-4 text-emerald-400" /> Platform Admins
            </span>
            <Badge tone="primary">{adminCount} Admins</Badge>
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono">{adminCount}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Full platform access</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-amber-500/15 via-card to-card border-amber-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Activity className="size-4 text-amber-400" /> Security Audit Log
            </span>
            <Badge tone="neutral">Live</Badge>
          </div>
          <div className="text-3xl font-bold text-foreground font-mono">{auditLog?.total ?? 0}</div>
          <div className="text-[11px] text-muted-foreground mt-1">Telemetry events recorded</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-purple-500/15 via-card to-card border-purple-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Key className="size-4 text-purple-400" /> RBAC Enforcer
            </span>
            <Badge tone="success">100% ACTIVE</Badge>
          </div>
          <div className="text-3xl font-bold text-purple-400 font-mono">5 Roles</div>
          <div className="text-[11px] text-muted-foreground mt-1">Zero-Trust permission gating</div>
        </Card>
      </motion.div>

      {/* Admin Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-border/80 pb-3">
        <button
          onClick={() => setActiveTab("users")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-200",
            activeTab === "users"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-sm"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <Users className="size-4" />
          <span>User Management</span>
          {users && (
            <span className="ml-1 rounded-full bg-primary/30 px-2 py-0.5 text-xs text-primary font-mono font-bold">
              {users.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-200",
            activeTab === "settings"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-sm"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <Sliders className="size-4" />
          <span>System Configuration</span>
        </button>

        <button
          onClick={() => setActiveTab("audit")}
          className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-200",
            activeTab === "audit"
              ? "bg-primary/20 text-primary border border-primary/40 shadow-sm"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          <ScrollText className="size-4" />
          <span>Platform Audit Log</span>
          {auditLog && (
            <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground font-mono">
              {auditLog.total}
            </span>
          )}
        </button>
      </div>

      {/* Tab 1: User Management */}
      {activeTab === "users" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
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
              <Card>
                <CardHeader
                  title="Registered Platform Accounts"
                  description="Assign roles, adjust permission scopes, and manage user statuses."
                  action={
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="relative">
                        <Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          placeholder="Search email or name..."
                          className="w-48 sm:w-64 rounded-lg border border-border bg-background pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                        />
                      </div>
                      <Select
                        className="h-8 text-xs w-36"
                        value={roleFilter}
                        onChange={(e) => setRoleFilter(e.target.value)}
                      >
                        <option value="all">All Roles</option>
                        {ALL_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_DISPLAY_NAMES[r]}
                          </option>
                        ))}
                      </Select>
                    </div>
                  }
                />

                <CardContent className="p-0 overflow-x-auto">
                  <Table>
                    <TableHead>
                      <tr>
                        <TableHeaderCell>User Profile</TableHeaderCell>
                        <TableHeaderCell>Full Name</TableHeaderCell>
                        <TableHeaderCell>Assigned RBAC Role</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell className="text-right">Actions</TableHeaderCell>
                      </tr>
                    </TableHead>
                    <TableBody>
                      {filteredUsers.map((user, idx) => {
                        const isUpdatingThisRole =
                          updateRole.isPending && updateRole.variables?.userId === user.id;
                        const isUpdatingThisActive =
                          updateActive.isPending && updateActive.variables?.userId === user.id;
                        const firstChar = user.email.charAt(0).toUpperCase();

                        return (
                          <motion.tr
                            key={user.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.2, delay: idx * 0.03 }}
                            className="hover:bg-muted/30 transition-colors"
                          >
                            <TableCell className="font-medium">
                              <div className="flex items-center gap-3">
                                <div className="flex size-8 items-center justify-center rounded-full bg-primary/20 font-bold text-primary text-xs shrink-0">
                                  {firstChar}
                                </div>
                                <span className="text-foreground">{user.email}</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-muted-foreground">{user.full_name || "—"}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Select
                                  className="h-8 text-xs w-48 font-medium"
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
                                {isUpdatingThisRole && <Spinner className="size-3.5" />}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge tone={user.is_active ? "success" : "neutral"} className="animate-pulse">
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
                          </motion.tr>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </motion.div>
        </AnimatePresence>
      )}

      {/* Tab 2: System Configuration */}
      {activeTab === "settings" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
            <SystemSettingsPanel />
          </motion.div>
        </AnimatePresence>
      )}

      {/* Tab 3: Platform Audit Log */}
      {activeTab === "audit" && (
        <AnimatePresence mode="wait">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
            <Card>
              <CardHeader
                title="Audit Telemetry Log"
                description="Recent authentication, policy modifications, and administrative actions across NOVA."
              />
              <CardContent className="p-0">
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
                          <TableHeaderCell>Action Event</TableHeaderCell>
                          <TableHeaderCell>Actor Email</TableHeaderCell>
                          <TableHeaderCell>Target Resource</TableHeaderCell>
                          <TableHeaderCell>Execution Status</TableHeaderCell>
                          <TableHeaderCell>Timestamp</TableHeaderCell>
                        </tr>
                      </TableHead>
                      <TableBody>
                        {auditLog.entries.map((entry, idx) => (
                          <motion.tr
                            key={entry.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.15, delay: idx * 0.02 }}
                            className="hover:bg-muted/30 transition-colors"
                          >
                            <TableCell className="font-mono text-xs text-foreground font-semibold flex items-center gap-2">
                              <UserCheck className="size-3.5 text-primary shrink-0" />
                              {entry.action}
                            </TableCell>
                            <TableCell className="text-muted-foreground font-medium">{entry.user_email ?? "—"}</TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
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
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {formatDateTime(entry.created_at)}
                            </TableCell>
                          </motion.tr>
                        ))}
                      </TableBody>
                    </Table>
                    <div className="flex items-center justify-between border-t border-border p-4">
                      <p className="text-xs text-muted-foreground">
                        Showing {auditOffset + 1}–{auditOffset + auditLog.entries.length} of {auditLog.total} entries
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
              </CardContent>
            </Card>
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}
