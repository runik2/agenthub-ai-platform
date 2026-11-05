export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  two_factor_enabled?: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type AgentStatus = "draft" | "active" | "archived";

export interface Agent {
  id: string;
  name: string;
  slug: string;
  description: string;
  system_prompt: string;
  greeting: string;
  provider_id: string | null;
  model_name: string;
  temperature: number;
  max_tokens: number;
  status: AgentStatus;
  avatar_color: string;
  tags: string[];
  is_template: boolean;
  template_slug: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface AgentPayload {
  name: string;
  description: string;
  system_prompt: string;
  greeting: string;
  provider_id: string | null;
  model_name: string;
  temperature: number;
  max_tokens: number;
  status: AgentStatus;
  avatar_color: string;
  tags: string[];
}

export interface AgentTemplate {
  slug: string;
  name: string;
  description: string;
  system_prompt: string;
  greeting: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  tags: string[];
  avatar_color: string;
  category: string;
}

export type ProviderKind = "ollama" | "openai_compatible";

export interface Provider {
  id: string;
  name: string;
  kind: ProviderKind;
  base_url: string;
  default_model: string;
  input_price_per_1m: number;
  output_price_per_1m: number;
  is_active: boolean;
  has_api_key: boolean;
  api_key_hint: string | null;
  last_checked_at: string | null;
  last_check_status: "ok" | "error" | "unknown";
  last_check_message: string | null;
  models_cache: string[];
  created_at: string;
  updated_at: string;
}

export interface ProviderPayload {
  name: string;
  kind: ProviderKind;
  base_url: string;
  api_key?: string | null;
  default_model: string;
  input_price_per_1m: number;
  output_price_per_1m: number;
  is_active: boolean;
}

export interface ConnectionResult {
  status: "ok" | "error";
  message: string;
  models: string[];
  latency_ms: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  model_name: string;
  provider_id: string | null;
  error_code: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Conversation {
  id: string;
  agent_id: string;
  user_id: string;
  title: string;
  status: string;
  message_count: number;
  total_tokens: number;
  total_cost: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Usage {
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  cost: number;
  currency: string;
  latency_ms: number;
  model_name: string;
  estimated: boolean;
}

export interface SendMessageResponse {
  user_message: Message;
  assistant_message: Message;
  usage: Usage;
}

export interface AnalyticsTotals {
  agents: number;
  conversations: number;
  messages: number;
  requests: number;
  tokens_in: number;
  tokens_out: number;
  tokens: number;
  cost: number;
  errors: number;
}

export interface AnalyticsSeriesPoint {
  date: string;
  tokens: number;
  cost: number;
  messages: number;
}

export interface AnalyticsOverview {
  range_days: number;
  totals: AnalyticsTotals;
  series: AnalyticsSeriesPoint[];
  top_agents: {
    agent_id: string;
    name: string;
    avatar_color: string;
    tokens: number;
    cost: number;
    messages: number;
  }[];
  providers: {
    provider_id: string;
    name: string;
    kind: string;
    status: string;
    requests: number;
    tokens: number;
    cost: number;
  }[];
  budget: {
    tokens: number;
    cost: number;
    token_limit: number;
    cost_limit: number;
    warning_percent: number;
    ratio: number;
    status: "ok" | "warning" | "exceeded";
  };
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  ip_address: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AppSettings {
  app_name: string;
  version: string;
  app_mode: "local" | "docker";
  database_backend: string;
  ollama_base_url: string;
  seed_demo_data: boolean;
  features: Record<string, boolean>;
  runtime: { queue_backend: string; scheduler: string };
  docker_verified: boolean;
}
