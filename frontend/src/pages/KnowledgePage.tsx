import { useEffect, useState } from "react";
import { BookOpen, FileText, Link2, Pencil, Plus, RefreshCw, Save, Search, Trash2, Upload, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { request } from "../api/client";
import { useAgents } from "../api/hooks";
import { Badge, Button, Card, IconButton, Input, Select, Textarea } from "../components/ui";

type Document = {
  id: string;
  title: string;
  agent_id: string | null;
  chunk_count: number;
  version: number;
  created_at: string;
};
type DocumentDetail = Document & { content: string };
type Result = { document_id: string; title: string; chunk_index: number; content: string; score: number };

export function KnowledgePage() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [agentId, setAgentId] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [editingContent, setEditingContent] = useState("");
  const agents = useAgents({ page: 1, search: "", status: "" });
  const docs = useQuery({
    queryKey: ["knowledge-documents"],
    queryFn: () => request<Document[]>("/knowledge/documents"),
  });
  const detail = useQuery({ queryKey: ["knowledge-document", editingId], queryFn: () => request<DocumentDetail>(`/knowledge/documents/${editingId}`), enabled: Boolean(editingId) });
  useEffect(() => { if (detail.data) { setEditingTitle(detail.data.title); setEditingContent(detail.data.content); } }, [detail.data]);
  const results = useQuery({
    queryKey: ["knowledge-search", search, agentId],
    queryFn: () => request<Result[]>("/knowledge/search", { query: { q: search, agent_id: agentId || undefined } }),
    enabled: search.length > 1,
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["knowledge-documents"] });
  const create = useMutation({
    mutationFn: () => request<Document>("/knowledge/documents", { method: "POST", body: { title, content, agent_id: agentId || null } }),
    onSuccess: () => { setTitle(""); setContent(""); invalidate(); },
  });
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file as File);
      if (agentId) form.append("agent_id", agentId);
      return request<Document>("/knowledge/documents/upload", { method: "POST", body: form });
    },
    onSuccess: () => { setFile(null); invalidate(); },
  });
  const importWeb = useMutation({
    mutationFn: () => request<Document>("/knowledge/documents/web", { method: "POST", query: { url, agent_id: agentId || undefined } }),
    onSuccess: () => { setUrl(""); invalidate(); },
  });
  const reindex = useMutation({
    mutationFn: (id: string) => request<Document>(`/knowledge/documents/${id}/reindex`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => request<void>(`/knowledge/documents/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  const update = useMutation({ mutationFn: () => request<Document>(`/knowledge/documents/${editingId}`, { method: "PATCH", body: { title: editingTitle, content: editingContent } }), onSuccess: () => { setEditingId(null); invalidate(); } });

  return <div className="mx-auto max-w-6xl space-y-5">
    <section className="relative overflow-hidden rounded-2xl border border-violet/20 bg-gradient-to-br from-violet/[.14] via-card to-accent/[.08] p-6">
      <div className="absolute -right-12 -top-16 h-52 w-52 rounded-full bg-violet/20 blur-3xl" />
      <div className="relative"><p className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[.16em] text-violet"><BookOpen size={14} /> Retrieval augmented context</p><h1 className="text-3xl font-semibold tracking-tight text-ink">База знаний</h1><p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted">Загрузите инструкции, регламенты и заметки — AgentHub разобьёт их на чанки, найдёт релевантные фрагменты и покажет источники ответа.</p></div>
    </section>
    <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
      <Card className="h-fit space-y-3">
        <div><p className="text-[11px] font-bold uppercase tracking-wider text-accent">Новый источник</p><h2 className="mt-1 font-semibold text-ink">Документ или заметка</h2></div>
        <Input value={title} onChange={event => setTitle(event.target.value)} placeholder="Название источника" />
        <Textarea value={content} onChange={event => setContent(event.target.value)} placeholder="Вставьте текст инструкции, FAQ или регламент…" className="min-h-36" />
        <Select value={agentId} onChange={event => setAgentId(event.target.value)}><option value="">Доступен всем агентам</option>{agents.data?.items.map(agent => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</Select>
        <Button className="w-full" disabled={!title.trim() || !content.trim()} loading={create.isPending} onClick={() => create.mutate()}><Plus size={15} /> Индексировать текст</Button>
        <div className="border-t border-line pt-3"><p className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink"><Upload size={13} /> Файл до 10 MB</p><Input type="file" accept=".txt,.csv,.md,.json,.pdf,.docx" onChange={event => setFile(event.target.files?.[0] ?? null)} className="h-auto py-2 text-xs" /><Button className="mt-2 w-full" variant="secondary" disabled={!file} loading={upload.isPending} onClick={() => upload.mutate()}><Upload size={14} /> Загрузить и индексировать</Button></div>
        <div className="border-t border-line pt-3"><p className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink"><Link2 size={13} /> Веб-страница</p><Input value={url} onChange={event => setUrl(event.target.value)} placeholder="https://example.com/guide" /><Button className="mt-2 w-full" variant="secondary" disabled={!url.startsWith("https://")} loading={importWeb.isPending} onClick={() => importWeb.mutate()}><Link2 size={14} /> Импортировать страницу</Button></div>
      </Card>
      <Card className="min-h-[450px]">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-wider text-muted">Источники</p><h2 className="mt-1 font-semibold text-ink">Индекс знаний</h2></div><div className="relative w-full sm:w-72"><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={15} /><Input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => event.key === "Enter" && setSearch(query)} placeholder="Поиск по знаниям · Enter" className="pl-9" /></div></div>
        {search ? <div className="mt-4 space-y-2 rounded-xl border border-accent/20 bg-accent/[.04] p-3"><p className="text-[11px] font-semibold uppercase tracking-wider text-accent">Релевантные фрагменты</p>{results.data?.map(result => <div key={`${result.document_id}-${result.chunk_index}`} className="rounded-lg border border-line bg-card p-3"><div className="flex items-center gap-2"><FileText size={13} className="text-accent" /><span className="text-xs font-semibold text-ink">{result.title} · фрагмент {result.chunk_index + 1}</span><Badge tone="accent">score {result.score}</Badge></div><p className="mt-2 text-sm leading-relaxed text-muted">{result.content}</p></div>) ?? <p className="py-4 text-center text-sm text-muted">Ищем…</p>}</div> : null}
        {editingId ? <div className="mt-5 space-y-3 rounded-xl border border-accent/25 bg-accent/[.04] p-4"><div className="flex items-center justify-between"><div><p className="text-[11px] font-bold uppercase tracking-wider text-accent">Новая версия источника</p><h3 className="font-semibold text-ink">Редактирование документа</h3></div><IconButton label="Закрыть" onClick={() => setEditingId(null)}><X size={14} /></IconButton></div><Input value={editingTitle} onChange={event => setEditingTitle(event.target.value)} /><Textarea value={editingContent} onChange={event => setEditingContent(event.target.value)} className="min-h-40" /><Button disabled={!editingTitle.trim() || !editingContent.trim()} loading={update.isPending} onClick={() => update.mutate()}><Save size={14} /> Сохранить новую версию</Button></div> : null}
        <div className="mt-5 space-y-2">{docs.data?.map(doc => <article key={doc.id} className="flex items-center gap-3 rounded-xl border border-line bg-card/50 p-4"><span className="grid h-9 w-9 place-items-center rounded-xl bg-violet/10 text-violet"><FileText size={16} /></span><div className="min-w-0 flex-1"><p className="truncate font-semibold text-ink">{doc.title}</p><p className="text-xs text-muted">v{doc.version} · {doc.chunk_count} чанков · {doc.agent_id ? "для выбранного агента" : "общий источник"}</p></div><IconButton label="Редактировать" onClick={() => setEditingId(doc.id)}><Pencil size={14} /></IconButton><IconButton label="Переиндексировать" onClick={() => reindex.mutate(doc.id)}><RefreshCw size={14} className={reindex.isPending ? "animate-spin" : ""} /></IconButton><IconButton label="Удалить источник" tone="danger" onClick={() => remove.mutate(doc.id)}><Trash2 size={14} /></IconButton></article>)}{!docs.data?.length && !docs.isLoading ? <div className="py-16 text-center"><BookOpen className="mx-auto text-muted/50" size={34} /><p className="mt-3 font-medium text-ink">База знаний пока пуста</p></div> : null}</div>
      </Card>
    </div>
  </div>;
}
