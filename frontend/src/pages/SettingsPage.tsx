import { AlertTriangle, CheckCircle2, KeyRound, LockKeyhole, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { request } from "../api/client";
import { useAppSettings, useMe } from "../api/hooks";
import { Badge, Button, Card, Field, Input, Skeleton } from "../components/ui";
import { useI18n } from "../i18n";

const featureKeys: { key: string; labelKey: string }[] = [
  { key: "chat", labelKey: "chat.title" },
  { key: "agents", labelKey: "nav.agents" },
  { key: "providers", labelKey: "nav.providers" },
  { key: "queue", labelKey: "settings.queue" },
  { key: "workflows", labelKey: "nav.workflows" },
  { key: "tools", labelKey: "nav.tools" },
  { key: "schedules", labelKey: "nav.schedules" },
  { key: "analytics_full", labelKey: "nav.analytics" },
];

export function SettingsPage() {
  const { t } = useI18n();
  const settings = useAppSettings();
  const me = useMe();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [secret, setSecret] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const password = useMutation({
    mutationFn: () => request<{ status: string }>("/auth/password", { method: "POST", body: { current_password: currentPassword, new_password: newPassword } }),
    onSuccess: () => { setCurrentPassword(""); setNewPassword(""); setNotice("Пароль изменён, старые сессии отозваны."); },
  });
  const setup2fa = useMutation({ mutationFn: () => request<{ secret: string }>("/auth/2fa/setup", { method: "POST" }), onSuccess: data => setSecret(data.secret) });
  const enable2fa = useMutation({ mutationFn: () => request<{ status: string }>("/auth/2fa/enable", { method: "POST", body: { code: otp } }), onSuccess: () => { setOtp(""); setSecret(null); me.refetch(); setNotice("2FA включена."); } });
  const disable2fa = useMutation({ mutationFn: () => request<{ status: string }>("/auth/2fa/disable", { method: "POST", body: { code: otp } }), onSuccess: () => { setOtp(""); me.refetch(); setNotice("2FA отключена."); } });
  const data = settings.data;

  if (settings.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-3">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">{t("settings.title")}</h1>
        <p className="mt-0.5 text-[13px] text-muted">{t("settings.subtitle")}</p>
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-ink">{t("settings.mode")}</h2>
          <Badge tone={data?.app_mode === "docker" ? "violet" : "accent"}>
            {data?.app_mode ?? "local"}
          </Badge>
        </div>
        <dl className="grid gap-3 text-[13px] sm:grid-cols-2">
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.mode")}</dt>
            <dd className="text-ink">
              {data?.app_mode === "docker" ? t("settings.modeDocker") : t("settings.modeLocal")}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.database")}</dt>
            <dd className="text-ink">{data?.database_backend}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.version")}</dt>
            <dd className="tabular text-ink">{data?.version}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.ollama")}</dt>
            <dd className="break-all font-mono text-[11px] text-ink">{data?.ollama_base_url}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.queue")}</dt>
            <dd className="text-ink">{data?.runtime.queue_backend}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wide text-muted">{t("settings.scheduler")}</dt>
            <dd className="text-ink">{data?.runtime.scheduler}</dd>
          </div>
        </dl>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-ink">{t("settings.features")}</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {featureKeys.map((feature) => {
            const enabled = Boolean(data?.features[feature.key]);
            return (
              <div
                key={feature.key}
                className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-[12.5px]"
              >
                <span className="min-w-0 truncate text-ink">{t(feature.labelKey)}</span>
                <span className={enabled ? "text-success" : "text-muted"}>
                  {enabled ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                </span>
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="space-y-2">
        <div className="flex items-center gap-2">
          <AlertTriangle size={15} className="text-warning" />
          <h2 className="text-sm font-semibold text-ink">{t("settings.modeDocker")}</h2>
          <Badge tone="warning">{t("settings.notVerified")}</Badge>
        </div>
        <p className="text-[12.5px] leading-relaxed text-muted">{t("settings.dockerNote")}</p>
      </Card>

      <Card className="space-y-5 border-accent/20">
        <div className="flex items-start gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-accent/10 text-accent"><ShieldCheck size={17} /></span><div><h2 className="font-semibold text-ink">Безопасность аккаунта</h2><p className="mt-1 text-xs text-muted">Сессии, пароль и двухфакторная защита управляются здесь.</p></div></div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3 rounded-xl border border-line bg-card/50 p-4"><div className="flex items-center gap-2"><KeyRound size={15} className="text-accent" /><h3 className="font-medium text-ink">Сменить пароль</h3></div><Field label="Текущий пароль"><Input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></Field><Field label="Новый пароль"><Input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Минимум 8 символов" /></Field><Button size="sm" disabled={newPassword.length < 8 || !currentPassword} loading={password.isPending} onClick={() => password.mutate()}>Обновить пароль</Button></div>
          <div className="space-y-3 rounded-xl border border-line bg-card/50 p-4"><div className="flex items-center gap-2"><LockKeyhole size={15} className="text-violet" /><h3 className="font-medium text-ink">Authenticator 2FA</h3><Badge tone={me.data?.two_factor_enabled ? "success" : "neutral"}>{me.data?.two_factor_enabled ? "включена" : "выключена"}</Badge></div>{!me.data?.two_factor_enabled ? <><p className="text-xs leading-relaxed text-muted">Подключите приложение-аутентификатор и подтвердите шестизначный код.</p>{secret ? <div className="rounded-lg bg-canvas p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Секрет для приложения</p><code className="mt-1 block break-all text-xs text-accent">{secret}</code></div> : null}<div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => setup2fa.mutate()} loading={setup2fa.isPending}>Получить секрет</Button><Input className="w-28" value={otp} onChange={e => setOtp(e.target.value)} placeholder="000000" maxLength={6} /></div><Button size="sm" disabled={!secret || otp.length !== 6} loading={enable2fa.isPending} onClick={() => enable2fa.mutate()}>Включить 2FA</Button></> : <><p className="text-xs leading-relaxed text-muted">Для отключения введите текущий код из authenticator-приложения.</p><div className="flex gap-2"><Input className="w-28" value={otp} onChange={e => setOtp(e.target.value)} placeholder="000000" maxLength={6} /><Button size="sm" variant="danger" disabled={otp.length !== 6} loading={disable2fa.isPending} onClick={() => disable2fa.mutate()}>Отключить</Button></div></>}</div>
        </div>{notice ? <p className="rounded-lg bg-success/10 px-3 py-2 text-xs text-success">{notice}</p> : null}
      </Card>
    </div>
  );
}
