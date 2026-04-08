"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useLocale } from "next-intl";
import { useMembershipTypes } from "../hooks/use-members";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { MemberData } from "../services/members-api";
import type { GenderOption } from "@/features/settings/components/gender-options-settings";

const memberSchema = z.object({
  first_name: z.string().min(1).max(100),
  last_name: z.string().min(1).max(100),
  email: z.string().email().optional().or(z.literal("")),
  date_of_birth: z.string().optional().or(z.literal("")),
  gender: z.string().optional().or(z.literal("")),
  national_id: z.string().optional().or(z.literal("")),
  membership_type_id: z.number().optional(),
  internal_notes: z.string().max(2000).optional().or(z.literal("")),
});

type MemberFormValues = z.infer<typeof memberSchema>;

interface MemberFormProps {
  member?: MemberData;
  onSubmit: (data: MemberFormValues) => Promise<void>;
  isSubmitting: boolean;
  onCancel?: () => void;
}

export function MemberForm({ member, onSubmit, isSubmitting, onCancel }: MemberFormProps) {
  const t = useTranslations();
  const locale = useLocale();
  const { data: membershipTypes } = useMembershipTypes();
  const { data: settings } = useSettings();
  const genderOptions = (settings?.features?.gender_options as GenderOption[] | undefined) || [];

  const form = useForm<MemberFormValues>({
    resolver: zodResolver(memberSchema),
    defaultValues: {
      first_name: member?.person.first_name || "",
      last_name: member?.person.last_name || "",
      email: member?.person.email || "",
      date_of_birth: member?.person.date_of_birth || "",
      gender: member?.person.gender || "",
      national_id: member?.person.national_id || "",
      membership_type_id: member?.membership_type_id || undefined,
      internal_notes: member?.internal_notes || "",
    },
  });

  const formContent = (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-3"
      >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="first_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("auth.firstName")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="last_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("auth.lastName")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("auth.email")}</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <FormField
                control={form.control}
                name="date_of_birth"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("members.dateOfBirth")}</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {genderOptions.length > 0 && (
                <FormField
                  control={form.control}
                  name="gender"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t("members.gender")}</FormLabel>
                      <Select
                        value={field.value || ""}
                        onValueChange={field.onChange}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="—" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {genderOptions.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt[`label_${locale}` as keyof GenderOption] || opt.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="national_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("members.nationalId")}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {membershipTypes && membershipTypes.length > 0 && (
              <FormField
                control={form.control}
                name="membership_type_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("members.membershipType")}</FormLabel>
                    <Select
                      value={field.value?.toString() || ""}
                      onValueChange={(v) => field.onChange(Number(v))}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t("members.selectType")} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {membershipTypes
                          .filter((mt) => mt.is_active)
                          .map((mt) => (
                            <SelectItem key={mt.id} value={mt.id.toString()}>
                              {mt.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={form.control}
              name="internal_notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("members.internalNotes")}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex gap-3">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? t("common.loading") : t("common.save")}
              </Button>
              {onCancel && (
                <Button type="button" variant="outline" onClick={onCancel}>
                  {t("common.cancel")}
                </Button>
              )}
            </div>
      </form>
    </Form>
  );

  // When used inline (has onCancel), render without Card wrapper
  if (onCancel) return formContent;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {member ? t("members.editMember") : t("members.createMember")}
        </CardTitle>
      </CardHeader>
      <CardContent>{formContent}</CardContent>
    </Card>
  );
}
