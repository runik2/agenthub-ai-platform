import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { clearToken, getToken, request, setToken } from "./client";
import type {
  Agent,
  AgentPayload,
  AgentTemplate,
  AnalyticsOverview,
  AppSettings,
  AuditLogEntry,
  ConnectionResult,
  Conversation,
  ConversationDetail,
  Page,
  Provider,
  ProviderPayload,
  SendMessageResponse,
  TokenResponse,
  User,
} from "./types";

/* ---------------------------------- auth --------------------------------- */

export function useSetupStatus() {
  return useQuery({
    queryKey: ["setup-status"],
    queryFn: () => request<{ needs_setup: boolean }>("/auth/setup-status"),
    staleTime: 30_000,
  });
}

export function useMe(): UseQueryResult<User> {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => request<User>("/auth/me"),
    enabled: Boolean(getToken()),
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; password: string }) =>
      request<TokenResponse>("/auth/login", { method: "POST", body: payload }),
    onSuccess: (data) => {
      setToken(data.access_token);
      queryClient.setQueryData(["me"], data.user);
      queryClient.invalidateQueries();
    },
  });
}

export function useSetupAdmin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; password: string; full_name: string }) =>
      request<TokenResponse>("/auth/setup", { method: "POST", body: payload }),
    onSuccess: (data) => {
      setToken(data.access_token);
      queryClient.setQueryData(["me"], data.user);
      queryClient.invalidateQueries({ queryKey: ["setup-status"] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        await request<{ status: string }>("/auth/logout", { method: "POST" });
      } catch {
        /* the client token is dropped regardless */
      }
    },
    onSettled: () => {
      clearToken();
      queryClient.clear();
    },
  });
}

/* --------------------------------- agents -------------------------------- */

export function useAgents(params: { page: number; search: string; status: string }) {
  return useQuery({
    queryKey: ["agents", params],
    queryFn: () =>
      request<Page<Agent>>("/agents", {
        query: {
          page: params.page,
          page_size: 9,
          search: params.search || undefined,
          status: params.status || undefined,
        },
      }),
    placeholderData: (previous) => previous,
  });
}

export function useAgent(agentId: string | undefined) {
  return useQuery({
    queryKey: ["agent", agentId],
    queryFn: () => request<Agent>(`/agents/${agentId}`),
    enabled: Boolean(agentId),
  });
}

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: () => request<AgentTemplate[]>("/agents/templates"),
    staleTime: 10 * 60_000,
  });
}

export function useAgentMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["agents"] });
    queryClient.invalidateQueries({ queryKey: ["analytics"] });
  };

  const create = useMutation({
    mutationFn: (payload: AgentPayload) => request<Agent>("/agents", { method: "POST", body: payload }),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<AgentPayload> }) =>
      request<Agent>(`/agents/${id}`, { method: "PATCH", body: payload }),
    onSuccess: (data) => {
      queryClient.setQueryData(["agent", data.id], data);
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => request<{ status: string }>(`/agents/${id}?force=true`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  const duplicate = useMutation({
    mutationFn: (id: string) => request<Agent>(`/agents/${id}/duplicate`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const fromTemplate = useMutation({
    mutationFn: (slug: string) => request<Agent>(`/agents/from-template/${slug}`, { method: "POST" }),
    onSuccess: invalidate,
  });

  return { create, update, remove, duplicate, fromTemplate };
}

/* -------------------------------- providers ------------------------------- */

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => request<Page<Provider>>("/providers", { query: { page_size: 100 } }),
  });
}

export function useProviderMutations() {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["providers"] });

  const create = useMutation({
    mutationFn: (payload: ProviderPayload) => request<Provider>("/providers", { method: "POST", body: payload }),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProviderPayload> }) =>
      request<Provider>(`/providers/${id}`, { method: "PATCH", body: payload }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => request<{ status: string }>(`/providers/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
  const test = useMutation({
    mutationFn: (id: string) =>
      request<ConnectionResult>(`/providers/${id}/test-connection`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const refreshModels = useMutation({
    mutationFn: (id: string) =>
      request<{ models: string[] }>(`/providers/${id}/refresh-models`, { method: "POST" }),
    onSuccess: invalidate,
  });

  return { create, update, remove, test, refreshModels };
}

/* ------------------------------ conversations ----------------------------- */

export function useConversations(agentId: string | undefined) {
  return useQuery({
    queryKey: ["conversations", agentId],
    queryFn: () =>
      request<Page<Conversation>>("/conversations", {
        query: { agent_id: agentId, page_size: 50 },
      }),
    enabled: Boolean(agentId),
  });
}

export function useConversation(conversationId: string | null) {
  return useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => request<ConversationDetail>(`/conversations/${conversationId}`),
    enabled: Boolean(conversationId),
  });
}

export function useConversationMutations() {
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (agentId: string) =>
      request<ConversationDetail>("/conversations", { method: "POST", body: { agent_id: agentId } }),
    onSuccess: (_data, agentId) => {
      queryClient.invalidateQueries({ queryKey: ["conversations", agentId] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => request<{ status: string }>(`/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
  return { create, remove };
}

export function useSendMessage(conversationId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) =>
      request<SendMessageResponse>(`/conversations/${conversationId}/messages`, {
        method: "POST",
        body: { content },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

/* -------------------------------- analytics ------------------------------- */

export function useOverview(days: number) {
  return useQuery({
    queryKey: ["analytics", days],
    queryFn: () => request<AnalyticsOverview>("/analytics/overview", { query: { days } }),
  });
}

export function useAuditLogs(page: number, action: string) {
  return useQuery({
    queryKey: ["logs", page, action],
    queryFn: () =>
      request<Page<AuditLogEntry>>("/logs", {
        query: { page, page_size: 20, action: action || undefined },
      }),
    placeholderData: (previous) => previous,
  });
}

export function useAppSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: () => request<AppSettings>("/settings"),
    staleTime: 60_000,
  });
}
