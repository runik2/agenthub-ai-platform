import { useEffect, useRef, useState, type ReactNode } from "react";
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
  Wrench,
  UsersRound,
  BookOpen,
  FlaskConical,
  RadioTower,
  X,
  Command,
  Search,
  ArrowRight,
} from "lucide-react";

import { useLogout, useMe } from "../api/hooks";
import { LanguageToggle } from "./LanguageToggle";
import { ThemeToggle } from "../theme";
import { useI18n } from "../i18n";
import { cn } from "../lib/utils";

type NavItem = { to: string; key?: string; label?: string; icon: typeof Brain; end?: boolean; admin?: boolean };

const mainNav: NavItem[] = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/agents", key: "nav.agents", icon: Bot },
  { to: "/providers", key: "nav.providers", icon: Plug },
  { to: "/logs", key: "nav.logs", icon: ScrollText, admin: true },
  { to: "/settings", key: "nav.settings", icon: Settings },
];

const soonNav: NavItem[] = [
  { to: "/memories", label: "Память", icon: Brain },
  { to: "/tools", key: "nav.tools", icon: Wrench },
  { to: "/team", label: "Команда", icon: UsersRound },
  { to: "/knowledge", label: "База знаний", icon: BookOpen },
  { to: "/evaluations", label: "Evaluations", icon: FlaskConical },
  { to: "/webhooks", label: "Webhooks", icon: RadioTower },
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
  const [commandOpen, setCommandOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [commandIndex, setCommandIndex] = useState(0);
  const commandInputRef = useRef<HTMLInputElement>(null);

  const openCommandPalette = () => {
    setCommandQuery("");
    setCommandIndex(0);
    setCommandOpen(true);
  };

  useEffect(() => {
    setMenuOpen(false);
    setCommandOpen(false);
    setCommandQuery("");
    setCommandIndex(0);
  }, [location.pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((open) => {
          if (open) return false;
          openCommandPalette();
          return true;
        });
      }
      if (event.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (commandOpen) window.setTimeout(() => commandInputRef.current?.focus(), 0);
  }, [commandOpen]);

  useEffect(() => {
    setCommandIndex(0);
  }, [commandQuery]);

  const commandItems = [...mainNav, ...soonNav]
    .filter((item) => !item.admin || user?.role === "admin")
    .map((item) => ({
      ...item,
      label: item.label ?? t(item.key ?? ""),
    }))
    .filter((item) => item.label.toLowerCase().includes(commandQuery.trim().toLowerCase()));

  const goTo = (path: string) => {
    setCommandOpen(false);
    navigate(path);
  };

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
                      : location.pathname.startsWith("/tools")
                        ? t("nav.tools")
                        : location.pathname.startsWith("/team")
                          ? "Команда"
                          : location.pathname.startsWith("/knowledge")
                            ? "База знаний"
                            : location.pathname.startsWith("/evaluations")
                              ? "Evaluations"
                              : location.pathname.startsWith("/webhooks")
                                ? "Webhooks"
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
                  <span className="truncate">{item.label ?? t(item.key ?? "")}</span>
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
              {item.to ? (
                <NavLink
                  to={item.to}
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
                  <span className="truncate">{item.label ?? t(item.key ?? "")}</span>
                </NavLink>
              ) : null}
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
            <button
              type="button"
              onClick={openCommandPalette}
              className="hidden items-center gap-1 rounded-lg border border-line bg-card/70 px-2 py-1 text-[10px] text-muted transition hover:border-accent/50 hover:text-ink xl:flex"
            >
              <Command size={11} /> K
            </button>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 sm:py-6">{children}</main>
      </div>

      {commandOpen ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/45 px-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setCommandOpen(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Навигация AgentHub"
            className="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-card shadow-2xl shadow-slate-950/25"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search size={17} className="shrink-0 text-muted" />
              <input
                ref={commandInputRef}
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setCommandIndex((index) => Math.min(index + 1, Math.max(commandItems.length - 1, 0)));
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    setCommandIndex((index) => Math.max(index - 1, 0));
                  } else if (event.key === "Enter" && commandItems[commandIndex]) {
                    event.preventDefault();
                    goTo(commandItems[commandIndex].to);
                  }
                }}
                placeholder="Перейти в раздел…"
                className="h-14 min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-muted"
              />
              <kbd className="rounded-md border border-line bg-raised px-1.5 py-0.5 text-[10px] text-muted">ESC</kbd>
            </div>
            <div className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
              {commandItems.map((item, index) => (
                <button
                  type="button"
                  key={item.to}
                  onClick={() => goTo(item.to)}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-accent/10",
                    commandIndex === index ? "bg-accent/10" : "",
                  )}
                >
                  <span className="grid h-8 w-8 place-items-center rounded-lg bg-raised text-muted transition group-hover:bg-accent/15 group-hover:text-accent">
                    <item.icon size={15} />
                  </span>
                  <span className="flex-1 text-sm font-medium text-ink">{item.label}</span>
                  <ArrowRight size={14} className="text-muted/50 transition group-hover:translate-x-0.5 group-hover:text-accent" />
                </button>
              ))}
              {!commandItems.length ? <p className="px-3 py-10 text-center text-sm text-muted">Ничего не найдено</p> : null}
            </div>
            <div className="flex items-center gap-3 border-t border-line bg-raised/40 px-4 py-2 text-[10px] text-muted">
              <span><kbd className="rounded border border-line bg-card px-1">Ctrl</kbd> + <kbd className="rounded border border-line bg-card px-1">K</kbd> открыть</span>
              <span>Быстрый переход по AgentHub</span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
