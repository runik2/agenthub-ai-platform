import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

import { useAppSettings } from "../api/hooks";
import { Badge, Card, Skeleton } from "../components/ui";
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
    </div>
  );
}
