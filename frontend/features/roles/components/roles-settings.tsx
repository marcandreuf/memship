"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TabContentSkeleton } from "@/components/ui/skeletons";
import { toast } from "sonner";
import { usePermissions } from "@/features/auth/hooks/use-permissions";
import { useSettings, useUpdateSettings } from "@/features/settings/hooks/use-settings";
import { errorDetail, groupPermissions } from "../lib/permission-groups";
import {
  useCreateRole,
  useDeleteRole,
  usePermissionCatalog,
  useRoles,
  useUpdateRole,
} from "../hooks/use-roles";
import type { Permission, Role } from "../services/roles-api";

export function RolesSettings() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("roles.write");

  const { data: settings } = useSettings();
  const updateSettings = useUpdateSettings();
  const enabled = Boolean(settings?.features?.custom_roles);

  // The whole roles API 404s while the flag is off — don't ask until it's on.
  const { data: roles = [], isLoading } = useRoles(enabled);
  const { data: catalog = [] } = usePermissionCatalog(enabled);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);

  function openCreate() {
    setEditing(null);
    setOpen(true);
  }

  async function onToggle(checked: boolean) {
    try {
      // PUT /settings replaces the whole features dict — merge to keep siblings.
      await updateSettings.mutateAsync({
        features: { ...(settings?.features ?? {}), custom_roles: checked },
      });
      toast.success(t("toast.success.saved"));
    } catch {
      /* global handler shows the error toast */
    }
  }

  return (
    <div className="space-y-3 max-w-5xl">
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("roles.tab")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0">
          <div className="flex items-center justify-between gap-2 rounded-lg border p-2.5">
            <div>
              <p className="text-xs font-medium">{t("roles.enabled")}</p>
              <p className="text-xs text-muted-foreground">
                {t("roles.enabledDesc")}
              </p>
            </div>
            <Switch
              checked={enabled}
              onCheckedChange={onToggle}
              disabled={!has("settings.write") || updateSettings.isPending}
              data-testid="custom-roles-toggle"
            />
          </div>
        </CardContent>
      </Card>

      {enabled && (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
          <div>
            <CardTitle className="text-base">{t("roles.title")}</CardTitle>
            <p className="text-xs text-muted-foreground">{t("roles.description")}</p>
          </div>
          {canWrite && (
            <Button variant="outline" size="sm" onClick={openCreate}>
              {t("roles.create")}
            </Button>
          )}
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 table-compact">
          {isLoading ? (
            <TabContentSkeleton />
          ) : !roles.length ? (
            <p className="text-sm text-muted-foreground">{t("common.noResults")}</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("roles.name")}</TableHead>
                    <TableHead>{t("roles.permissions")}</TableHead>
                    <TableHead>{t("roles.users")}</TableHead>
                    <TableHead>{t("common.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {roles.map((role) => (
                    <RoleRow
                      key={role.id}
                      role={role}
                      canWrite={canWrite}
                      onEdit={() => {
                        setEditing(role);
                        setOpen(true);
                      }}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      )}

      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) setEditing(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {editing ? t("roles.edit") : t("roles.create")}
            </DialogTitle>
          </DialogHeader>
          {/* Remount per target so the form always starts from that role. */}
          <RoleForm
            key={editing?.id ?? "new"}
            role={editing}
            catalog={catalog}
            onSuccess={() => {
              setOpen(false);
              setEditing(null);
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function RoleRow({
  role,
  canWrite,
  onEdit,
}: {
  role: Role;
  canWrite: boolean;
  onEdit: () => void;
}) {
  const t = useTranslations();
  const deleteMutation = useDeleteRole();
  const [confirmDialog, confirmAction] = useConfirmDialog();

  // super_admin holds the catalog implicitly and is locked end to end; the API
  // refuses to update it, so the row offers nothing to click.
  const isSuperAdmin = role.slug === "super_admin";

  return (
    <TableRow data-testid={`role-row-${role.slug}`}>
      <TableCell className="font-medium">
        {role.name}
        {role.is_system && (
          <Badge variant="secondary" className="ml-2">
            {t("roles.system")}
          </Badge>
        )}
        {role.description && (
          <p className="text-xs text-muted-foreground">{role.description}</p>
        )}
      </TableCell>
      <TableCell className="font-mono text-xs">
        {isSuperAdmin ? "—" : role.permission_keys.length}
      </TableCell>
      <TableCell>{t("roles.assignedUsers", { count: role.assigned_user_count })}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          {confirmDialog}
          {isSuperAdmin || !canWrite ? (
            <span
              className="flex items-center gap-1 text-xs text-muted-foreground"
              title={t("roles.locked")}
            >
              <Lock className="h-3 w-3" />
            </span>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={onEdit}>
                {t("common.edit")}
              </Button>
              {/* A system role keeps its name and cannot be deleted; only its
                  permission set is tunable, which Edit already covers. */}
              {!role.is_system && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={deleteMutation.isPending}
                  onClick={() =>
                    confirmAction({
                      title: t("roles.confirmDelete"),
                      cancelLabel: t("common.cancel"),
                      confirmLabel: t("common.delete"),
                      onConfirm: async () => {
                        try {
                          await deleteMutation.mutateAsync(role.id);
                          toast.success(t("toast.success.deleted"));
                        } catch (error) {
                          const detail = errorDetail(error);
                          if (detail?.code === "role_in_use") {
                            toast.error(
                              t("roles.inUse", {
                                count: Number(detail.assigned_user_count ?? 0),
                              })
                            );
                          }
                          /* anything else: the global handler toasts it */
                        }
                      },
                    })
                  }
                >
                  {t("common.delete")}
                </Button>
              )}
            </>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

function RoleForm({
  role,
  catalog,
  onSuccess,
}: {
  role: Role | null;
  catalog: Permission[];
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const createMutation = useCreateRole();
  const updateMutation = useUpdateRole();

  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(role?.permission_keys ?? [])
  );
  const [nameError, setNameError] = useState<string | null>(null);

  const isSystem = Boolean(role?.is_system);
  const { administrative, selfService } = useMemo(
    () => groupPermissions(catalog),
    [catalog]
  );

  function toggle(key: string, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!isSystem && !name.trim()) {
      setNameError(t("roles.name"));
      return;
    }
    setNameError(null);

    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      permission_keys: [...selected],
    };

    try {
      if (role) {
        await updateMutation.mutateAsync({ id: role.id, data: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      const detail = errorDetail(error);
      if (detail?.code === "role_slug_exists") {
        setNameError(t("roles.slugExists", { name: String(detail.name ?? "") }));
        return;
      }
      if (detail?.code === "reserved_permissions") {
        toast.error(t("roles.reserved"));
        return;
      }
      /* anything else: the global handler toasts it */
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label className="text-xs">{t("roles.name")}</Label>
          <Input
            className="h-8"
            value={name}
            disabled={isSystem}
            onChange={(e) => setName(e.target.value)}
            data-testid="role-name"
          />
          {isSystem && (
            <p className="text-xs text-muted-foreground">{t("roles.locked")}</p>
          )}
          {nameError && <p className="text-xs text-destructive">{nameError}</p>}
        </div>
        <div className="space-y-1">
          <Label className="text-xs">{t("roles.roleDescription")}</Label>
          <Textarea
            className="min-h-8"
            rows={2}
            value={description}
            disabled={isSystem}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </div>

      {/* Retuning `member` reaches every account in the club, staff included,
          because it is pinned to all of them. */}
      {role?.slug === "member" && (
        <p className="rounded-md border border-dashed p-2 text-xs text-muted-foreground">
          {t("roles.memberPinned")}
        </p>
      )}

      <PermissionSection
        title={t("roles.administrative")}
        groups={administrative}
        selected={selected}
        isSystem={isSystem}
        onToggle={toggle}
      />
      <PermissionSection
        title={t("roles.selfService")}
        groups={selfService}
        selected={selected}
        isSystem={isSystem}
        onToggle={toggle}
      />

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? t("common.loading") : t("common.save")}
      </Button>
    </form>
  );
}

function PermissionSection({
  title,
  groups,
  selected,
  isSystem,
  onToggle,
}: {
  title: string;
  groups: [string, Permission[]][];
  selected: Set<string>;
  isSystem: boolean;
  onToggle: (key: string, checked: boolean) => void;
}) {
  const t = useTranslations();

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{title}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {groups.map(([group, permissions]) => (
          <div key={group} className="space-y-1.5 rounded-lg border p-2.5">
            <p className="text-xs font-medium text-muted-foreground">
              {t(`roles.domains.${group}`)}
            </p>
            {permissions.map((permission) => {
              // Reserved keys are rejected on any non-system role, so the box
              // is disabled rather than left to fail on submit.
              const locked = permission.reserved && !isSystem;
              return (
                <label
                  key={permission.key}
                  className={`flex items-start gap-2 ${locked ? "opacity-60" : "cursor-pointer"}`}
                  title={locked ? t("roles.reserved") : undefined}
                >
                  <Checkbox
                    className="mt-0.5"
                    checked={selected.has(permission.key)}
                    disabled={locked}
                    onCheckedChange={(checked) =>
                      onToggle(permission.key, checked === true)
                    }
                    data-testid={`permission-${permission.key}`}
                  />
                  <span className="leading-tight">
                    <span className="block text-xs font-medium">
                      {t(permission.label_key)}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {t(permission.description_key)}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
