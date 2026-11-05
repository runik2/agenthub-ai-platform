import { type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { getToken } from "./api/client";
import { useMe, useSetupStatus } from "./api/hooks";
import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/ui";
import { AgentChatPage } from "./pages/AgentChatPage";
import { AgentFormPage } from "./pages/AgentFormPage";
import { AgentsPage } from "./pages/AgentsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { LogsPage } from "./pages/LogsPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupPage } from "./pages/SetupPage";
import { TasksPage } from "./pages/TasksPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";
import { SchedulesPage } from "./pages/SchedulesPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { MemoriesPage } from "./pages/MemoriesPage";
import { ToolsPage } from "./pages/ToolsPage";
import { PromptVersionsPage } from "./pages/PromptVersionsPage";
import { TeamPage } from "./pages/TeamPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { EvaluationsPage } from "./pages/EvaluationsPage";
import { WebhooksPage } from "./pages/WebhooksPage";
import { InvitePage } from "./pages/InvitePage";

function Splash() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas text-muted">
      <Spinner size={22} />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const token = getToken();
  const me = useMe();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (me.isLoading) {
    return <Splash />;
  }
  if (me.isError) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell>{children}</AppShell>;
}

function SetupGuard({ children }: { children: ReactNode }) {
  const location = useLocation();
  const status = useSetupStatus();

  if (status.isLoading) {
    return <Splash />;
  }
  if (status.data?.needs_setup && location.pathname !== "/setup") {
    return <Navigate to="/setup" replace />;
  }
  if (!status.data?.needs_setup && location.pathname === "/setup") {
    return <Navigate to={getToken() ? "/" : "/login"} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <SetupGuard>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/invite" element={<InvitePage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/agents"
          element={
            <RequireAuth>
              <AgentsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/agents/new"
          element={
            <RequireAuth>
              <AgentFormPage mode="create" />
            </RequireAuth>
          }
        />
        <Route
          path="/agents/:id/edit"
          element={
            <RequireAuth>
              <AgentFormPage mode="edit" />
            </RequireAuth>
          }
        />
        <Route path="/agents/:id/versions" element={<RequireAuth><PromptVersionsPage /></RequireAuth>} />
        <Route
          path="/agents/:id/chat"
          element={
            <RequireAuth>
              <AgentChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/providers"
          element={
            <RequireAuth>
              <ProvidersPage />
            </RequireAuth>
          }
        />
        <Route
          path="/logs"
          element={
            <RequireAuth>
              <LogsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <SettingsPage />
            </RequireAuth>
          }
        />
        <Route path="/tasks" element={<RequireAuth><TasksPage /></RequireAuth>} />
        <Route path="/workflows" element={<RequireAuth><WorkflowsPage /></RequireAuth>} />
        <Route path="/schedules" element={<RequireAuth><SchedulesPage /></RequireAuth>} />
        <Route path="/analytics" element={<RequireAuth><AnalyticsPage /></RequireAuth>} />
        <Route path="/memories" element={<RequireAuth><MemoriesPage /></RequireAuth>} />
        <Route path="/tools" element={<RequireAuth><ToolsPage /></RequireAuth>} />
        <Route path="/team" element={<RequireAuth><TeamPage /></RequireAuth>} />
        <Route path="/knowledge" element={<RequireAuth><KnowledgePage /></RequireAuth>} />
        <Route path="/evaluations" element={<RequireAuth><EvaluationsPage /></RequireAuth>} />
        <Route path="/webhooks" element={<RequireAuth><WebhooksPage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </SetupGuard>
  );
}
