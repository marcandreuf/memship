"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
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
import { errorDetail } from "../lib/permission-groups";
import {
  useRoles,
  useSetUserActive,
  useUpdateUserRoles,
  useUserAccounts,
} from "../hooks/use-roles";
import type { Role, UserAccount } from "../services/roles-api";

export function UsersSettings() {
  const t = useTranslations();
  const { has } = usePermissions();
  const canWrite = has("users.write");

  const [search, setSearch] = useState("");
  const { data: users = [], isLoading } = useUserAccounts(search || undefined);
  const { data: roles = [] } = useRoles();

  const [assigning, setAssigning] = useState<UserAccount | null>(null);

  return (
    <div className="space-y-3 max-w-5xl">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 py-3 px-4">
          <div>
            <CardTitle className="text-base">{t("roles.users")}</CardTitle>
            <p className="text-xs text-muted-foreground">
              {t("roles.usersDescription")}
            </p>
          </div>
          <Input
            className="h-8 max-w-xs"
            placeholder={t("roles.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="user-search"
          />
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 table-compact">
          {isLoading ? (
            <TabContentSkeleton />
          ) : !users.length ? (
            <p className="text-sm text-muted-foreground">{t("common.noResults")}</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("profile.email")}</TableHead>
                    <TableHead>{t("profile.firstName")}</TableHead>
                    <TableHead>{t("roles.tab")}</TableHead>
                    <TableHead>{t("roles.active")}</TableHead>
                    <TableHead>{t("common.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((account) => (
                    <UserRow
                      key={account.id}
                      account={account}
                      // A full replacement re-sends every role the account
                      // holds, so an account holding something the caller
                      // cannot grant is not editable by them at all — better a
                      // hidden button than an escalation_blocked on save.
                      canWrite={
                        canWrite &&
                        roles.length > 0 &&
                        account.roles.every(
                          (held) => roles.find((r) => r.id === held.id)?.assignable
                        )
                      }
                      canDeactivate={canWrite}
                      onAssign={() => setAssigning(account)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={assigning !== null}
        onOpenChange={(o) => {
          if (!o) setAssigning(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("roles.tab")}</DialogTitle>
          </DialogHeader>
          {assigning && (
            <AssignRolesForm
              key={assigning.id}
              account={assigning}
              roles={roles}
              onSuccess={() => setAssigning(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UserRow({
  account,
  canWrite,
  canDeactivate,
  onAssign,
}: {
  account: UserAccount;
  canWrite: boolean;
  canDeactivate: boolean;
  onAssign: () => void;
}) {
  const t = useTranslations();
  const setActive = useSetUserActive();

  return (
    <TableRow
      className={account.is_active ? undefined : "opacity-60"}
      data-testid={`user-row-${account.email}`}
    >
      <TableCell className="font-medium">{account.email}</TableCell>
      <TableCell>
        {account.first_name} {account.last_name}
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {account.roles.map((role) => (
            <Badge
              key={role.id}
              variant={role.slug === "member" ? "secondary" : "default"}
            >
              {role.name}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>
        <Switch
          checked={account.is_active}
          disabled={!canDeactivate || setActive.isPending}
          onCheckedChange={async (checked) => {
            try {
              await setActive.mutateAsync({
                userId: account.id,
                isActive: checked,
              });
              toast.success(t("toast.success.saved"));
            } catch {
              /* global handler shows the error toast */
            }
          }}
          aria-label={account.is_active ? t("roles.active") : t("roles.inactive")}
        />
      </TableCell>
      <TableCell>
        {canWrite && (
          <Button variant="outline" size="sm" onClick={onAssign}>
            {t("common.edit")}
          </Button>
        )}
      </TableCell>
    </TableRow>
  );
}

function AssignRolesForm({
  account,
  roles,
  onSuccess,
}: {
  account: UserAccount;
  roles: Role[];
  onSuccess: () => void;
}) {
  const t = useTranslations();
  const mutation = useUpdateUserRoles();

  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(account.roles.map((r) => r.id))
  );

  function toggle(roleId: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(roleId);
      else next.delete(roleId);
      return next;
    });
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await mutation.mutateAsync({
        userId: account.id,
        roleIds: [...selected],
      });
      toast.success(t("toast.success.saved"));
      onSuccess();
    } catch (error) {
      const detail = errorDetail(error);
      switch (detail?.code) {
        case "escalation_blocked":
          toast.error(t("roles.notAssignable"));
          return;
        case "roles_required":
          toast.error(t("roles.rolesRequired"));
          return;
        case "last_super_admin":
          toast.error(t("roles.lastSuperAdmin"));
          return;
        default:
        /* global handler shows the error toast */
      }
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-sm text-muted-foreground">{account.email}</p>

      <div className="space-y-1.5">
        {roles.map((role) => {
          // `member` is pinned to every account and removable by nobody, so it
          // renders as a locked, always-checked row rather than a choice.
          const pinned = role.slug === "member";
          const reason = role.assignable
            ? null
            : role.slug === "super_admin"
              ? t("roles.superAdminOnly")
              : t("roles.notAssignable");

          return (
            <label
              key={role.id}
              className={`flex items-start gap-2 rounded-md border p-2 ${
                pinned || reason ? "opacity-70" : "cursor-pointer"
              }`}
              title={reason ?? undefined}
              data-testid={`assign-role-${role.slug}`}
            >
              <Checkbox
                className="mt-0.5"
                checked={pinned || selected.has(role.id)}
                disabled={pinned || Boolean(reason)}
                onCheckedChange={(checked) => toggle(role.id, checked === true)}
              />
              <span className="leading-tight">
                <span className="block text-xs font-medium">{role.name}</span>
                <span className="block text-xs text-muted-foreground">
                  {pinned
                    ? t("roles.memberPinned")
                    : (reason ?? role.description ?? "")}
                </span>
              </span>
            </label>
          );
        })}
      </div>

      <Button type="submit" disabled={mutation.isPending} className="w-full">
        {mutation.isPending ? t("common.loading") : t("common.save")}
      </Button>
    </form>
  );
}
