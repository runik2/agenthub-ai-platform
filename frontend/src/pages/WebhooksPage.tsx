import { useState } from "react";
import {
  CheckCircle2,
  Copy,
  Link2,
  Plus,
  RadioTower,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { request } from "../api/client";
import { Badge, Button, Card, Field, Input, Select, Textarea } from "../components/ui";

type Workflow = { id: string; name: string };
type Endpoint = {
  id: string;
  name: string;
  slug: string;
  workflow_id: string;
  enabled: boolean;
  allowed_ips: string[];
  last_received_at: string | null;
};
type Delivery = {
  id: string;
  task_id: string | null;
  status: string;
  signature_valid: boolean;
  payload: Record<string, unknown>;
  error: string | null;
  created_at: string;
};

export function WebhooksPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [allowedIps, setAllowedIps] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [testPayload, setTestPayload] = useState('{"event":"test"}');
  const [testMessage, setTestMessage] = useState("");
  const workflows = useQuery({
    queryKey: ["workflows"],
    queryFn: () => request<Workflow[]>("/workflows"),
  });
  const endpoints = useQuery({
    queryKey: ["webhook-endpoints"],
    queryFn: () => request<Endpoint[]>("/webhooks/endpoints"),
  });
  const deliveries = useQuery({
    queryKey: ["webhook-deliveries", selectedId],
    queryFn: () =>
      request<Delivery[]>(`/webhooks/endpoints/${selectedId}/deliveries`),
    enabled: Boolean(selectedId),
  });
  const create = useMutation({
    mutationFn: () =>
      request<Endpoint & { secret: string }>("/webhooks/endpoints", {
        method: "POST",
        body: {
          name,
          slug,
          workflow_id: workflowId,
          allowed_ips: allowedIps
            .split(/[\s,]+/)
            .map((value) => value.trim())
            .filter(Boolean),
        },
      }),
    onSuccess: (data) => {
      setSecret(data.secret);
      setName("");
      setSlug("");
      setAllowedIps("");
      qc.invalidateQueries({ queryKey: ["webhook-endpoints"] });
    },
  });
  const retry = useMutation({
    mutationFn: ({
      endpointId,
      deliveryId,
    }: {
      endpointId: string;
      deliveryId: string;
    }) =>
      request<Delivery>(
        `/webhooks/endpoints/${endpointId}/deliveries/${deliveryId}/retry`,
        { method: "POST" },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["webhook-deliveries", selectedId] }),
  });
  const test = useMutation({
    mutationFn: (endpointId: string) => {
      const parsed = JSON.parse(testPayload) as Record<string, unknown>;
      return request<{ status: string; task_id: string }>(
        `/webhooks/endpoints/${endpointId}/test`,
        { method: "POST", body: { payload: parsed } },
      );
    },
    onSuccess: (data) => {
      setTestMessage(`Тест принят: ${data.status}`);
      qc.invalidateQueries({ queryKey: ["webhook-deliveries", selectedId] });
    },
    onError: (error) =>
      setTestMessage(error instanceof Error ? error.message : "Не удалось отправить тест"),
  });
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <section className="relative overflow-hidden rounded-2xl border border-accent/20 bg-gradient-to-br from-accent/[.13] via-card to-violet/[.08] p-6">
        <div className="absolute -right-12 -top-16 h-52 w-52 rounded-full bg-accent/20 blur-3xl" />
        <div className="relative">
          <p className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[.16em] text-accent">
            <RadioTower size={14} /> Event gateway
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">
            Входящие Webhooks
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Принимайте события от CRM, магазина или Telegram и запускайте
            workflow по подписанной HMAC-команде.
          </p>
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card className="h-fit space-y-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
              Новый endpoint
            </p>
            <h2 className="mt-1 font-semibold text-ink">Событие → workflow</h2>
          </div>
          <Field label="Название">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Новый заказ"
            />
          </Field>
          <Field label="Slug">
            <Input
              value={slug}
              onChange={(e) =>
                setSlug(
                  e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
                )
              }
              placeholder="new-order"
            />
          </Field>
          <Field label="Workflow">
            <Select
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
            >
              <option value="">Выберите workflow</option>
              {workflows.data?.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Разрешённые IP / CIDR"
            hint="Необязательно. Например: 203.0.113.10, 10.20.0.0/16"
          >
            <Input
              value={allowedIps}
              onChange={(e) => setAllowedIps(e.target.value)}
              placeholder="Оставьте пустым для любого источника"
            />
          </Field>
          <Button
            className="w-full"
            disabled={!name || !slug || !workflowId}
            loading={create.isPending}
            onClick={() => create.mutate()}
          >
            <Plus size={15} /> Создать endpoint
          </Button>
          {secret ? (
            <div className="rounded-xl border border-warning/30 bg-warning/10 p-3">
              <p className="text-xs font-semibold text-warning">
                Сохраните секрет — он показывается один раз
              </p>
              <code className="mt-2 block break-all text-[11px] text-ink">
                {secret}
              </code>
              <Button
                size="sm"
                variant="secondary"
                className="mt-2"
                onClick={() => navigator.clipboard.writeText(secret)}
              >
                <Copy size={12} /> Скопировать
              </Button>
            </div>
          ) : null}
        </Card>
        <Card>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted">
              Gateway endpoints
            </p>
            <h2 className="mt-1 font-semibold text-ink">Активные webhook-и</h2>
          </div>
          <div className="mt-5 space-y-2">
            {endpoints.data?.map((endpoint) => (
              <article
                key={endpoint.id}
                className="rounded-xl border border-line bg-card/50 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Link2 size={15} className="text-accent" />
                  <span className="flex-1 font-semibold text-ink">
                    {endpoint.name}
                  </span>
                  <Badge tone={endpoint.enabled ? "success" : "neutral"}>
                    {endpoint.enabled ? "активен" : "выключен"}
                  </Badge>
                  {endpoint.allowed_ips?.length ? (
                    <Badge tone="violet">IP allowlist · {endpoint.allowed_ips.length}</Badge>
                  ) : null}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      setSelectedId(
                        selectedId === endpoint.id ? null : endpoint.id,
                      )
                    }
                  >
                    История
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setSelectedId(endpoint.id)}>
                    Тест
                  </Button>
                </div>
                <code className="mt-3 block rounded-lg bg-canvas p-2 text-xs text-accent">
                  POST /api/v1/webhooks/incoming/{endpoint.slug}
                </code>
                <p className="mt-2 text-xs text-muted">
                  Подпись:{" "}
                  <code>X-AgentHub-Signature: sha256=&lt;hmac&gt;</code>
                </p>
                {selectedId === endpoint.id ? (
                  <div className="mt-4 border-t border-line pt-3">
                    <div className="mb-4 rounded-xl border border-accent/20 bg-accent/[.04] p-3">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
                        Test payload
                      </p>
                      <Textarea
                        value={testPayload}
                        onChange={(event) => setTestPayload(event.target.value)}
                        className="mt-2 min-h-20 font-mono text-xs"
                        aria-label="JSON test payload"
                      />
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => test.mutate(endpoint.id)}
                          loading={test.isPending}
                        >
                          Отправить тест
                        </Button>
                        <span className="text-[11px] text-muted">
                          Тест проходит обычный task/approval flow.
                        </span>
                      </div>
                      {testMessage ? <p className="mt-2 text-xs text-accent">{testMessage}</p> : null}
                    </div>
                    <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">
                      Последние доставки
                    </p>
                    {deliveries.data?.map((delivery) => (
                      <div
                        key={delivery.id}
                        className="mb-2 rounded-lg border border-line bg-canvas/60 p-3"
                      >
                        <div className="flex items-center gap-2 text-xs">
                          <span className="flex-1 font-semibold text-ink">
                            {delivery.status}
                          </span>
                          {delivery.signature_valid ? (
                            <CheckCircle2 className="text-success" size={14} />
                          ) : (
                            <XCircle className="text-danger" size={14} />
                          )}{" "}
                          {delivery.status === "failed" ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() =>
                                retry.mutate({
                                  endpointId: endpoint.id,
                                  deliveryId: delivery.id,
                                })
                              }
                              loading={retry.isPending}
                            >
                              <RefreshCw size={12} /> Повторить
                            </Button>
                          ) : null}
                        </div>
                        {delivery.error ? (
                          <p className="mt-1 text-[11px] text-danger">
                            {delivery.error}
                          </p>
                        ) : null}
                        <pre className="mt-2 max-h-20 overflow-auto text-[10px] text-muted">
                          {JSON.stringify(delivery.payload, null, 2)}
                        </pre>
                      </div>
                    ))}
                    {!deliveries.data?.length ? (
                      <p className="text-xs text-muted">Доставок пока нет.</p>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ))}
            {!endpoints.data?.length ? (
              <p className="py-16 text-center text-sm text-muted">
                Создайте первый webhook endpoint слева.
              </p>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
