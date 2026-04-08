"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { X, Plus, GripVertical } from "lucide-react";
import { toast } from "sonner";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import { locales } from "@/lib/i18n/config";

export interface GenderOption {
  value: string;
  [key: `label_${string}`]: string;
}

function emptyOption(): GenderOption {
  const opt: GenderOption = { value: "" };
  for (const loc of locales) {
    opt[`label_${loc}`] = "";
  }
  return opt;
}

export function GenderOptionsSettings() {
  const t = useTranslations();
  const { data: settings } = useSettings();
  const updateMutation = useUpdateSettings();
  const [options, setOptions] = useState<GenderOption[]>([]);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (settings?.features?.gender_options) {
      setOptions(settings.features.gender_options as GenderOption[]);
    }
  }, [settings]);

  function updateOption(index: number, field: string, value: string) {
    const updated = [...options];
    updated[index] = { ...updated[index], [field]: value };
    setOptions(updated);
    setDirty(true);
  }

  function addOption() {
    setOptions([...options, emptyOption()]);
    setDirty(true);
  }

  function removeOption(index: number) {
    setOptions(options.filter((_, i) => i !== index));
    setDirty(true);
  }

  async function handleSave() {
    const valid = options.filter((o) => o.value.trim());
    const normalized = valid.map((o) => ({
      ...o,
      value: o.value.trim().toLowerCase().replace(/\s+/g, "_"),
    }));

    try {
      const currentFeatures = settings?.features || {};
      await updateMutation.mutateAsync({
        features: { ...currentFeatures, gender_options: normalized },
      });
      toast.success(t("toast.success.saved"));
      setDirty(false);
    } catch {
      toast.error(t("toast.error.generic"));
    }
  }

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-base">{t("settings.genderOptions")}</CardTitle>
        <CardDescription className="text-xs">{t("settings.genderOptionsDesc")}</CardDescription>
      </CardHeader>
      <CardContent className="px-4 pb-3 pt-0 space-y-3 table-compact">
        {options.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead className="w-[120px]">{t("settings.genderValue")}</TableHead>
                {locales.map((loc) => (
                  <TableHead key={loc}>{loc.toUpperCase()}</TableHead>
                ))}
                <TableHead className="w-10"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {options.map((opt, i) => (
                <TableRow key={i}>
                  <TableCell className="text-muted-foreground"><GripVertical className="h-4 w-4" /></TableCell>
                  <TableCell>
                    <Input
                      value={opt.value}
                      onChange={(e) => updateOption(i, "value", e.target.value)}
                      className="h-7 text-xs font-mono"
                      placeholder="value_key"
                    />
                  </TableCell>
                  {locales.map((loc) => (
                    <TableCell key={loc}>
                      <Input
                        value={(opt[`label_${loc}`] as string) || ""}
                        onChange={(e) => updateOption(i, `label_${loc}`, e.target.value)}
                        className="h-7 text-xs"
                      />
                    </TableCell>
                  ))}
                  <TableCell>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeOption(i)}>
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={addOption}>
            <Plus className="h-4 w-4 mr-1" /> {t("settings.addGenderOption")}
          </Button>
          {dirty && (
            <Button size="sm" onClick={handleSave} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? t("common.loading") : t("common.save")}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
