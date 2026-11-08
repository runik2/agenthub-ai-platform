import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { getToken } from "./api/client";
import { useMe, useSetupStatus } from "./api/hooks";
import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/ui";
const AgentChatPage = lazy(() => import("./pages/AgentChatPage").then(module => ({ default: module.AgentChatPage })));
const AgentFormPage = lazy(() => import("./pages/AgentFormPage").then(module => ({ default: module.AgentFormPage })));
const AgentsPage = lazy(() => import("./pages/AgentsPage").then(module => ({ default: module.AgentsPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then(module => ({ default: module.DashboardPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then(module => ({ default: module.LoginPage })));
const LogsPage = lazy(() => import("./pages/LogsPage").then(module => ({ default: module.LogsPage })));
const ProvidersPage = lazy(() => import("./pages/ProvidersPage").then(module => ({ default: module.ProvidersPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(module => ({ default: module.SettingsPage })));
const SetupPage = lazy(() => import("./pages/SetupPage").then(module => ({ default: module.SetupPage })));
const TasksPage = lazy(() => import("./pages/TasksPage").then(module => ({ default: module.TasksPage })));
const WorkflowsPage = lazy(() => import("./pages/WorkflowsPage").then(module => ({ default: module.WorkflowsPage })));
const SchedulesPage = lazy(() => import("./pages/SchedulesPage").then(module => ({ default: module.SchedulesPage })));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage").then(module => ({ default: module.AnalyticsPage })));
const MemoriesPage = lazy(() => import("./pages/MemoriesPage").then(module => ({ default: module.MemoriesPage })));
const ToolsPage = lazy(() => import("./pages/ToolsPage").then(module => ({ default: module.ToolsPage })));
const PromptVersionsPage = lazy(() => import("./pages/PromptVersionsPage").then(module => ({ default: module.PromptVersionsPage })));
const TeamPage = lazy(() => import("./pages/TeamPage").then(module => ({ default: module.TeamPage })));
const KnowledgePage = lazy(() => import("./pages/KnowledgePage").then(module => ({ default: module.KnowledgePage })));
const EvaluationsPage = lazy(() => import("./pages/EvaluationsPage").then(module => ({ default: module.EvaluationsPage })));
const WebhooksPage = lazy(() => import("./pages/WebhooksPage").then(module => ({ default: module.WebhooksPage })));
const InvitePage = lazy(() => import("./pages/InvitePage").then(module => ({ default: module.InvitePage })));

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
    <Suspense fallback={<Splash />}>
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
    </Suspense>
  );
}
