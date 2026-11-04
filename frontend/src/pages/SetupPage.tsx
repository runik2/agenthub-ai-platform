import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSetupAdmin } from "../api/hooks";
import { Button, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { errorCode } from "../lib/utils";
import { AuthLayout } from "./LoginPage";

export function SetupPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const setup = useSetupAdmin();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && password !== confirm;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    setup.mutate(
      { email, password, full_name: fullName },
      { onSuccess: () => navigate("/", { replace: true }) },
    );
  };

  return (
    <AuthLayout>
      <h1 className="text-base font-semibold text-ink">{t("setup.title")}</h1>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">{t("setup.subtitle")}</p>

      <form className="mt-4 space-y-3" onSubmit={submit}>
        <Field label={t("setup.name")}>
          <Input
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder={t("setup.namePlaceholder")}
            autoComplete="name"
          />
        </Field>
        <Field label={t("setup.email")}>
          <Input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="admin@agenthub.local"
            autoComplete="username"
          />
        </Field>
        <Field label={t("setup.password")} hint={t("setup.passwordHint")}>
          <Input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
          />
        </Field>
        <Field label={t("setup.confirm")} error={mismatch ? t("setup.mismatch") : undefined}>
          <Input
            type="password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
          />
        </Field>

        {setup.error ? (
          <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[12px] text-danger">
            {t(`errors.${errorCode(setup.error)}`)}
          </p>
        ) : null}

        <Button type="submit" className="w-full" loading={setup.isPending} disabled={mismatch}>
          {setup.isPending ? t("setup.submitting") : t("setup.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}
