"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Check, Copy, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useSsoConfig, useUpdateSsoConfig } from "../hooks/use-sso-config";
import type {
  SsoConfigUpdate,
  SsoConfigView,
  SsoSecretStatus,
} from "../services/sso-api";

type SecretInput = { value: string; clear: boolean };

interface ProviderForm {
  enabled: boolean;
  fields: Record<string, string>; // non-secret fields
  secrets: Record<string, SecretInput>; // secret fields
}

// Which fields each provider carries, and which are secret.
const PROVIDER_SCHEMA = {
  google: {
    icon: "🔵",
    fields: ["client_id"] as const,
    secrets: ["client_secret"] as const,
    required: ["client_id", "client_secret"],
  },
  apple: {
    icon: "",
    fields: ["client_id", "team_id", "key_id"] as const,
    secrets: ["private_key"] as const,
    required: ["client_id", "team_id", "key_id", "private_key"],
  },
} as const;

type ProviderName = keyof typeof PROVIDER_SCHEMA;

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }
  return (
    <div className="space-y-0.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <div className="flex items-center gap-2">
        <Input readOnly value={value} className="h-8 font-mono text-xs" />
        <Button type="button" variant="outline" size="icon" className="h-8 w-8 shrink-0" onClick={copy}>
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </Button>
      </div>
    </div>
  );
}

export function SsoSettings() {
  const t = useTranslations();
  const { data, isLoading } = useSsoConfig();
  const updateMutation = useUpdateSsoConfig();

  const [forms, setForms] = useState<Record<ProviderName, ProviderForm> | null>(null);
  const initialRef = useRef<Record<ProviderName, ProviderForm> | null>(null);

  useEffect(() => {
    if (!data) return;
    const build = (name: ProviderName): ProviderForm => {
      const schema = PROVIDER_SCHEMA[name];
      const view = data[name] as unknown as Record<string, unknown>;
      const fields: Record<string, string> = {};
      for (const f of schema.fields) fields[f] = (view[f] as string) ?? "";
      const secrets: Record<string, SecretInput> = {};
      for (const s of schema.secrets) secrets[s] = { value: "", clear: false };
      return { enabled: view.enabled as boolean, fields, secrets };
    };
    const next = { google: build("google"), apple: build("apple") };
    setForms(next);
    initialRef.current = JSON.parse(JSON.stringify(next));
  }, [data]);

  if (isLoading || !forms || !data) return <FormSkeleton fields={4} />;

  const encryptionOff = !data.secrets_encryption_available;

  function update(name: ProviderName, patch: Partial<ProviderForm>) {
    setForms((prev) => (prev ? { ...prev, [name]: { ...prev[name], ...patch } } : prev));
  }

  function isConfigured(name: ProviderName): boolean {
    const form = forms![name];
    const view = data![name] as unknown as Record<string, SsoSecretStatus | string>;
    const schema = PROVIDER_SCHEMA[name];
    for (const f of schema.fields) if (!form.fields[f]) return false;
    for (const s of schema.secrets) {
      const status = view[s] as SsoSecretStatus;
      const typed = form.secrets[s].value.length > 0;
      const cleared = form.secrets[s].clear;
      if (cleared || (!status.configured && !typed)) return false;
    }
    return true;
  }

  function buildProviderUpdate(name: ProviderName) {
    const form = forms![name];
    const initial = initialRef.current![name];
    const schema = PROVIDER_SCHEMA[name];
    const payload: Record<string, unknown> = {};

    if (form.enabled !== initial.enabled) payload.enabled = form.enabled;

    for (const f of schema.fields) {
      if (form.fields[f] !== initial.fields[f]) payload[f] = form.fields[f];
    }
    for (const s of schema.secrets) {
      const input = form.secrets[s];
      if (input.clear) payload[s] = { clear: true };
      else if (input.value.length > 0)
        payload[s] = { value: input.value, secret: true };
    }
    return payload;
  }

  async function handleSave() {
    // Guard: refuse to submit a secret write when the server can't encrypt it.
    if (encryptionOff) {
      for (const name of ["google", "apple"] as ProviderName[]) {
        for (const s of PROVIDER_SCHEMA[name].secrets) {
          if (forms![name].secrets[s].value.length > 0) {
            toast.error(t("settings.sso.encryptionKeyRequired"));
            return;
          }
        }
      }
    }

    const body: SsoConfigUpdate = {};
    const g = buildProviderUpdate("google");
    const a = buildProviderUpdate("apple");
    if (Object.keys(g).length) body.google = g;
    if (Object.keys(a).length) body.apple = a;

    if (!Object.keys(body).length) {
      toast.info(t("settings.sso.nothingToSave"));
      return;
    }

    try {
      await updateMutation.mutateAsync(body);
      toast.success(t("toast.success.saved"));
    } catch (err) {
      const code = (err as { detail?: { code?: string } })?.detail?.code;
      if (code === "sso_encryption_key_missing") {
        toast.error(t("settings.sso.encryptionKeyRequired"));
      } else {
        toast.error(t("toast.error.generic"));
      }
    }
  }

  function renderProvider(name: ProviderName) {
    const form = forms![name];
    const view = data![name] as unknown as {
      ready: boolean;
    } & Record<string, SsoSecretStatus | string | boolean>;
    const schema = PROVIDER_SCHEMA[name];
    const configurable = isConfigured(name);

    return (
      <Card key={name}>
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">{schema.icon}</span>
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                {t(`settings.sso.providers.${name}`)}
                {view.ready ? (
                  <Badge variant="default">{t("settings.sso.live")}</Badge>
                ) : (
                  <Badge variant="outline">{t("settings.sso.off")}</Badge>
                )}
              </CardTitle>
              <CardDescription className="text-xs">
                {t("settings.sso.enableHint")}
              </CardDescription>
            </div>
          </div>
          <Switch
            checked={form.enabled}
            onCheckedChange={(v) => update(name, { enabled: v })}
            disabled={!configurable && !form.enabled}
          />
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 space-y-3">
          {schema.fields.map((f) => {
            const source = data!.sources[`${name}.${f}`];
            return (
              <div key={f} className="space-y-0.5">
                <label className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.sso.fields.${f}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.sso.fromEnv")}
                    </Badge>
                  )}
                </label>
                <Input
                  className="h-8 font-mono text-xs"
                  value={form.fields[f]}
                  onChange={(e) =>
                    update(name, { fields: { ...form.fields, [f]: e.target.value } })
                  }
                />
              </div>
            );
          })}

          {schema.secrets.map((s) => {
            const status = view[s] as SsoSecretStatus;
            const input = form.secrets[s];
            const source = data!.sources[`${name}.${s}`];
            const placeholder = status.configured
              ? `•••• ${status.last4 ?? ""}`
              : t("settings.sso.notConfigured");
            return (
              <div key={s} className="space-y-0.5">
                <label className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.sso.fields.${s}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.sso.fromEnv")}
                    </Badge>
                  )}
                  {status.configured && (
                    <Badge variant="outline" className="text-[10px]">
                      {t("settings.sso.stored")}
                    </Badge>
                  )}
                </label>
                <Input
                  type="password"
                  className="h-8 font-mono text-xs"
                  placeholder={placeholder}
                  value={input.clear ? "" : input.value}
                  disabled={input.clear}
                  onChange={(e) =>
                    update(name, {
                      secrets: { ...form.secrets, [s]: { value: e.target.value, clear: false } },
                    })
                  }
                />
                <p className="text-[11px] text-muted-foreground">
                  {t("settings.sso.secretHint")}
                  {status.configured && (
                    <button
                      type="button"
                      className="ml-2 underline hover:text-foreground"
                      onClick={() =>
                        update(name, {
                          secrets: { ...form.secrets, [s]: { value: "", clear: !input.clear } },
                        })
                      }
                    >
                      {input.clear ? t("settings.sso.undoClear") : t("settings.sso.clear")}
                    </button>
                  )}
                </p>
              </div>
            );
          })}

          <CopyRow
            label={t("settings.sso.redirectUri")}
            value={data!.redirect_uris[name] ?? ""}
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3 max-w-3xl">
      <div>
        <h2 className="text-base font-semibold">{t("settings.sso.title")}</h2>
        <p className="text-xs text-muted-foreground">{t("settings.sso.description")}</p>
      </div>

      {encryptionOff ? (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          {t("settings.sso.encryptionKeyMissing")}
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{t("settings.sso.encryptionActive")}</span>
        </div>
      )}

      <Card>
        <CardContent className="px-4 py-3">
          <CopyRow label={t("settings.sso.backendUrl")} value={data.backend_public_url} />
          <p className="mt-2 text-[11px] text-muted-foreground">
            {t("settings.sso.consoleHint")}
          </p>
        </CardContent>
      </Card>

      {(["google", "apple"] as ProviderName[]).map(renderProvider)}

      <Button onClick={handleSave} disabled={updateMutation.isPending}>
        {updateMutation.isPending ? t("common.loading") : t("common.save")}
      </Button>
    </div>
  );
}