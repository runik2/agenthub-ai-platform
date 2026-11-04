import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Copy, MessageSquare, Pencil, Plus, Search, Trash2 } from "lucide-react";

import { useAgentMutations, useAgents, useTemplates } from "../api/hooks";
import type { Agent } from "../api/types";
import { ConfirmDialog, useToast } from "../components/overlays";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  IconButton,
  Input,
  Pagination,
  Select,
  Skeleton,
} from "../components/ui";
import { useI18n } from "../i18n";
import { errorCode, initials } from "../lib/utils";

const statusTone = (status: Agent["status"]) =>
  status === "active" ? "success" : status === "draft" ? "warning" : "neutral";

export function AgentsPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Agent | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 320);
    return () => window.clearTimeout(timer);
  }, [search]);

  const agents = useAgents({ page, search: debounced, status });
  const templates = useTemplates();
  const mutations = useAgentMutations();

  const statusLabel = useMemo(
    () => ({
      active: t("agents.statusActive"),
      draft: t("agents.statusDraft"),
      archived: t("agents.statusArchived"),
    }),
    [t],
  );

  const onDelete = () => {
    if (!pendingDelete) return;
    mutations.remove.mutate(pendingDelete.id, {
      onSuccess: () => {
        toast.push(t("agents.deleted"), "success");
        setPendingDelete(null);
      },
      onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
    });
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-ink">{t("agents.title")}</h1>
          <p className="mt-0.5 text-[13px] text-muted">{t("agents.subtitle")}</p>
        </div>
        <Button onClick={() => navigate("/agents/new")}>
          <Plus size={15} />
          {t("agents.new")}
        </Button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative min-w-0 flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("agents.searchPlaceholder")}
            className="pl-8"
            aria-label={t("common.search")}
          />
        </div>
        <Select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="sm:w-48"
          aria-label={t("common.status")}
        >
          <option value="">{t("agents.allStatuses")}</option>
          <option value="active">{t("agents.statusActive")}</option>
          <option value="draft">{t("agents.statusDraft")}</option>
          <option value="archived">{t("agents.statusArchived")}</option>
        </Select>
      </div>

      {agents.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-[168px]" />
          ))}
        </div>
      ) : agents.data && agents.data.items.length > 0 ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {agents.data.items.map((agent) => (
              <Card key={agent.id} className="flex flex-col gap-3 p-4">
                <div className="flex items-start gap-3">
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[12px] font-semibold text-white"
                    style={{ background: agent.avatar_color }}
                  >
                    {initials(agent.name)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/agents/${agent.id}/chat`}
                      className="block truncate text-[14px] font-semibold text-ink hover:text-accent"
                    >
                      {agent.name}
                    </Link>
                    <p className="truncate text-[11px] text-muted">
                      {agent.model_name || t("agents.noModel")}
                    </p>
                  </div>
                  <Badge tone={statusTone(agent.status)}>{statusLabel[agent.status]}</Badge>
                </div>

                <p className="line-clamp-2 min-h-[32px] text-[12px] leading-relaxed text-muted">
                  {agent.description || t("common.none")}
                </p>

                <div className="flex flex-wrap gap-1">
                  {agent.tags.slice(0, 3).map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                  {agent.tags.length > 3 ? <Badge>+{agent.tags.length - 3}</Badge> : null}
                </div>

                <div className="mt-auto flex items-center gap-1.5 border-t border-line/70 pt-3">
                  <Button size="sm" variant="secondary" onClick={() => navigate(`/agents/${agent.id}/chat`)}>
                    <MessageSquare size={13} />
                    {t("agents.chat")}
                  </Button>
                  <IconButton
                    label={t("agents.edit")}
                    onClick={() => navigate(`/agents/${agent.id}/edit`)}
                  >
                    <Pencil size={13} />
                  </IconButton>
                  <IconButton
                    label={t("agents.duplicate")}
                    onClick={() =>
                      mutations.duplicate.mutate(agent.id, {
                        onSuccess: () => toast.push(t("agents.duplicated"), "success"),
                      })
                    }
                  >
                    <Copy size={13} />
                  </IconButton>
                  <IconButton
                    label={t("common.delete")}
                    tone="danger"
                    className="ml-auto"
                    onClick={() => setPendingDelete(agent)}
                  >
                    <Trash2 size={13} />
                  </IconButton>
                </div>
              </Card>
            ))}
          </div>
          <Pagination
            page={agents.data.page}
            pages={agents.data.pages}
            onChange={setPage}
            label={t("common.page", { page: agents.data.page, pages: agents.data.pages })}
            prevLabel={t("common.prev")}
            nextLabel={t("common.next")}
          />
        </>
      ) : (
        <EmptyState
          title={t("agents.emptyTitle")}
          description={t("agents.emptyBody")}
          action={
            <Button onClick={() => navigate("/agents/new")}>
              <Plus size={15} />
              {t("agents.new")}
            </Button>
          }
        />
      )}

      <section className="space-y-3 pt-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">{t("agents.templatesTitle")}</h2>
          <p className="text-[12px] text-muted">{t("agents.templatesSubtitle")}</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {(templates.data ?? []).map((template) => (
            <div
              key={template.slug}
              className="flex min-w-0 flex-col gap-2 rounded-xl border border-line bg-card/60 p-3"
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: template.avatar_color }}
                />
                <p className="truncate text-[13px] font-medium text-ink">
                  {t(`templates.${template.slug}.name`)}
                </p>
                <Badge className="ml-auto">{template.category}</Badge>
              </div>
              <p className="line-clamp-2 text-[11px] leading-relaxed text-muted">
                {t(`templates.${template.slug}.description`)}
              </p>
              <Button
                size="sm"
                variant="secondary"
                className="mt-auto w-full"
                loading={mutations.fromTemplate.isPending}
                onClick={() =>
                  mutations.fromTemplate.mutate(template.slug, {
                    onSuccess: (agent) => {
                      toast.push(t("agents.created"), "success");
                      navigate(`/agents/${agent.id}/edit`);
                    },
                    onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
                  })
                }
              >
                {t("agents.useTemplate")}
              </Button>
            </div>
          ))}
        </div>
      </section>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={t("agents.deleteTitle")}
        description={t("agents.deleteBody", { name: pendingDelete?.name ?? "" })}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        pending={mutations.remove.isPending}
        onConfirm={onDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
