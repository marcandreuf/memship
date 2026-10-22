"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { CircleCheck, CircleHelp, Lock, Mail, Send, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { FormSkeleton } from "@/components/ui/skeletons";
import { useLocaleDate } from "@/hooks/use-locale-date";
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
import { StoredSecretField } from "./stored-secret-field";

// `replacing` is the only thing that makes `value` a write: a stored secret has
// no input until the admin asks to replace it, so nothing else can fill one.
type SecretInput = { value: string; clear: boolean; replacing: boolean };

function secretTyped(input: SecretInput): boolean {
  return input.replacing && input.value.length > 0;
}

interface ProviderForm {
  fields: Record<string, string>; // non-secret fields
  secrets: Record<string, SecretInput>; // secret fields
}

// Which fields each provider carries, which are secret, and which are required
// for the provider to be activatable. `sender` lists fields of which at least
// one must be filled: SMTP sends as the From address, or else as the user.
const PROVIDER_SCHEMA = {
  resend: {
    icon: "📧",
    fields: ["from_email"] as const,
    secrets: ["api_key"] as const,
    required: ["api_key"],
    sender: [],
  },
  smtp: {
    icon: "✉️",
    fields: ["host", "port", "tls", "user", "from_email"] as const,
    secrets: ["password"] as const,
    required: ["host"],
    sender: ["from_email", "user"],
  },
} as const;

type ProviderName = keyof typeof PROVIDER_SCHEMA;
const PROVIDERS: ProviderName[] = ["resend", "smtp"];

// Gmail is a configuration of the SMTP provider, not a provider of its own.
const GMAIL_PRESET = { host: "smtp.gmail.com", port: "587", tls: "true" };

// The form keeps every field as text; the API takes port and TLS typed.
function toPayloadValue(field: string, value: string): string | number | boolean {
  if (field === "port") return Number(value);
  if (field === "tls") return value === "true";
  return value;
}

function validPort(value: string): boolean {
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

export function MailingSettings() {
  const t = useTranslations();
  const { data, isLoading } = useMailingConfig();
  const updateMutation = useUpdateMailingConfig();
  const testMutation = useTestMailingProvider();
  const { shortDateTime } = useLocaleDate();

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
      for (const f of schema.fields) fields[f] = String(view[f] ?? "");
      const secrets: Record<string, SecretInput> = {};
      for (const s of schema.secrets) {
        const status = view[s] as MailSecretStatus;
        secrets[s] = { value: "", clear: false, replacing: !status.configured };
      }
      return { fields, secrets };
    };
    const next = { resend: build("resend"), smtp: build("smtp") };
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

  // Required fields present locally (saved value kept, or freshly typed).
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
      const typed = secretTyped(form.secrets[s]);
      const cleared = form.secrets[s].clear;
      if (cleared || (!status.configured && !typed)) return false;
    }
    const sender = schema.sender as readonly string[];
    if (sender.length && !sender.some((f) => form.fields[f])) return false;
    return true;
  }

  // Why a provider cannot be chosen as the active one, or null when it can.
  // Mirrors the backend gate: switching to a provider needs a passing send
  // through its saved credentials, so unsaved edits block it until saved and
  // tested. The provider already active stays selectable.
  function activationBlocker(name: ProviderName): string | null {
    if (!isConfigurable(name)) return t("settings.mailing.fillCredsFirst");
    if (name === initialActive.current) return null;
    if (isDirty(name)) return t("settings.mailing.activationNeedsSave");
    if (data![name].health.status !== "ok") return t("settings.mailing.activationNeedsTest");
    return null;
  }

  function isDirty(name: ProviderName): boolean {
    const form = forms![name];
    const initial = initialForms.current![name];
    const schema = PROVIDER_SCHEMA[name];
    for (const f of schema.fields) if (form.fields[f] !== initial.fields[f]) return true;
    for (const s of schema.secrets) {
      if (secretTyped(form.secrets[s]) || form.secrets[s].clear) return true;
    }
    return false;
  }

  function buildProviderUpdate(name: ProviderName) {
    const form = forms![name];
    const initial = initialForms.current![name];
    const schema = PROVIDER_SCHEMA[name];
    const payload: Record<string, unknown> = {};
    for (const f of schema.fields) {
      if (form.fields[f] !== initial.fields[f]) payload[f] = toPayloadValue(f, form.fields[f]);
    }
    for (const s of schema.secrets) {
      const input = form.secrets[s];
      if (input.clear) payload[s] = { clear: true };
      else if (secretTyped(input)) payload[s] = { value: input.value, secret: true };
    }
    return payload;
  }

  async function handleSave() {
    if (encryptionOff) {
      for (const name of PROVIDERS) {
        for (const s of PROVIDER_SCHEMA[name].secrets) {
          if (secretTyped(forms![name].secrets[s])) {
            toast.error(t("settings.mailing.encryptionKeyRequired"));
            return;
          }
        }
      }
    }

    if (!validPort(forms!.smtp.fields.port)) {
      toast.error(t("settings.mailing.invalidPort"));
      return;
    }

    const body: MailingConfigUpdate = {};
    const r = buildProviderUpdate("resend");
    const smtp = buildProviderUpdate("smtp");
    if (Object.keys(r).length) body.resend = r;
    if (Object.keys(smtp).length) body.smtp = smtp;
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
      } else if (code === "mailing_provider_not_verified") {
        toast.error(t("settings.mailing.providerNotVerified"));
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

  // Whether the saved credentials are known to work — judged by the backend
  // against the credentials in effect now, so a replaced one reads unverified.
  function renderHealth(name: ProviderName) {
    const health = data![name].health;
    const { icon: Icon, tone, message } =
      health.status === "ok"
        ? {
            icon: CircleCheck,
            tone: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
            message: t("settings.mailing.health.ok", {
              date: shortDateTime(health.last_success_at!),
            }),
          }
        : health.status === "failing"
          ? {
              icon: TriangleAlert,
              tone: "border-destructive/40 bg-destructive/10 text-destructive",
              message: t("settings.mailing.health.failing", {
                date: shortDateTime(health.last_failure_at!),
                reason: t(`settings.mailing.health.failures.${health.last_failure ?? "unknown"}`),
              }),
            }
          : {
              icon: CircleHelp,
              tone: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
              message: t("settings.mailing.health.unverified"),
            };
    return (
      <div
        data-testid={`mailing-${name}-health`}
        data-status={health.status}
        className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-xs", tone)}
      >
        <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>{message}</span>
      </div>
    );
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
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between gap-2">
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
          {view.ready && renderHealth(name)}

          {name === "smtp" && (
            <div className="space-y-0.5">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => update(name, { fields: { ...form.fields, ...GMAIL_PRESET } })}
              >
                {t("settings.mailing.gmailPreset")}
              </Button>
              <p className="text-[11px] text-muted-foreground">
                {t("settings.mailing.gmailPresetHint")}
              </p>
            </div>
          )}

          {schema.fields.map((f) => {
            const source = data!.sources[`${name}.${f}`];
            const id = `mailing-${name}-${f}`;
            const setField = (value: string) =>
              update(name, { fields: { ...form.fields, [f]: value } });
            return (
              <div key={f} className="space-y-0.5">
                <label htmlFor={id} className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.mailing.fields.${f}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.mailing.fromEnv")}
                    </Badge>
                  )}
                </label>
                {f === "tls" ? (
                  <>
                    <Switch
                      id={id}
                      checked={form.fields[f] === "true"}
                      onCheckedChange={(checked) => setField(checked ? "true" : "false")}
                    />
                    <p className="text-[11px] text-muted-foreground">
                      {t("settings.mailing.tlsHint")}
                    </p>
                  </>
                ) : (
                  <Input
                    id={id}
                    className="h-8 font-mono text-xs"
                    type={f === "port" ? "number" : "text"}
                    inputMode={f === "port" ? "numeric" : undefined}
                    min={f === "port" ? 1 : undefined}
                    max={f === "port" ? 65535 : undefined}
                    value={form.fields[f]}
                    onChange={(e) => setField(e.target.value)}
                  />
                )}
              </div>
            );
          })}

          {schema.secrets.map((s) => {
            const status = view[s] as MailSecretStatus;
            const input = form.secrets[s];
            const source = data!.sources[`${name}.${s}`];
            const setSecret = (next: Partial<SecretInput>) =>
              update(name, { secrets: { ...form.secrets, [s]: { ...input, ...next } } });
            return (
              <div key={s} className="space-y-0.5">
                <label className="text-xs font-medium flex items-center gap-2">
                  {t(`settings.mailing.fields.${s}`)}
                  {source === "env" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {t("settings.mailing.fromEnv")}
                    </Badge>
                  )}
                </label>
                <StoredSecretField
                  name={`mailing-${name}-credential`}
                  className="h-8 font-mono text-xs"
                  stored={status.configured}
                  last4={status.last4}
                  replacing={input.replacing}
                  cleared={input.clear}
                  value={input.value}
                  placeholder={t("settings.mailing.notConfigured")}
                  onReplace={() => setSecret({ replacing: true, value: "" })}
                  onCancel={() => setSecret({ replacing: false, value: "" })}
                  onChange={(value) => setSecret({ value })}
                />
                <p className="text-[11px] text-muted-foreground">
                  {t("settings.mailing.secretHint")}
                  {status.configured && (
                    <button
                      type="button"
                      className="ml-2 underline hover:text-foreground"
                      onClick={() =>
                        setSecret({ clear: !input.clear, replacing: false, value: "" })
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
          None / Resend / SMTP is active; switching to a provider needs its
          saved credentials to have passed a send (see activationBlocker). */}
      <Card>
        <CardContent className="px-4 py-3 space-y-2">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{t("settings.mailing.activeProvider")}</span>
          </div>
          <div className="inline-flex gap-1 rounded-lg border bg-muted p-1">
            {([null, ...PROVIDERS] as (MailProvider | null)[]).map((opt) => {
              const blocker = opt === null ? null : activationBlocker(opt);
              const disabled = blocker !== null;
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
                  title={blocker ?? undefined}
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