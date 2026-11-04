import { type FormEvent, useState } from "react";
import { CheckCircle2, Pencil, Plus, RefreshCw, Trash2, XCircle } from "lucide-react";

import { useProviderMutations, useProviders } from "../api/hooks";
import type { Provider, ProviderPayload } from "../api/types";
import { ConfirmDialog, Modal, useToast } from "../components/overlays";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  IconButton,
  Input,
  Select,
  Skeleton,
} from "../components/ui";
import { useI18n } from "../i18n";
import { errorCode, formatCost } from "../lib/utils";

const emptyProvider: ProviderPayload = {
  name: "",
  kind: "ollama",
  base_url: "http://127.0.0.1:11434",
  api_key: "",
  default_model: "llama3.2:3b",
  input_price_per_1m: 0,
  output_price_per_1m: 0,
  is_active: true,
};

export function ProvidersPage() {
  const { t, formatDate, formatNumber } = useI18n();
  const toast = useToast();
  const providers = useProviders();
  const mutations = useProviderMutations();

  const [editing, setEditing] = useState<Provider | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ProviderPayload>(emptyProvider);
  const [pendingDelete, setPendingDelete] = useState<Provider | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyProvider);
    setFormOpen(true);
  };

  const openEdit = (provider: Provider) => {
    setEditing(provider);
    setForm({
      name: provider.name,
      kind: provider.kind,
      base_url: provider.base_url,
      api_key: "",
      default_model: provider.default_model,
      input_price_per_1m: provider.input_price_per_1m,
      output_price_per_1m: provider.output_price_per_1m,
      is_active: provider.is_active,
    });
    setFormOpen(true);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (editing) {
      mutations.update.mutate(
        { id: editing.id, payload: form },
        {
          onSuccess: () => {
            toast.push(t("providers.updated"), "success");
            setFormOpen(false);
          },
          onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
        },
      );
    } else {
      mutations.create.mutate(form, {
        onSuccess: () => {
          toast.push(t("providers.created"), "success");
          setFormOpen(false);
        },
        onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
      });
    }
  };

  const test = (provider: Provider) => {
    setTestingId(provider.id);
    mutations.test.mutate(provider.id, {
      onSuccess: (result) => {
        toast.push(
          result.status === "ok"
            ? t("providers.testOk", { count: result.models.length })
            : `${t("providers.testError")}: ${result.message}`,
          result.status === "ok" ? "success" : "error",
        );
      },
      onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
      onSettled: () => setTestingId(null),
    });
  };

  const statusBadge = (provider: Provider) => {
    if (provider.last_check_status === "ok") {
      return (
        <Badge tone="success">
          <CheckCircle2 size={11} />
          {t("providers.statusOk")}
        </Badge>
      );
    }
    if (provider.last_check_status === "error") {
      return (
        <Badge tone="danger">
          <XCircle size={11} />
          {t("providers.statusError")}
        </Badge>
      );
    }
    return <Badge>{t("providers.statusUnknown")}</Badge>;
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-ink">{t("providers.title")}</h1>
          <p className="mt-0.5 text-[13px] text-muted">{t("providers.subtitle")}</p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={15} />
          {t("providers.add")}
        </Button>
      </div>

      {providers.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <Skeleton key={index} className="h-32" />
          ))}
        </div>
      ) : providers.data && providers.data.items.length > 0 ? (
        <div className="grid gap-3">
          {providers.data.items.map((provider) => (
            <Card key={provider.id} className="space-y-3">
              <div className="flex flex-wrap items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-[14px] font-semibold text-ink">{provider.name}</p>
                    <Badge tone={provider.kind === "ollama" ? "violet" : "accent"}>
                      {provider.kind === "ollama" ? t("providers.kindOllama") : t("providers.kindOpenai")}
                    </Badge>
                    {statusBadge(provider)}
                    {!provider.is_active ? <Badge>{t("providers.inactive")}</Badge> : null}
                  </div>
                  <p className="mt-1 break-all font-mono text-[11px] text-muted">{provider.base_url}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={testingId === provider.id}
                    onClick={() => test(provider)}
                  >
                    {t("providers.check")}
                  </Button>
                  <IconButton
                    label={t("providers.refreshModels")}
                    onClick={() =>
                      mutations.refreshModels.mutate(provider.id, {
                        onSuccess: () => toast.push(t("providers.modelsUpdated"), "success"),
                        onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
                      })
                    }
                  >
                    <RefreshCw size={13} />
                  </IconButton>
                  <IconButton label={t("common.edit")} onClick={() => openEdit(provider)}>
                    <Pencil size={13} />
                  </IconButton>
                  <IconButton label={t("common.delete")} tone="danger" onClick={() => setPendingDelete(provider)}>
                    <Trash2 size={13} />
                  </IconButton>
                </div>
              </div>

              <div className="grid gap-x-6 gap-y-1 text-[12px] sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted">{t("providers.defaultModel")}</p>
                  <p className="truncate text-ink">{provider.default_model || t("common.none")}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted">{t("providers.pricePair")}</p>
                  <p className="tabular truncate text-ink">
                    {provider.input_price_per_1m === 0 && provider.output_price_per_1m === 0
                      ? t("providers.priceFree")
                      : `${formatCost(provider.input_price_per_1m)} / ${formatCost(provider.output_price_per_1m)}`}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted">{t("providers.apiKey")}</p>
                  <p className="truncate text-ink">
                    {provider.has_api_key ? provider.api_key_hint : t("common.none")}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-muted">{t("providers.lastChecked")}</p>
                  <p className="truncate text-ink">
                    {provider.last_checked_at ? formatDate(provider.last_checked_at, true) : t("providers.never")}
                  </p>
                </div>
              </div>

              <div className="space-y-1.5">
                <p className="text-[10px] uppercase tracking-wide text-muted">
                  {t("providers.models")} · {formatNumber(provider.models_cache.length)}
                </p>
                {provider.models_cache.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {provider.models_cache.slice(0, 8).map((model) => (
                      <Badge key={model} tone="neutral">
                        {model}
                      </Badge>
                    ))}
                    {provider.models_cache.length > 8 ? (
                      <Badge>+{provider.models_cache.length - 8}</Badge>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-[11px] text-muted">{t("providers.noModels")}</p>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          title={t("providers.emptyTitle")}
          description={t("providers.emptyBody")}
          action={
            <Button onClick={openCreate}>
              <Plus size={15} />
              {t("providers.add")}
            </Button>
          }
        />
      )}

      <Modal
        open={formOpen}
        title={editing ? t("providers.editTitle") : t("providers.createTitle")}
        onClose={() => setFormOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              form="provider-form"
              loading={mutations.create.isPending || mutations.update.isPending}
            >
              {mutations.create.isPending || mutations.update.isPending
                ? t("common.saving")
                : t("common.save")}
            </Button>
          </>
        }
      >
        <form id="provider-form" onSubmit={submit} className="space-y-3">
          <Field label={t("providers.name")}>
            <Input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder={t("providers.namePlaceholder")}
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("providers.kind")}>
              <Select
                value={form.kind}
                onChange={(event) =>
                  setForm({
                    ...form,
                    kind: event.target.value as ProviderPayload["kind"],
                    base_url:
                      event.target.value === "ollama" ? "http://127.0.0.1:11434" : "https://api.openai.com/v1",
                  })
                }
              >
                <option value="ollama">{t("providers.kindOllama")}</option>
                <option value="openai_compatible">{t("providers.kindOpenai")}</option>
              </Select>
            </Field>
            <Field label={t("providers.defaultModel")}>
              <Input
                value={form.default_model}
                onChange={(event) => setForm({ ...form, default_model: event.target.value })}
                placeholder="llama3.2:3b"
              />
            </Field>
          </div>
          <Field label={t("providers.baseUrl")} hint={t("providers.baseUrlHint")}>
            <Input
              required
              value={form.base_url}
              onChange={(event) => setForm({ ...form, base_url: event.target.value })}
              className="font-mono text-[12px]"
            />
          </Field>
          <Field
            label={t("providers.apiKey")}
            hint={editing?.has_api_key ? t("providers.apiKeyStored", { hint: editing.api_key_hint ?? "" }) : t("providers.apiKeyKeep")}
          >
            <Input
              type="password"
              value={form.api_key ?? ""}
              onChange={(event) => setForm({ ...form, api_key: event.target.value })}
              placeholder="sk-…"
              autoComplete="off"
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("providers.inputPrice")}>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={form.input_price_per_1m}
                onChange={(event) => setForm({ ...form, input_price_per_1m: Number(event.target.value) })}
              />
            </Field>
            <Field label={t("providers.outputPrice")}>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={form.output_price_per_1m}
                onChange={(event) => setForm({ ...form, output_price_per_1m: Number(event.target.value) })}
              />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-[13px] text-ink">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            {t("providers.active")}
          </label>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={t("providers.deleteTitle")}
        description={t("providers.deleteBody", { name: pendingDelete?.name ?? "" })}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        pending={mutations.remove.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return;
          mutations.remove.mutate(pendingDelete.id, {
            onSuccess: () => {
              toast.push(t("providers.deleted"), "success");
              setPendingDelete(null);
            },
            onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
          });
        }}
      />
    </div>
  );
}
