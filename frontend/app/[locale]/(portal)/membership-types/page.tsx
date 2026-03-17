"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { useMembershipTypes } from "@/features/members/hooks/use-members";
import { createMembershipType } from "@/features/members/services/members-api";
import { useQueryClient } from "@tanstack/react-query";

const createSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().min(1).max(100).regex(/^[a-z0-9-]+$/),
  description: z.string().optional(),
  base_price: z.coerce.number().min(0),
});

type CreateFormValues = z.infer<typeof createSchema>;

export default function MembershipTypesPage() {
  const t = useTranslations();
  const { data: types, isLoading } = useMembershipTypes();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: "", slug: "", description: "", base_price: 0 },
  });

  async function onSubmit(data: CreateFormValues) {
    setIsSubmitting(true);
    try {
      await createMembershipType(data);
      queryClient.invalidateQueries({ queryKey: ["membership-types"] });
      setOpen(false);
      form.reset();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("nav.membershipTypes")}</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>{t("common.create")}</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("members.createType")}</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.typeName")}</FormLabel>
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
                      <FormLabel>{t("members.typeSlug")}</FormLabel>
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
                      <FormLabel>{t("members.typeDescription")}</FormLabel>
                      <FormControl><Input {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="base_price"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.typePrice")}</FormLabel>
                      <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={isSubmitting} className="w-full">
                  {isSubmitting ? t("common.loading") : t("common.create")}
                </Button>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-muted-foreground">{t("common.loading")}</div>
      ) : !types?.length ? (
        <div className="py-8 text-center text-muted-foreground">{t("common.noResults")}</div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("members.typeName")}</TableHead>
                  <TableHead>{t("members.typeSlug")}</TableHead>
                  <TableHead>{t("members.typePrice")}</TableHead>
                  <TableHead>{t("common.status")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {types.map((type) => (
                  <TableRow key={type.id}>
                    <TableCell className="font-medium">{type.name}</TableCell>
                    <TableCell className="font-mono text-sm">{type.slug}</TableCell>
                    <TableCell>{type.base_price.toFixed(2)} EUR</TableCell>
                    <TableCell>
                      <Badge variant={type.is_active ? "default" : "outline"}>
                        {type.is_active ? t("status.active") : t("members.inactive")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
