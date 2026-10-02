import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AlertOctagon,
  Boxes,
  CircleDot,
  FolderGit2,
  FolderTree,
  Gauge,
  GitPullRequestArrow,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Network,
  Search,
  Settings as SettingsIcon,
  Sun,
  Wrench,
  X,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useRepositories } from "../hooks/queries";
import { setCurrentRepoId, useCurrentRepoId } from "../hooks/currentRepo";
import { Logo } from "../components/Logo";
import { Button, cx, Kbd } from "../components/ui";
import { CommandPalette } from "../components/CommandPalette";
import { ErrorBoundary } from "../components/ErrorBoundary";

function SideLink({
  to,
  icon: Icon,
  label,
  end,
  disabled,
  onNavigate,
}: {
  to: string;
  icon: typeof LayoutDashboard;
  label: string;
  end?: boolean;
  disabled?: boolean;
  onNavigate?: () => void;
}) {
  if (disabled) {
    return (
      <span
        className="flex h-8 cursor-not-allowed items-center gap-2.5 rounded px-2.5 text-sm text-faint"
        title="Open a repository first"
        aria-disabled="true"
      >
        <Icon className="h-4 w-4" aria-hidden />
        {label}
      </span>
    );
  }
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }: { isActive: boolean }) =>
        cx(
          "flex h-8 items-center gap-2.5 rounded px-2.5 text-sm transition-colors",
          isActive ? "bg-raised font-medium text-ink" : "text-muted hover:bg-raised/60 hover:text-ink",
        )
      }
    >
      <Icon className="h-4 w-4" aria-hidden />
      {label}
    </NavLink>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const repoId = useCurrentRepoId();
  const repositories = useRepositories();
  const current = repositories.data?.find((repo) => repo.id === repoId);
  const base = current ? `/app/r/${current.id}` : "";
  const repoDisabled = !current;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center px-4">
        <Link to="/app" onClick={onNavigate} aria-label="CodePulse AI home">
          <Logo />
        </Link>
      </div>
      <nav aria-label="Main" className="scroll-thin flex-1 space-y-5 overflow-y-auto px-3 pb-4 pt-2">
        <div className="space-y-0.5">
          <SideLink to="/app" end icon={LayoutDashboard} label="Overview" onNavigate={onNavigate} />
          <SideLink to="/app/repositories" icon={FolderGit2} label="Repositories" onNavigate={onNavigate} />
        </div>
        <div>
          <p className="mb-1.5 truncate px-2.5 text-xs text-faint" title={current?.full_name}>
            {current ? current.full_name : "No repository open"}
          </p>
          <div className="space-y-0.5">
            <SideLink to={base} end icon={CircleDot} label="Start here" disabled={repoDisabled} onNavigate={onNavigate} />
            <SideLink
              to={`${base}/opportunities`}
              icon={GitPullRequestArrow}
              label="Contributions"
              disabled={repoDisabled}
              onNavigate={onNavigate}
            />
            <SideLink to={`${base}/architecture`} icon={Network} label="Architecture" disabled={repoDisabled} onNavigate={onNavigate} />
            <SideLink to={`${base}/explore`} icon={FolderTree} label="Explorer" disabled={repoDisabled} onNavigate={onNavigate} />
            <SideLink to={`${base}/issues`} icon={AlertOctagon} label="Issues" disabled={repoDisabled} onNavigate={onNavigate} />
          </div>
          <p className="mb-1.5 mt-4 px-2.5 text-xs text-faint">Analysis</p>
          <div className="space-y-0.5">
            <SideLink to={`${base}/metrics`} icon={Gauge} label="Metrics" disabled={repoDisabled} onNavigate={onNavigate} />
            <SideLink to={`${base}/debt`} icon={Boxes} label="Technical Debt" disabled={repoDisabled} onNavigate={onNavigate} />
            <SideLink to={`${base}/review`} icon={Wrench} label="Code Review" disabled={repoDisabled} onNavigate={onNavigate} />
          </div>
        </div>
        <div className="space-y-0.5">
          <SideLink to="/app/settings" icon={SettingsIcon} label="Settings" onNavigate={onNavigate} />
        </div>
      </nav>
      <div className="border-t border-line p-3">
        <div className="flex items-center gap-2.5 px-1">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-raised text-xs font-semibold text-ink"
            aria-hidden
          >
            {(user?.name ?? "?").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user?.name}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
          </div>
          <Button size="sm" variant="ghost" onClick={logout} aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function RepoSelector() {
  const repositories = useRepositories();
  const repoId = useCurrentRepoId();
  const navigate = useNavigate();
  const list = repositories.data ?? [];
  if (list.length === 0) return null;
  return (
    <div className="relative hidden min-w-0 sm:block">
      <FolderGit2 className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" aria-hidden />
      <select
        aria-label="Current repository"
        value={list.some((repo) => repo.id === repoId) ? repoId ?? "" : ""}
        onChange={(event) => {
          const id = event.target.value;
          if (!id) return;
          setCurrentRepoId(id);
          navigate(`/app/r/${id}`);
        }}
        className="h-8 max-w-[260px] truncate rounded border border-line bg-surface pl-8 pr-7 text-sm text-ink focus:outline-none focus-visible:border-accent"
      >
        <option value="" disabled>
          Select repository
        </option>
        {list.map((repo) => (
          <option key={repo.id} value={repo.id}>
            {repo.full_name}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { theme, toggle } = useTheme();
  const location = useLocation();

  useEffect(() => setMobileOpen(false), [location.pathname]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const isMac = useMemo(() => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform), []);

  return (
    <div className="flex h-full">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface lg:block">
        <Sidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-canvas/70" onClick={() => setMobileOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-72 border-r border-line bg-surface" aria-label="Navigation">
            <Button
              size="sm"
              variant="ghost"
              className="absolute right-2 top-3"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
            >
              <X className="h-4 w-4" />
            </Button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-line bg-canvas/90 px-3 backdrop-blur sm:px-5">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <RepoSelector />
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="ml-auto flex h-8 min-w-0 items-center gap-2 rounded border border-line bg-surface px-2.5 text-sm text-faint hover:text-muted sm:w-72"
            aria-label="Search files and pages"
          >
            <Search className="h-4 w-4 shrink-0" aria-hidden />
            <span className="hidden truncate sm:inline">Search files and pages</span>
            <span className="ml-auto hidden sm:inline">
              <Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd> <Kbd>K</Kbd>
            </span>
          </button>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Light theme" : "Dark theme"}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>
        <main id="main" className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6">
            <ErrorBoundary key={location.pathname} inline>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
