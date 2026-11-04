import { useState } from "react";
import type { ReactNode } from "react";
import { Activity, AlertTriangle, Bot, Coins, MessagesSquare } from "lucide-react";

import { useOverview } from "../api/hooks";
import { Badge, Card, EmptyState, Segmented, Skeleton, Table, Td, Th } from "../components/ui";
import { useI18n } from "../i18n";
import { cn, compactNumber, formatCost } from "../lib/utils";

function MetricCard({
  label,
  value,
  hint,
  icon,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: ReactNode;
  tone?: "accent" | "violet" | "success" | "warning";
}) {
  const tones = {
    accent: "text-accent bg-accent/10",
    violet: "text-violet bg-violet/10",
    success: "text-success bg-success/10",
    warning: "text-warning bg-warning/10",
  } as const;
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[12px] font-medium text-muted">{label}</span>
        <span className={cn("flex h-7 w-7 items-center justify-center rounded-lg", tones[tone ?? "accent"])}>
          {icon}
        </span>
      </div>
      <div className="tabular text-2xl font-semibold tracking-tight text-ink">{value}</div>
      {hint ? <p className="text-[11px] text-muted">{hint}</p> : null}
    </Card>
  );
}

function ActivityChart({
  points,
  emptyLabel,
}: {
  points: { date: string; tokens: number; messages: number }[];
  emptyLabel: string;
}) {
  const { formatNumber, formatDate } = useI18n();
  const width = 720;
  const height = 150;
  const max = Math.max(...points.map((point) => point.tokens), 1);
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const hasData = points.some((point) => point.tokens > 0);

  if (!hasData) {
    return (
      <div className="flex h-[150px] items-center justify-center rounded-lg border border-dashed border-line text-[12px] text-muted">
        {emptyLabel}
      </div>
    );
  }

  const line = points
    .map((point, index) => {
      const x = index * step;
      const y = height - (point.tokens / max) * (height - 18) - 6;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-[150px] w-full"
        role="img"
        aria-label={emptyLabel}
      >
        <defs>
          <linearGradient id="tokensFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#tokensFill)" />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
        {points.map((point, index) => {
          const x = index * step;
          const y = height - (point.tokens / max) * (height - 18) - 6;
          return (
            <circle key={point.date} cx={x} cy={y} r={2.4} fill="var(--accent)">
              <title>{`${formatDate(point.date)} · ${formatNumber(point.tokens)}`}</title>
            </circle>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-muted">
        <span>{formatDate(points[0]?.date)}</span>
        <span>{formatDate(points[points.length - 1]?.date)}</span>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { t, formatNumber } = useI18n();
  const [days, setDays] = useState(30);
  const overview = useOverview(days);
  const data = overview.data;

  const statusTone = (status: string) =>
    status === "ok" ? "success" : status === "error" ? "danger" : "neutral";

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-ink">{t("dashboard.title")}</h1>
          <p className="mt-0.5 text-[13px] text-muted">{t("dashboard.subtitle", { days })}</p>
        </div>
        <Segmented
          value={days}
          onChange={setDays}
          options={[
            { value: 7, label: t("dashboard.range7") },
            { value: 30, label: t("dashboard.range30") },
          ]}
        />
      </div>

      {overview.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-[104px]" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label={t("dashboard.agents")}
            value={formatNumber(data?.totals.agents ?? 0)}
            hint={`${t("dashboard.conversations")}: ${formatNumber(data?.totals.conversations ?? 0)}`}
            icon={<Bot size={15} />}
          />
          <MetricCard
            label={t("dashboard.tokens")}
            value={compactNumber(data?.totals.tokens ?? 0)}
            hint={`${t("dashboard.requests")}: ${formatNumber(data?.totals.requests ?? 0)}`}
            icon={<Activity size={15} />}
            tone="violet"
          />
          <MetricCard
            label={t("dashboard.cost")}
            value={formatCost(data?.totals.cost ?? 0)}
            hint={`${t("dashboard.messages")}: ${formatNumber(data?.totals.messages ?? 0)}`}
            icon={<Coins size={15} />}
            tone="success"
          />
          <MetricCard
            label={t("dashboard.errors")}
            value={formatNumber(data?.totals.errors ?? 0)}
            hint={`${t("dashboard.conversations")}: ${formatNumber(data?.totals.conversations ?? 0)}`}
            icon={<AlertTriangle size={15} />}
            tone="warning"
          />
        </div>
      )}

      <Card className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-ink">{t("dashboard.activity")}</h2>
            <p className="text-[11px] text-muted">{t("dashboard.activityHint")}</p>
          </div>
        </div>
        {overview.isLoading ? (
          <Skeleton className="h-[150px]" />
        ) : (
          <ActivityChart points={data?.series ?? []} emptyLabel={t("dashboard.noUsage")} />
        )}
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card className="space-y-2">
          <h2 className="text-sm font-semibold text-ink">{t("dashboard.topAgents")}</h2>
          {overview.isLoading ? (
            <Skeleton className="h-32" />
          ) : data && data.top_agents.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>{t("dashboard.tableAgent")}</Th>
                  <Th className="text-right">{t("dashboard.tableTokens")}</Th>
                  <Th className="text-right">{t("dashboard.tableCost")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.top_agents.map((agent) => (
                  <tr key={agent.agent_id}>
                    <Td>
                      <span className="flex min-w-0 items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ background: agent.avatar_color }}
                        />
                        <span className="truncate">{agent.name}</span>
                      </span>
                    </Td>
                    <Td className="tabular text-right">{formatNumber(agent.tokens)}</Td>
                    <Td className="tabular text-right text-muted">{formatCost(agent.cost)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title={t("dashboard.emptyTitle")} description={t("dashboard.emptyBody")} />
          )}
        </Card>

        <Card className="space-y-2">
          <h2 className="text-sm font-semibold text-ink">{t("dashboard.providers")}</h2>
          {overview.isLoading ? (
            <Skeleton className="h-32" />
          ) : data && data.providers.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>{t("common.name")}</Th>
                  <Th className="text-right">{t("dashboard.tableRequests")}</Th>
                  <Th className="text-right">{t("dashboard.tableStatus")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.providers.map((provider) => (
                  <tr key={provider.provider_id}>
                    <Td>
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate">{provider.name}</span>
                        <span className="text-[11px] text-muted">{provider.kind}</span>
                      </span>
                    </Td>
                    <Td className="tabular text-right">{formatNumber(provider.requests)}</Td>
                    <Td className="text-right">
                      <Badge tone={statusTone(provider.status)}>
                        {provider.status === "ok"
                          ? t("providers.statusOk")
                          : provider.status === "error"
                            ? t("providers.statusError")
                            : t("providers.statusUnknown")}
                      </Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title={t("dashboard.emptyTitle")} description={t("dashboard.emptyBody")} />
          )}
        </Card>
      </div>

      <p className="flex items-center gap-1.5 text-[11px] text-muted">
        <MessagesSquare size={12} />
        {t("dashboard.activityHint")}
      </p>
    </div>
  );
}
