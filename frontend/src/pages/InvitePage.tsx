import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { request } from "../api/client";
import { Button, Field, Input } from "../components/ui";
import { AuthLayout } from "./LoginPage";

export function InvitePage() {
  const [params] = useSearchParams();
  const [token] = useState(params.get("invite_token") ?? "");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const accept = useMutation({
    mutationFn: () => request<{ status: string; email: string }>("/team/invitations/accept", { method: "POST", body: { token, full_name: name, password } }),
  });
  const submit = (event: FormEvent) => { event.preventDefault(); accept.mutate(); };
  return <AuthLayout><h1 className="text-base font-semibold text-ink">Приглашение в AgentHub</h1><p className="mt-1 text-[13px] leading-relaxed text-muted">Создайте пароль, чтобы присоединиться к рабочему пространству.</p><form className="mt-4 space-y-3" onSubmit={submit}><Field label="Имя"><Input required value={name} onChange={event => setName(event.target.value)} placeholder="Ваше имя" /></Field><Field label="Новый пароль"><Input type="password" minLength={8} required value={password} onChange={event => setPassword(event.target.value)} placeholder="Минимум 8 символов" /></Field>{accept.isError ? <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[12px] text-danger">Ссылка недействительна или уже использована.</p> : null}{accept.isSuccess ? <p className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-[12px] text-success">Аккаунт создан. Теперь можно войти в AgentHub.</p> : null}<Button className="w-full" disabled={!token} loading={accept.isPending}>Присоединиться</Button></form></AuthLayout>;
}
