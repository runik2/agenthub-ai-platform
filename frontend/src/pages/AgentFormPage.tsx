import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Save } from "lucide-react";

import { useAgent, useAgentMutations, useProviders } from "../api/hooks";
import type { AgentPayload, AgentStatus } from "../api/types";
import { useToast } from "../components/overlays";
import { Badge, Button, Card, Field, Input, Select, Skeleton, Textarea } from "../components/ui";
import { useI18n } from "../i18n";
import { cn, errorCode } from "../lib/utils";

const COLORS = ["#3B82F6", "#8B5CF6", "#22C55E", "#F59E0B", "#EF4444", "#06B6D4", "#EC4899", "#64748B"];

const emptyAgent: AgentPayload = {
  name: "",
  description: "",
  system_prompt: "",
  greeting: "",
  provider_id: null,
  model_name: "",
  temperature: 0.7,
  max_tokens: 1024,
  status: "draft",
  avatar_color: "#3B82F6",
  tags: [],
};

export function AgentFormPage({ mode }: { mode: "create" | "edit" }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const toast = useToast();
  const params = useParams();
  const agentQuery = useAgent(mode === "edit" ? params.id : undefined);
  const providers = useProviders();
  const mutations = useAgentMutations();

  const [form, setForm] = useState<AgentPayload>(emptyAgent);
  const [tagsText, setTagsText] = useState("");
  const [errors, setErrors] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (mode === "edit" && agentQuery.data) {
      const agent = agentQuery.data;
      setForm({
        name: agent.name,
        description: agent.description,
        system_prompt: agent.system_prompt,
        greeting: agent.greeting,
        provider_id: agent.provider_id,
        model_name: agent.model_name,
        temperature: agent.temperature,
        max_tokens: agent.max_tokens,
        status: agent.status,
        avatar_color: agent.avatar_color,
        tags: agent.tags,
      });
      setTagsText(agent.tags.join(", "));
    }
  }, [mode, agentQuery.data]);

  const models = useMemo(() => {
    const provider = providers.data?.items.find((item) => item.id === form.provider_id);
    return provider?.models_cache ?? [];
  }, [providers.data, form.provider_id]);

  const update = <K extends keyof AgentPayload>(key: K, value: AgentPayload[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = {
      name: !form.name.trim(),
      system_prompt: !form.system_prompt.trim(),
    };
    setErrors(nextErrors);
    if (nextErrors.name || nextErrors.system_prompt) {
      toast.push(t("agentForm.required"), "error");
      return;
    }
    const payload: AgentPayload = {
      ...form,
      tags: tagsText
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    };

    if (mode === "create") {
      mutations.create.mutate(payload, {
        onSuccess: (agent) => {
          toast.push(t("agents.created"), "success");
          navigate(`/agents/${agent.id}/chat`);
        },
        onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
      });
    } else if (params.id) {
      mutations.update.mutate(
        { id: params.id, payload },
        {
          onSuccess: () => {
            toast.push(t("agents.updated"), "success");
            navigate("/agents");
          },
          onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
        },
      );
    }
  };

  const saving = mutations.create.isPending || mutations.update.isPending;

  if (mode === "edit" && agentQuery.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-3">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-[520px]" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => navigate("/agents")}>
          <ArrowLeft size={14} />
          {t("chat.backToAgents")}
        </Button>
      </div>

      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          {mode === "create" ? t("agentForm.createTitle") : t("agentForm.editTitle")}
        </h1>
        <p className="mt-0.5 text-[13px] text-muted">{t("agentForm.subtitle")}</p>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <Card className="grid gap-4 sm:grid-cols-2">
          <Field label={t("agentForm.name")} error={errors.name ? t("agentForm.required") : undefined}>
            <Input
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              placeholder={t("agentForm.namePlaceholder")}
              required
            />
          </Field>
          <Field label={t("agentForm.status")}>
            <Select
              value={form.status}
              onChange={(event) => update("status", event.target.value as AgentStatus)}
            >
              <option value="draft">{t("agents.statusDraft")}</option>
              <option value="active">{t("agents.statusActive")}</option>
              <option value="archived">{t("agents.statusArchived")}</option>
            </Select>
          </Field>
          <Field label={t("agentForm.description")} className="sm:col-span-2">
            <Input
              value={form.description}
              onChange={(event) => update("description", event.target.value)}
              placeholder={t("agentForm.descriptionPlaceholder")}
            />
          </Field>
          <Field
            label={t("agentForm.systemPrompt")}
            hint={t("agentForm.systemPromptHint")}
            error={errors.system_prompt ? t("agentForm.required") : undefined}
            className="sm:col-span-2"
          >
            <Textarea
              rows={8}
              value={form.system_prompt}
              onChange={(event) => update("system_prompt", event.target.value)}
              className="font-mono text-[12px]"
              required
            />
          </Field>
          <Field label={t("agentForm.greeting")} className="sm:col-span-2">
            <Textarea
              rows={2}
              value={form.greeting}
              onChange={(event) => update("greeting", event.target.value)}
              placeholder={t("agentForm.greetingPlaceholder")}
            />
          </Field>
        </Card>

        <Card className="grid gap-4 sm:grid-cols-2">
          <Field label={t("agentForm.provider")}>
            <Select
              value={form.provider_id ?? ""}
              onChange={(event) => update("provider_id", event.target.value || null)}
            >
              <option value="">{t("agentForm.providerPlaceholder")}</option>
              {(providers.data?.items ?? []).map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("agentForm.model")} hint={t("agentForm.modelHint")}>
            <Input
              list="agent-models"
              value={form.model_name}
              onChange={(event) => update("model_name", event.target.value)}
              placeholder={t("agentForm.modelPlaceholder")}
            />
            <datalist id="agent-models">
              {models.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
          </Field>
          <Field label={`${t("agentForm.temperature")}: ${form.temperature.toFixed(1)}`} hint={t("agentForm.temperatureHint")}>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={form.temperature}
              onChange={(event) => update("temperature", Number(event.target.value))}
              className="h-10 w-full accent-[var(--accent)]"
            />
          </Field>
          <Field label={t("agentForm.maxTokens")}>
            <Input
              type="number"
              min={16}
              max={32000}
              value={form.max_tokens}
              onChange={(event) => update("max_tokens", Number(event.target.value))}
            />
          </Field>
          <Field label={t("agentForm.color")} className="sm:col-span-2">
            <div className="flex flex-wrap gap-2">
              {COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  aria-label={color}
                  onClick={() => update("avatar_color", color)}
                  className={cn(
                    "h-7 w-7 rounded-lg border-2 transition-transform",
                    form.avatar_color === color ? "border-ink scale-105" : "border-transparent",
                  )}
                  style={{ background: color }}
                />
              ))}
            </div>
          </Field>
          <Field label={t("agentForm.tags")} hint={t("agentForm.tagsHint")} className="sm:col-span-2">
            <Input
              value={tagsText}
              onChange={(event) => setTagsText(event.target.value)}
              placeholder="support, billing"
            />
          </Field>
          {form.tags.length > 0 ? (
            <div className="flex flex-wrap gap-1 sm:col-span-2">
              {form.tags.map((tag) => (
                <Badge key={tag}>{tag}</Badge>
              ))}
            </div>
          ) : null}
        </Card>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => navigate("/agents")}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" loading={saving}>
            <Save size={15} />
            {saving ? t("common.saving") : t("common.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}
