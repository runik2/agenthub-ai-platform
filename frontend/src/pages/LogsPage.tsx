import { useState } from "react";
import { Search } from "lucide-react";

import { useAuditLogs, useMe } from "../api/hooks";
import { Badge, Card, EmptyState, Input, Pagination, Skeleton, Table, Td, Th } from "../components/ui";
import { useI18n } from "../i18n";

export function LogsPage() {
  const { t, formatDate } = useI18n();
  const { data: user } = useMe();
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const logs = useAuditLogs(page, action);

  if (user && user.role !== "admin") {
    return (
      <div className="mx-auto max-w-4xl">
        <EmptyState title={t("logs.adminOnly")} description={t("errors.FORBIDDEN")} />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">{t("logs.title")}</h1>
        <p className="mt-0.5 text-[13px] text-muted">{t("logs.subtitle")}</p>
      </div>

      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <Input
          value={action}
          onChange={(event) => {
            setAction(event.target.value);
            setPage(1);
          }}
          placeholder={t("logs.filterAction")}
          className="pl-8"
          aria-label={t("logs.filterAction")}
        />
      </div>

      <Card className="p-0">
        {logs.isLoading ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-9" />
            ))}
          </div>
        ) : logs.data && logs.data.items.length > 0 ? (
          <div className="p-1">
            <Table>
              <thead>
                <tr>
                  <Th>{t("logs.time")}</Th>
                  <Th>{t("logs.action")}</Th>
                  <Th>{t("logs.entity")}</Th>
                  <Th>{t("logs.ip")}</Th>
                </tr>
              </thead>
              <tbody>
                {logs.data.items.map((entry) => (
                  <tr key={entry.id}>
                    <Td className="whitespace-nowrap text-muted">{formatDate(entry.created_at, true)}</Td>
                    <Td>
                      <Badge tone="accent">{entry.action}</Badge>
                    </Td>
                    <Td className="text-muted">
                      <span className="truncate">
                        {entry.entity_type || t("common.none")}
                        {entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}` : ""}
                      </span>
                    </Td>
                    <Td className="whitespace-nowrap font-mono text-[11px] text-muted">
                      {entry.ip_address ?? t("common.none")}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ) : (
          <div className="p-3">
            <EmptyState title={t("logs.emptyTitle")} description={t("logs.emptyBody")} />
          </div>
        )}
      </Card>

      {logs.data ? (
        <Pagination
          page={logs.data.page}
          pages={logs.data.pages}
          onChange={setPage}
          label={t("common.page", { page: logs.data.page, pages: logs.data.pages })}
          prevLabel={t("common.prev")}
          nextLabel={t("common.next")}
        />
      ) : null}
    </div>
  );
}
