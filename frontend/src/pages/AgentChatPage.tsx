import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BrainCircuit,
  MessageSquarePlus,
  Send,
  Trash2,
} from "lucide-react";

import {
  useAgent,
  useConversation,
  useConversationMutations,
  useConversations,
  useSendMessage,
} from "../api/hooks";
import { ConfirmDialog, useToast } from "../components/overlays";
import { Badge, Button, EmptyState, IconButton, Skeleton, Spinner, Textarea } from "../components/ui";
import { useI18n } from "../i18n";
import { cn, errorCode, formatCost } from "../lib/utils";

export function AgentChatPage() {
  const { t, formatDate, formatNumber } = useI18n();
  const navigate = useNavigate();
  const toast = useToast();
  const { id: agentId } = useParams();
  const agentQuery = useAgent(agentId);
  const conversations = useConversations(agentId);
  const conversationMutations = useConversationMutations();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingText, setPendingText] = useState<string | null>(null);
  const [mobilePane, setMobilePane] = useState<"list" | "chat">("list");
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const conversationQuery = useConversation(selectedId);
  const sendMessage = useSendMessage(selectedId);

  const items = conversations.data?.items ?? [];

  useEffect(() => {
    if (!selectedId && items.length > 0) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [conversationQuery.data?.messages.length, pendingText, sendMessage.isPending]);

  const messages = conversationQuery.data?.messages ?? [];
  const agent = agentQuery.data;

  const createConversation = () => {
    if (!agentId) return;
    conversationMutations.create.mutate(agentId, {
      onSuccess: (conversation) => {
        setSelectedId(conversation.id);
        setDraft("");
        setMobilePane("chat");
      },
      onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
    });
  };

  const send = () => {
    const content = draft.trim();
    if (!content || !selectedId || sendMessage.isPending) return;
    abortRef.current = new AbortController();
    setPendingText(content);
    setDraft("");
    sendMessage.mutate({ content, signal: abortRef.current.signal }, {
      onSuccess: () => {
        abortRef.current = null;
        setPendingText(null);
      },
      onError: (error) => {
        abortRef.current = null;
        if (error instanceof DOMException && error.name === "AbortError") {
          setPendingText(null);
          setDraft(content);
          return;
        }
        setPendingText(null);
        setDraft(content);
        toast.push(t(`errors.${errorCode(error)}`), "error");
      },
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  const activeConversation = conversationQuery.data;
  const modelLabel = useMemo(
    () => agent?.model_name || t("agents.noModel"),
    [agent?.model_name, t],
  );

  if (agentQuery.isError) {
    return (
      <EmptyState
        title={t("chat.noAgent")}
        description={t("errors.AGENT_NOT_FOUND")}
        action={<Button onClick={() => navigate("/agents")}>{t("chat.backToAgents")}</Button>}
      />
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-104px)] w-full max-w-6xl gap-3">
      <aside
        className={cn(
          "w-full shrink-0 flex-col gap-2 rounded-xl border border-line bg-card p-2 sm:w-[250px]",
          mobilePane === "chat" ? "hidden sm:flex" : "flex",
        )}
      >
        <div className="flex items-center gap-1 px-1">
          <p className="min-w-0 flex-1 truncate text-[12px] font-semibold uppercase tracking-wide text-muted">
            {t("chat.conversations")}
          </p>
          <IconButton label={t("chat.newChat")} onClick={createConversation}>
            <MessageSquarePlus size={14} />
          </IconButton>
        </div>

        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {conversations.isLoading ? (
            <div className="space-y-1">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-12" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <p className="px-2 py-4 text-[12px] text-muted">{t("chat.noConversations")}</p>
          ) : (
            items.map((conversation) => (
              <div
                key={conversation.id}
                className={cn(
                  "group flex items-center gap-1 rounded-lg px-2 py-1.5",
                  conversation.id === selectedId ? "bg-accent/10" : "hover:bg-raised",
                )}
              >
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(conversation.id);
                    setMobilePane("chat");
                  }}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate text-[12.5px] font-medium text-ink">
                    {conversation.title || t("chat.untitled")}
                  </span>
                  <span className="block truncate text-[10.5px] text-muted">
                    {formatDate(conversation.last_message_at ?? conversation.created_at, true)} ·{" "}
                    {formatNumber(conversation.total_tokens)} {t("common.tokensShort")}
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={t("common.delete")}
                  onClick={() => setPendingDelete(conversation.id)}
                  className="rounded p-1 text-muted opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <section
        className={cn(
          "min-w-0 flex-1 flex-col rounded-xl border border-line bg-card",
          mobilePane === "list" ? "hidden sm:flex" : "flex",
        )}
      >
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <Button
            variant="ghost"
            size="sm"
            className="px-1.5 sm:hidden"
            onClick={() => setMobilePane("list")}
            aria-label={t("chat.conversations")}
          >
            <ArrowLeft size={15} />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-ink">
              {agent?.name ?? t("common.loading")}
            </p>
            <p className="truncate text-[11px] text-muted">{modelLabel}</p>
          </div>
          <Badge tone="accent">{modelLabel}</Badge>
          <Button size="sm" variant="secondary" onClick={createConversation}>
            <MessageSquarePlus size={13} />
            <span className="hidden sm:inline">{t("chat.newChat")}</span>
          </Button>
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-4 sm:px-4">
          {!selectedId ? (
            <div className="flex h-full items-center justify-center">
              <EmptyState
                title={t("chat.emptyTitle")}
                description={t("chat.emptyBody")}
                action={
                  <Button onClick={createConversation}>
                    <MessageSquarePlus size={15} />
                    {t("chat.newChat")}
                  </Button>
                }
              />
            </div>
          ) : conversationQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-3/4" />
              <Skeleton className="ml-auto h-14 w-2/3" />
              <Skeleton className="h-20 w-4/5" />
            </div>
          ) : messages.length === 0 && !pendingText ? (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-md rounded-xl border border-line bg-raised/40 p-4 text-center">
                <p className="text-[13px] font-medium text-ink">{t("chat.emptyTitle")}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted">
                  {agent?.greeting || t("chat.emptyBody")}
                </p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => {
                const isUser = message.role === "user";
                return (
                  <div
                    key={message.id}
                    className={cn("flex min-w-0 flex-col gap-1", isUser ? "items-end" : "items-start")}
                  >
                    <span className="px-1 text-[10px] uppercase tracking-wide text-muted">
                      {isUser ? t("chat.you") : t("chat.assistant")}
                    </span>
                    <div
                      className={cn(
                        "max-w-[92%] whitespace-pre-wrap break-words rounded-xl px-3 py-2 text-[13px] leading-relaxed sm:max-w-[80%]",
                        isUser
                          ? "bg-accent text-white"
                          : "border border-line bg-raised/60 text-ink",
                      )}
                    >
                      {message.content}
                    </div>
                    {!isUser ? (
                      <>
                      <span className="tabular flex flex-wrap items-center gap-2 px-1 text-[10.5px] text-muted">
                        <span>{message.model_name}</span>
                        <span>·</span>
                        <span>
                          {t("chat.tokensIn")} {formatNumber(message.tokens_in)} / {t("chat.tokensOut")}{" "}
                          {formatNumber(message.tokens_out)}
                        </span>
                        <span>·</span>
                        <span>{message.latency_ms} ms</span>
                      </span>
                      {Array.isArray(message.meta.sources) && message.meta.sources.length > 0 ? (
                        <div className="flex flex-wrap items-center gap-1.5 px-1 text-[10.5px] text-muted">
                          <span className="font-semibold text-violet">Источники:</span>
                          {message.meta.sources.map((source) => {
                            const item = source as { title?: string; chunk_index?: number };
                            return <span key={`${item.title}-${item.chunk_index}`} className="rounded-md border border-violet/20 bg-violet/10 px-1.5 py-0.5 text-violet">{item.title ?? "Документ"} · {Number(item.chunk_index ?? 0) + 1}</span>;
                          })}
                        </div>
                      ) : null}
                      {Array.isArray(message.meta.memory_context) && message.meta.memory_context.length > 0 ? (
                        <div className="flex flex-wrap items-center gap-1.5 px-1 text-[10.5px] text-muted">
                          <span className="flex items-center gap-1 font-semibold text-accent"><BrainCircuit size={12} /> Память использована:</span>
                          {message.meta.memory_context.map((memory) => {
                            const item = memory as { memory_id?: string; content?: string; reason?: string };
                            return <span key={item.memory_id} title={item.reason ?? "Контекст агента"} className="max-w-[260px] truncate rounded-md border border-accent/20 bg-accent/10 px-1.5 py-0.5 text-accent">{item.content ?? "Факт"} · {item.reason ?? "контекст"}</span>;
                          })}
                        </div>
                      ) : null}
                      </>
                    ) : null}
                  </div>
                );
              })}

              {pendingText ? (
                <div className="flex flex-col items-end gap-1">
                  <span className="px-1 text-[10px] uppercase tracking-wide text-muted">{t("chat.you")}</span>
                  <div className="max-w-[92%] whitespace-pre-wrap break-words rounded-xl bg-accent/80 px-3 py-2 text-[13px] text-white sm:max-w-[80%]">
                    {pendingText}
                  </div>
                </div>
              ) : null}

              {sendMessage.isPending ? (
                <div className="flex items-center gap-2 px-1 text-[12px] text-muted">
                  <Spinner size={12} />
                  {t("chat.thinking")}
                  <button
                    type="button"
                    className="rounded-md border border-line px-2 py-1 text-[11px] text-ink hover:bg-raised"
                    onClick={() => abortRef.current?.abort()}
                  >
                    Остановить
                  </button>
                </div>
              ) : null}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="border-t border-line p-2 sm:p-3">
          {activeConversation ? (
            <div className="tabular mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-[10.5px] text-muted">
              <span>
                {formatNumber(activeConversation.total_tokens)} {t("common.tokensShort")}
              </span>
              <span>{formatCost(activeConversation.total_cost)}</span>
              <span>{activeConversation.message_count} {t("dashboard.messages")}</span>
            </div>
          ) : null}
          <div className="flex items-end gap-2">
            <Textarea
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder={t("chat.placeholder")}
              disabled={!selectedId}
              className="max-h-32 min-h-[42px] resize-none"
            />
            <Button onClick={send} disabled={!draft.trim() || !selectedId || sendMessage.isPending}>
              <Send size={15} />
              <span className="hidden sm:inline">{t("chat.send")}</span>
            </Button>
          </div>
        </footer>
      </section>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={t("chat.deleteTitle")}
        description={t("chat.deleteBody")}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        pending={conversationMutations.remove.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return;
          conversationMutations.remove.mutate(pendingDelete, {
            onSuccess: () => {
              if (pendingDelete === selectedId) setSelectedId(null);
              setPendingDelete(null);
            },
            onError: (error) => toast.push(t(`errors.${errorCode(error)}`), "error"),
          });
        }}
      />
    </div>
  );
}
