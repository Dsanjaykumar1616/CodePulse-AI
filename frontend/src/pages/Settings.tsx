import { Moon, Sun } from "lucide-react";
import { Button, Panel } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { fmtDate } from "../lib/format";

export default function Settings() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>

      <Panel title="Account">
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Name</dt>
            <dd>{user?.name}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Email</dt>
            <dd>{user?.email}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Member since</dt>
            <dd>{fmtDate(user?.created_at)}</dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Appearance">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted">Theme: {theme === "dark" ? "Dark" : "Light"}</p>
          <Button size="sm" onClick={toggle} icon={theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}>
            Use {theme === "dark" ? "light" : "dark"} theme
          </Button>
        </div>
      </Panel>

      <Panel title="About the analysis">
        <ul className="list-disc space-y-1.5 pl-4 text-sm text-muted">
          <li>Only public GitHub repositories can be analyzed.</li>
          <li>
            The historical risk signal comes from a model trained on each repository's own bug-fix commits. It describes past
            activity and is not a guarantee about future defects.
          </li>
          <li>GitHub issue data uses the public GitHub API, which limits unauthenticated requests to 60 per hour.</li>
        </ul>
      </Panel>

      <Panel title="Session">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted">Sign out of CodePulse on this device.</p>
          <Button size="sm" variant="danger" onClick={logout}>
            Sign out
          </Button>
        </div>
      </Panel>
    </div>
  );
}
