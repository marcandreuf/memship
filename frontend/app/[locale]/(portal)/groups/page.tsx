"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/lib/i18n/routing";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { PageInfo } from "@/components/page-info";
import { SearchInput } from "@/components/entity/search-input";
import { TableSkeleton } from "@/components/ui/skeletons";
import { useSearchParam } from "@/hooks/use-url-state";
import { useGroups, useCreateGroup } from "@/features/groups/hooks/use-groups";

const groupSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(100).regex(/^[a-z0-9-]+$/),
  description: z.string().max(2000).optional(),
  is_billable: z.boolean().optional(),
  color: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional().or(z.literal("")),
});

type GroupFormValues = z.infer<typeof groupSchema>;

export default function GroupsPage() {
  const t = useTranslations();
  const router = useRouter();
  const { data: groups, isLoading } = useGroups();
  const createMutation = useCreateGroup();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useSearchParam();

  const form = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: { name: "", slug: "", description: "", is_billable: true, color: "" },
  });

  async function onSubmit(data: GroupFormValues) {
    const payload = {
      ...data,
      color: data.color || undefined,
    };
    try {
      await createMutation.mutateAsync(payload);
      toast.success(t("toast.success.created"));
      setOpen(false);
      form.reset();
    } catch { /* global handler shows error toast */ }
  }

  // Client-side search filter
  const filteredGroups = groups?.filter((g) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      g.name.toLowerCase().includes(term) ||
      g.slug.toLowerCase().includes(term) ||
      (g.description && g.description.toLowerCase().includes(term))
    );
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">{t("groups.title")}</h1>
          <PageInfo text={t("groups.info")} />
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">{t("groups.createGroup")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("groups.createGroup")}</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.name")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="slug"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.slug")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.description")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="color"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("groups.color")}</FormLabel>
                      <FormControl>
                        <div className="flex gap-2">
                          <Input type="color" className="w-12 h-10 p-1" value={field.value || "#000000"} onChange={(e) => field.onChange(e.target.value)} />
                          <Input {...field} placeholder="#FF6B6B" className="flex-1" />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={createMutation.isPending} className="w-full">
                  {createMutation.isPending ? t("common.loading") : t("common.create")}
                </Button>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder={t("common.search")}
        className="sm:max-w-xs"
        minChars={1}
      />

      {isLoading ? (
        <TableSkeleton rows={4} columns={4} />
      ) : !filteredGroups?.length ? (
        <div className="py-8 text-center text-muted-foreground">{t("groups.noGroups")}</div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("groups.name")}</TableHead>
                  <TableHead>{t("groups.slug")}</TableHead>
                  <TableHead>{t("groups.billable")}</TableHead>
                  <TableHead>{t("groups.color")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredGroups.map((group) => (
                  <TableRow
                    key={group.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/groups/${group.id}`)}
                  >
                    <TableCell className="font-medium">{group.name}</TableCell>
                    <TableCell className="font-mono text-sm">{group.slug}</TableCell>
                    <TableCell>
                      <Badge variant={group.is_billable ? "default" : "outline"}>
                        {group.is_billable ? t("common.yes") : t("common.no")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {group.color && (
                        <div className="flex items-center gap-2">
                          <div
                            className="h-4 w-4 rounded-full border"
                            style={{ backgroundColor: group.color }}
                          />
                          <span className="font-mono text-xs">{group.color}</span>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile card view */}
          <div className="space-y-3 md:hidden">
            {filteredGroups.map((group) => (
              <div
                key={group.id}
                className="rounded-lg border p-4 hover:bg-accent transition-colors cursor-pointer"
                onClick={() => router.push(`/groups/${group.id}`)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{group.name}</p>
                    <p className="text-sm text-muted-foreground font-mono">{group.slug}</p>
                  </div>
                  <Badge variant={group.is_billable ? "default" : "outline"}>
                    {group.is_billable ? t("common.yes") : t("common.no")}
                  </Badge>
                </div>
                {group.description && (
                  <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                    {group.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
