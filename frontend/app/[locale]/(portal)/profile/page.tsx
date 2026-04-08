"use client";

import { useState, useEffect } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useMember } from "@/features/members/hooks/use-members";
import { useSettings } from "@/features/settings/hooks/use-settings";
import { usePathname, useRouter } from "@/lib/i18n/routing";
import { locales, type Locale } from "@/lib/i18n/config";
import { apiClient } from "@/lib/client-api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { GenderOption } from "@/features/settings/components/gender-options-settings";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

interface ProfileData {
  gender: string | null;
  phone: string | null;
}

function useMyProfile() {
  return useQuery({
    queryKey: ["my-profile"],
    queryFn: () => apiClient<ProfileData>("/members/me/profile"),
  });
}

function useUpdateMyProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient<ProfileData>("/members/me/profile", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-profile"] });
      qc.invalidateQueries({ queryKey: ["auth"] });
    },
  });
}

export default function ProfilePage() {
  const t = useTranslations();
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const { data: member, isLoading } = useMember(user?.member_id || 0);
  const { data: profile, isLoading: profileLoading } = useMyProfile();
  const { data: settings } = useSettings();
  const updateMutation = useUpdateMyProfile();
  const genderOptions = (settings?.features?.gender_options as GenderOption[] | undefined) || [];

  const [gender, setGender] = useState("");
  const [phone, setPhone] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (profile) {
      setGender(profile.gender || "");
      setPhone(profile.phone || "");
    }
  }, [profile]);

  if (isLoading || profileLoading || !member) {
    return <FormSkeleton fields={5} />;
  }

  const person = member.person;

  function handleLocaleChange(newLocale: string) {
    router.replace(pathname, { locale: newLocale as Locale });
  }

  function handleGenderChange(value: string) {
    setGender(value);
    setDirty(true);
  }

  function handlePhoneChange(value: string) {
    setPhone(value);
    setDirty(true);
  }

  async function handleSave() {
    try {
      await updateMutation.mutateAsync({ gender: gender || null, phone: phone || null });
      toast.success(t("toast.success.saved"));
      setDirty(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  function getGenderLabel(value: string | null | undefined): string | null | undefined {
    if (!value) return value;
    const opt = genderOptions.find((o) => o.value === value);
    if (!opt) return value;
    return opt[`label_${locale}` as keyof GenderOption] || opt.label_en;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{t("nav.profile")}</h1>
        <Badge>{t(`status.${member.status}`)}</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("profile.personalInfo")}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <dl className="grid gap-2 sm:grid-cols-2">
              <Field label={t("profile.firstName")} value={person.first_name} />
              <Field label={t("profile.lastName")} value={person.last_name} />
              <Field label={t("profile.email")} value={person.email} />
              <Field label={t("profile.dateOfBirth")} value={person.date_of_birth ? new Date(person.date_of_birth).toLocaleDateString() : null} />
              <Field label={t("profile.nationalId")} value={person.national_id} />
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-base">{t("profile.membership")}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <dl className="grid gap-2 sm:grid-cols-2">
              <Field label={t("profile.memberNumber")} value={member.member_number} />
              <Field label={t("profile.membershipType")} value={member.membership_type_name} />
              <Field label={t("profile.status")} value={t(`status.${member.status}`)} />
              <Field label={t("profile.joinedAt")} value={new Date(member.joined_at).toLocaleDateString()} />
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Editable profile fields */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("profile.editProfile")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <div className="grid gap-3 sm:grid-cols-2 max-w-lg">
            {genderOptions.length > 0 && (
              <div>
                <p className="text-xs text-muted-foreground mb-1.5">{t("members.gender")}</p>
                <Select value={gender} onValueChange={handleGenderChange}>
                  <SelectTrigger className="h-8">
                    <SelectValue placeholder="—" />
                  </SelectTrigger>
                  <SelectContent>
                    {genderOptions.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt[`label_${locale}` as keyof GenderOption] || opt.label_en}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">{t("profile.phone")}</p>
              <Input
                className="h-8"
                type="tel"
                value={phone}
                onChange={(e) => handlePhoneChange(e.target.value)}
                placeholder="+34 612 345 678"
              />
            </div>
          </div>
          {dirty && (
            <Button size="sm" className="mt-3" onClick={handleSave} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? t("common.loading") : t("common.save")}
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-base">{t("profile.preferences")}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          <div className="max-w-xs">
            <p className="text-xs text-muted-foreground mb-1.5">{t("profile.language")}</p>
            <Select value={locale} onValueChange={handleLocaleChange}>
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {locales.map((loc) => (
                  <SelectItem key={loc} value={loc}>
                    {t(`locale.${loc}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
