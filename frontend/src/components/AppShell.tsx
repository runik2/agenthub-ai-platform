import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Brain,
  Bot,
  CalendarClock,
  ChevronRight,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Plug,
  ScrollText,
  Settings,
  Workflow,
  X,
  Command,
} from "lucide-react";

import { useLogout, useMe } from "../api/hooks";
import { LanguageToggle } from "./LanguageToggle";
import { ThemeToggle } from "../theme";
import { useI18n } from "../i18n";
import { cn } from "../lib/utils";

const mainNav = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/agents", key: "nav.agents", icon: Bot },
  { to: "/providers", key: "nav.providers", icon: Plug },
  { to: "/logs", key: "nav.logs", icon: ScrollText, admin: true },
  { to: "/settings", key: "nav.settings", icon: Settings },
];

const soonNav: { to: string; key?: string; label?: string; icon: typeof Brain }[] = [
  { to: "/memories", label: "Память", icon: Brain },
  { to: "/tasks", key: "nav.tasks", icon: ListChecks },
  { to: "/workflows", key: "nav.workflows", icon: Workflow },
  { to: "/schedules", key: "nav.schedules", icon: CalendarClock },
  { to: "/analytics", key: "nav.analytics", icon: BarChart3 },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  const title =
    location.pathname === "/"
      ? t("nav.dashboard")
      : location.pathname.startsWith("/agents")
        ? t("nav.agents")
        : location.pathname.startsWith("/providers")
          ? t("nav.providers")
          : location.pathname.startsWith("/logs")
            ? t("nav.logs")
            : location.pathname.startsWith("/tasks")
              ? t("nav.tasks")
              : location.pathname.startsWith("/workflows")
                ? t("nav.workflows")
                : location.pathname.startsWith("/schedules")
                  ? t("nav.schedules")
                  : location.pathname.startsWith("/analytics")
                    ? t("nav.analytics")
                    : location.pathname.startsWith("/memories")
                      ? "Память"
            : t("nav.settings");

  const sidebar = (
    <div className="flex h-full w-[260px] shrink-0 flex-col border-r border-line bg-sidebar/95">
      <div className="flex h-16 items-center gap-2.5 border-b border-line px-4">
        <span className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-accent via-blue-500 to-violet text-[13px] font-bold text-white shadow-lg shadow-accent/20">
          <span className="absolute inset-1 rounded-lg border border-white/30" />A
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold tracking-tight text-ink">AgentHub</p>
          <p className="truncate text-[10px] uppercase tracking-[0.12em] text-muted">{t("app.tagline")}</p>
        </div>
        <button
          type="button"
          onClick={() => setMenuOpen(false)}
          aria-label={t("nav.closeMenu")}
          className="ml-auto rounded-lg p-1 text-muted hover:bg-raised lg:hidden"
        >
          <X size={16} />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <p className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted/80">
          {t("nav.main")}
        </p>
        <ul className="space-y-1">
          {mainNav
            .filter((item) => !item.admin || user?.role === "admin")
            .map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-lg px-2 py-2 text-[13px] transition-colors",
                      isActive
                        ? "bg-accent/10 text-ink shadow-[inset_2px_0_0_var(--accent)]"
                        : "text-muted hover:bg-raised hover:text-ink",
                    )
                  }
                >
                  <item.icon size={15} />
                  <span className="truncate">{t(item.key)}</span>
                </NavLink>
              </li>
            ))}
        </ul>

        <p className="mt-5 px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted/80">
          {t("nav.upcoming")}
        </p>
        <ul className="space-y-1">
          {soonNav.map((item) => (
            <li key={item.to}>
              {item.to ? <NavLink to={item.to} className="flex items-center gap-2 rounded-lg px-2 py-2 text-[13px] text-muted hover:bg-raised hover:text-ink">
                <item.icon size={15} />
                <span className="truncate">{item.label ?? t(item.key ?? "")}</span>
              </NavLink> : null}
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t border-line p-3">
        <div className="mb-2 flex items-center gap-2 rounded-lg bg-raised/60 px-2 py-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/15 text-[11px] font-semibold text-accent">
            {(user?.full_name || user?.email || "A").slice(0, 2).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[12px] font-medium text-ink">
              {user?.full_name || user?.email}
            </p>
            <p className="truncate text-[10px] uppercase tracking-wide text-muted">{user?.role}</p>
          </div>
          <button
            type="button"
            aria-label={t("nav.logout")}
            title={t("nav.logout")}
            onClick={() =>
              logout.mutate(undefined, {
                onSettled: () => navigate("/login", { replace: true }),
              })
            }
            className="rounded-lg p-1.5 text-muted hover:bg-card hover:text-danger"
          >
            <LogOut size={14} />
          </button>
        </div>
        <p className="px-1 text-[10px] text-muted/70">v0.1.0 · {t("common.localMode")}</p>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-canvas">
      <div className="hidden lg:block">{sidebar}</div>

      {menuOpen ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <div className="relative z-10 h-full">{sidebar}</div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-line bg-canvas/90 px-4 backdrop-blur">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label={t("nav.openMenu")}
            className="rounded-lg border border-line p-1.5 text-muted hover:text-ink lg:hidden"
          >
            <Menu size={16} />
          </button>
          <div className="flex min-w-0 items-center gap-1.5 text-[13px]">
            <span className="hidden text-muted sm:inline">AgentHub</span>
            <ChevronRight size={13} className="hidden text-muted/60 sm:inline" />
            <span className="truncate font-medium text-ink">{title}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-1 rounded-lg border border-line bg-card/70 px-2 py-1 text-[10px] text-muted xl:flex">
              <Command size={11} /> K
            </div>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 sm:py-6">{children}</main>
      </div>
    </div>
  );
}
