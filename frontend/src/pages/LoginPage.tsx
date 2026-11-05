import { type FormEvent, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useMutation } from "@tanstack/react-query";

import { useLogin, useSetupStatus } from "../api/hooks";
import { request } from "../api/client";
import { LanguageToggle } from "../components/LanguageToggle";
import { Button, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { errorCode } from "../lib/utils";
import { ThemeToggle } from "../theme";

export function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-canvas px-4 py-10">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute -right-24 bottom-1/4 h-72 w-72 rounded-full bg-violet/10 blur-3xl" />
      </div>
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <LanguageToggle />
        <ThemeToggle />
      </div>
      <div className="relative w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-violet text-base font-bold text-white shadow-card">
            A
          </span>
          <p className="text-sm font-semibold tracking-tight text-ink">{t("app.name")}</p>
          <p className="text-[12px] text-muted">{t("app.tagline")}</p>
        </div>
        <div className="surface p-5 shadow-card">{children}</div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const login = useLogin();
  const setupStatus = useSetupStatus();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get("reset_token") ?? "");
  const [resetMode, setResetMode] = useState(() => Boolean(new URLSearchParams(window.location.search).get("reset_token")));
  const [newPassword, setNewPassword] = useState("");
  const [resetNotice, setResetNotice] = useState("");
  const resetRequest = useMutation({
    mutationFn: () => request<{ status: string; dev_token?: string }>("/auth/password-reset/request", { method: "POST", body: { email } }),
    onSuccess: data => { setResetNotice(data.dev_token ? `${data.status}. Demo token: ${data.dev_token}` : data.status); if (data.dev_token) setResetToken(data.dev_token); },
  });
  const resetConfirm = useMutation({
    mutationFn: () => request<{ status: string }>("/auth/password-reset/confirm", { method: "POST", body: { token: resetToken, new_password: newPassword } }),
    onSuccess: () => { setResetNotice(t("login.resetDone")); setResetMode(false); setResetToken(""); setNewPassword(""); },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate(
      { email, password, ...(otpCode ? { otp_code: otpCode } : {}) },
      { onSuccess: () => navigate("/", { replace: true }) },
    );
  };

  return (
    <AuthLayout>
      <h1 className="text-base font-semibold text-ink">{resetMode ? t("login.resetTitle") : t("login.title")}</h1>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">{resetMode ? t("login.resetSubtitle") : t("login.subtitle")}</p>

      {resetMode ? <form className="mt-4 space-y-3" onSubmit={event => { event.preventDefault(); if (!resetToken) resetRequest.mutate(); else resetConfirm.mutate(); }}>
        <Field label={t("login.email")}><Input type="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="admin@agenthub.local" /></Field>
        {resetToken ? <><Field label={t("login.resetToken")}><Input required value={resetToken} onChange={event => setResetToken(event.target.value)} /></Field><Field label={t("login.newPassword")}><Input type="password" minLength={8} required value={newPassword} onChange={event => setNewPassword(event.target.value)} /></Field></> : null}
        {resetNotice ? <p className="break-all rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-[12px] text-success">{resetNotice}</p> : null}
        <Button type="submit" className="w-full" loading={resetRequest.isPending || resetConfirm.isPending}>{resetToken ? t("login.resetConfirm") : t("login.resetSend")}</Button>
        <button type="button" className="w-full text-center text-[12px] text-accent hover:underline" onClick={() => { setResetMode(false); setResetNotice(""); }}>{t("login.backToLogin")}</button>
      </form> : <form className="mt-4 space-y-3" onSubmit={submit}>
        <Field label={t("login.email")}>
          <Input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@agenthub.local"
          />
        </Field>

        {errorCode(login.error) === "TWO_FACTOR_REQUIRED" || otpCode ? (
          <Field label={t("login.otp")}>
            <Input
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              required={errorCode(login.error) === "TWO_FACTOR_REQUIRED"}
              value={otpCode}
              onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, ""))}
              placeholder="123456"
            />
          </Field>
        ) : null}
        <Field label={t("login.password")}>
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
          />
        </Field>

        <button type="button" className="text-[12px] text-accent hover:underline" onClick={() => setResetMode(true)}>{t("login.resetLink")}</button>

        {login.error ? (
          <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[12px] text-danger">
            {t(`errors.${errorCode(login.error)}`)}
          </p>
        ) : null}

        <Button type="submit" className="w-full" loading={login.isPending}>
          {login.isPending ? t("login.submitting") : t("login.submit")}
          {!login.isPending ? <ArrowRight size={15} /> : null}
        </Button>
      </form>}

      <p className="mt-3 text-[11px] leading-relaxed text-muted">{t("login.demoHint")}</p>

      {setupStatus.data?.needs_setup ? (
        <p className="mt-3 border-t border-line pt-3 text-[12px] text-muted">
          <Link to="/setup" className="font-medium text-accent hover:underline">
            {t("setup.title")}
          </Link>
        </p>
      ) : null}
    </AuthLayout>
  );
}
