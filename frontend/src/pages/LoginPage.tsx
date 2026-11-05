import { type FormEvent, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { useLogin, useSetupStatus } from "../api/hooks";
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

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate(
      { email, password, ...(otpCode ? { otp_code: otpCode } : {}) },
      { onSuccess: () => navigate("/", { replace: true }) },
    );
  };

  return (
    <AuthLayout>
      <h1 className="text-base font-semibold text-ink">{t("login.title")}</h1>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">{t("login.subtitle")}</p>

      <form className="mt-4 space-y-3" onSubmit={submit}>
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

        {login.error ? (
          <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[12px] text-danger">
            {t(`errors.${errorCode(login.error)}`)}
          </p>
        ) : null}

        <Button type="submit" className="w-full" loading={login.isPending}>
          {login.isPending ? t("login.submitting") : t("login.submit")}
          {!login.isPending ? <ArrowRight size={15} /> : null}
        </Button>
      </form>

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
