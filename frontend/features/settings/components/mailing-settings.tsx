"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Lock, Mail, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { cn } from "@/lib/utils";
import {
  useMailingConfig,
  useTestMailingProvider,
  useUpdateMailingConfig,
} from "../hooks/use-mailing-config";
import type {
  MailingConfigUpdate,
  MailProvider,
  MailSecretStatus,
} from "../services/mailing-api";

type SecretInput = { value: string; clear: boolean };

interface ProviderForm {
  fields: Record<string, string>; // non-secret fields
  secrets: Record<string, SecretInput>; // secret fields
}

// Which fields each provider carries, which are secret, and which are required
// for the provider to be activatable.
const PROVIDER_SCHEMA = {
  resend: {
    icon: "📧",
    fields: ["from_email"] as const,
    secrets: ["api_key"] as const,
    required: ["api_key"],
  },
  gmail: {
    icon: "✉️",
    fields: ["user", "from_email"] as const,
    secrets: ["app_password"] as const,
    required: ["user", "app_password"],
  },
} as const;

type ProviderName = keyof typeof PROVIDER_SCHEMA;
const PROVIDERS: ProviderName[] = ["resend", "gmail"];

export function MailingSettings() {
  const t = useTranslations();
  const { data, isLoading } = useMailingConfig();
  const updateMutation = useUpdateMailingConfig();
  const testMutation = useTestMailingProvider();

  const [forms, setForms] = useState<Record<ProviderName, ProviderForm> | null>(null);
  const [active, setActive] = useState<MailProvider | null>(null);
  const initialForms = useRef<Record<ProviderName, ProviderForm> | null>(null);
  const initialActive = useRef<MailProvider | null>(null);

  useEffect(() => {
    if (!data) return;
    const build = (name: ProviderName): ProviderForm => {
      const schema = PROVIDER_SCHEMA[name];
      const view = data[name] as unknown as Record<string, unknown>;
      const fields: Record<string, string> = {};
      for (const f of schema.fields) fields[f] = (view[f] as string) ?? "";
      const secrets: Record<string, SecretInput> = {};
      for (const s of schema.secrets) secrets[s] = { value: "", clear: false };
      return { fields, secrets };
    };
    const next = { resend: build("resend"), gmail: build("gmail") };
    setForms(next);
    setActive(data.active_provider);
    initialForms.current = JSON.parse(JSON.stringify(next));
    initialActive.current = data.active_provider;
  }, [data]);

  if (isLoading || !forms || !data) return <FormSkeleton fields={4} />;

  const encryptionOff = !data.secrets_encryption_available;

  function update(name: ProviderName, patch: Partial<ProviderForm>) {
    setForms((prev) => (prev ? { ...prev, [name]: { ...prev[name], ...patch } } : prev));
  }

  // Fields present locally (saved value kept, or freshly typed) — the gate for
  // offering a provider as the active one. A save applies these field edits and
  // the activation in one request, so typed-but-unsaved creds can still activate.
  function isConfigurable(name: ProviderName): boolean {
    const form = forms![name];
    const view = data![name] as unknown as Record<string, MailSecretStatus | string>;
    const schema = PROVIDER_SCHEMA[name];
    const required = schema.required as readonly string[];
    for (const f of schema.fields) {
      if (required.includes(f) && !form.fields[f]) return false;
    }
    for (const s of schema.secrets) {
      if (!required.includes(s)) continue;
      const status = view[s] as MailSecretStatus;
      const typed = form.secrets[s].value.length > 0;
      const cleared = form.secrets[s].clear;
      if (cleared || (!status.configured && !typed)) return false;
    }
    return true;
  }

  function isDirty(name: ProviderName): boolean {
    const form = forms![name];
    const initial = initialForms.current![name];
    const schema = PROVIDER_SCHEMA[name];
    for (const f of schema.fields) if (form.fields[f] !== initial.fields[f]) return true;
    for (const s of schema.secrets) {
      if (form.secrets[s].value.length > 0 || form.secrets[s].clear) return true;
    }
    return false;
  }

  function buildProviderUpdate(name: ProviderName) {
    const form = forms![name];
    const initial = initialForms.current![name];
    const schema = PROVIDER_SCHEMA[name];
    const payload: Record<string, unknown> = {};
    for (const f of schema.fields) {
      if (form.fields[f] !== initial.fields[f]) payload[f] = form.fields[f];
    }
    for (const s of schema.secrets) {
      const input = form.secrets[s];
      if (input.clear) payload[s] = { clear: true };
      else if (input.value.length > 0) payload[s] = { value: input.value, secret: true };
    }
    return payload;
  }

  async function handleSave() {
    if (encryptionOff) {
      for (const name of PROVIDERS) {
        for (const s of PROVIDER_SCHEMA[name].secrets) {
          if (forms![name].secrets[s].value.length > 0) {
            toast.error(t("settings.mailing.encryptionKeyRequired"));
            return;
          }
        }
      }
    }

    const body: MailingConfigUpdate = {};
    const r = buildProviderUpdate("resend");
    const g = buildProviderUpdate("gmail");
    if (Object.keys(r).length) body.resend = r;
    if (Object.keys(g).length) body.gmail = g;
    if (active !== initialActive.current) body.active_provider = active;

    if (!Object.keys(body).length) {
      toast.info(t("settings.mailing.nothingToSave"));
      return;
    }

    try {
      await updateMutation.mutateAsync(body);
      toast.success(t("toast.success.saved"));
    } catch (err) {
      const code = (err as { detail?: { code?: string } })?.detail?.code;
      if (code === "mailing_encryption_key_missing") {
        toast.error(t("settings.mailing.encryptionKeyRequired"));
      } else if (code === "mailing_provider_not_ready") {
        toast.error(t("settings.mailing.providerNotReady"));
      } else {
        toast.error(t("toast.error.generic"));
      }
    }
  }

  async function handleTest(name: ProviderName) {
    try {
      const result = await testMutation.mutateAsync(name);
      if (result.ok) {
        toast.success(t("settings.mailing.testSent"));
      } else {
        toast.error(t("settings.mailing.testFailed", { error: result.error ?? "" }));
      }
    } catch (err) {
      const code = (err as { detail?: { code?: string } })?.detail?.code;
      if (code === "mailing_provider_not_ready") {
        toast.error(t("settings.mailing.providerNotReady"));
      } else {
        toast.error(t("toast.error.generic"));
      }
    }
  }

  function renderProvider(name: ProviderName) {
    const form = forms![name];
    const view = data![name] as unknown as {
      ready: boolean;
    } & Record<string, MailSecretStatus | string | boolean>;
    const schema = PROVIDER_SCHEMA[name];
    const dirty = isDirty(name);
    const testable = view.ready && !dirty;

    return (
      <Card key={name}>
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">{schema.icon}</span>
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                {t(`settings.mailing.providers.${name}`)}
                {active === name ? (
                  <Badge variant="default">{t("settings.mailing.active")}</Badge>
                ) : view.ready ? (
                  <Badge variant="outline">{t("settings.mailing.ready")}</Badge>
                ) : (
                  <Badge variant="outline">{t("settings.mailing.off")}</Badge>
                )}
              </CardTitle>
              <CardDescription className="text-xs">
                {t(`settings.mailing.hints.${name}`)}
              </CardDescription>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5"
            disabled={!testable || testMutation.isPending}
            title={!view.ready ? t("settings.mailing.testNeedsReady") : dirty ? t("settings.mailing.testNeedsSave") : undefined}
            onClick={() => handleTest(name)}
          >
            <Send className="h-3.5 w-3.5" />
            {t("settings.mailing.sendTest")}
          </Button>
        </CardHeader>
        <CardContent className="px-4 pb-3 pt-0 space-y-3">
          {schema.fields.map((f) => {
            const source = data!.sources[`${name}.${f}`];
            return (
              <div key={f} className="space-y-0.5">
                <label className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.mailing.fields.${f}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.mailing.fromEnv")}
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
            const status = view[s] as MailSecretStatus;
            const input = form.secrets[s];
            const source = data!.sources[`${name}.${s}`];
            const placeholder = status.configured
              ? `•••• ${status.last4 ?? ""}`
              : t("settings.mailing.notConfigured");
            return (
              <div key={s} className="space-y-0.5">
                <label className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.mailing.fields.${s}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.mailing.fromEnv")}
                    </Badge>
                  )}
                  {status.configured && (
                    <Badge variant="outline" className="text-[10px]">
                      {t("settings.mailing.stored")}
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
                  {name === "gmail" && s === "app_password"
                    ? t("settings.mailing.appPasswordHint")
                    : t("settings.mailing.secretHint")}
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
                      {input.clear ? t("settings.mailing.undoClear") : t("settings.mailing.clear")}
                    </button>
                  )}
                </p>
              </div>
            );
          })}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3 max-w-3xl">
      <div>
        <h2 className="text-base font-semibold">{t("settings.mailing.title")}</h2>
        <p className="text-xs text-muted-foreground">{t("settings.mailing.description")}</p>
      </div>

      {encryptionOff ? (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          {t("settings.mailing.encryptionKeyMissing")}
        </div>
      ) : (
        <div className="flex items-start gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{t("settings.mailing.encryptionActive")}</span>
        </div>
      )}

      {/* Active-provider selector — the mutual-exclusion control. Exactly one of
          None / Resend / Gmail is active; a provider is selectable only once its
          required fields are present (saved or freshly typed). */}
      <Card>
        <CardContent className="px-4 py-3 space-y-2">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{t("settings.mailing.activeProvider")}</span>
          </div>
          <div className="inline-flex gap-1 rounded-lg border bg-muted p-1">
            {([null, "resend", "gmail"] as (MailProvider | null)[]).map((opt) => {
              const disabled = opt !== null && !isConfigurable(opt);
              const label =
                opt === null ? t("settings.mailing.none") : t(`settings.mailing.providers.${opt}`);
              return (
                <button
                  key={String(opt)}
                  type="button"
                  disabled={disabled}
                  onClick={() => setActive(opt)}
                  className={cn(
                    "rounded-md px-3 py-1 text-sm transition-colors",
                    active === opt
                      ? "bg-background shadow-sm font-medium"
                      : "text-muted-foreground hover:text-foreground",
                    disabled && "cursor-not-allowed opacity-40 hover:text-muted-foreground",
                  )}
                  title={disabled ? t("settings.mailing.fillCredsFirst") : undefined}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <p className="text-[11px] text-muted-foreground">{t("settings.mailing.oneAtATime")}</p>
        </CardContent>
      </Card>

      {PROVIDERS.map(renderProvider)}

      <Button onClick={handleSave} disabled={updateMutation.isPending}>
        {updateMutation.isPending ? t("common.loading") : t("common.save")}
      </Button>
    </div>
  );
}