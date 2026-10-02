import { Link } from "react-router-dom";
import { FolderGit2 } from "lucide-react";
import { AnalyzeForm } from "../components/AnalyzeForm";
import { HelpActions } from "../components/HelpActions";
import { getCurrentRepoId } from "../hooks/currentRepo";
import { RepoLink, ScoreCell, StatusBadge } from "../components/RepoBits";
import { Button, Callout, EmptyState, Panel, Skeleton } from "../components/ui";
import { useRepositories } from "../hooks/queries";
import { useAuth } from "../lib/auth";
import { timeAgo } from "../lib/format";

export default function Dashboard() {
  const { user } = useAuth();
  const repositories = useRepositories();
  const list = repositories.data ?? [];
  const recent = [...list]
    .sort((a, b) => (b.last_analyzed_at ?? b.created_at).localeCompare(a.last_analyzed_at ?? a.created_at))
    .slice(0, 6);
  const active = list.filter((repo) => repo.status === "queued" || repo.status === "running");
  const analyzed = list.filter((repo) => repo.has_results);
  const focus =
    analyzed.find((repo) => repo.id === getCurrentRepoId()) ??
    [...analyzed].sort((a, b) => (b.last_analyzed_at ?? "").localeCompare(a.last_analyzed_at ?? ""))[0] ??
    null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          {user ? `Hello, ${user.name.split(" ")[0]}` : "Overview"}
        </h1>
        <p className="mt-1 text-sm text-muted">Analyze a repository, or pick up where you left off.</p>
      </div>

      <section className="panel p-5 sm:p-6" aria-labelledby="analyze-heading">
        <h2 id="analyze-heading" className="text-base font-semibold">
          Analyze a Repository
        </h2>
        <p className="mb-4 mt-1 text-sm text-muted">
          Paste a public GitHub repository URL. Analysis runs in the background and usually takes from under a minute to a
          few minutes, depending on repository size and history.
        </p>
        <AnalyzeForm autoFocus />
      </section>

      <section className="space-y-3" aria-labelledby="help-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="help-heading" className="text-base font-semibold">
            How can CodePulse help you?
          </h2>
          {focus ? (
            <p className="text-sm text-muted">
              For <span className="font-mono text-[13px] text-ink">{focus.full_name}</span>
              {analyzed.length > 1 && (
                <>
                  {" "}
                  ·{" "}
                  <Link to="/app/repositories" className="text-accent hover:underline">
                    switch repository
                  </Link>
                </>
              )}
            </p>
          ) : (
            <p className="text-sm text-muted">Analyze a repository above to enable these.</p>
          )}
        </div>
        <HelpActions repoId={focus?.id ?? null} compact />
      </section>

      {active.length > 0 && (
        <Callout title="Analysis in progress">
          {active.map((repo) => (
            <span key={repo.id} className="mr-3 inline-block">
              <Link to={repo.latest_job ? `/app/analysis/${repo.latest_job.id}` : `/app/r/${repo.id}`} className="text-accent hover:underline">
                {repo.full_name}
              </Link>{" "}
              ({repo.status === "queued" ? "queued" : `${repo.latest_job?.progress ?? 0}%`})
            </span>
          ))}
        </Callout>
      )}

      <Panel
        title="Recent repositories"
        actions={
          list.length > 0 && (
            <Link to="/app/repositories">
              <Button size="sm" variant="ghost">
                View all
              </Button>
            </Link>
          )
        }
        bodyClassName="p-0"
      >
        {repositories.isLoading ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : repositories.isError ? (
          <div className="p-4">
            <Callout tone="error">{repositories.error?.message}</Callout>
          </div>
        ) : recent.length === 0 ? (
          <EmptyState icon={<FolderGit2 className="h-6 w-6" />} title="No repositories yet">
            Your analyzed repositories will appear here. Try https://github.com/psf/requests to get started.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {recent.map((repo) => (
              <li key={repo.id} className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <RepoLink repository={repo} />
                  <p className="text-xs text-muted">
                    {repo.last_analyzed_at ? `Analyzed ${timeAgo(repo.last_analyzed_at)}` : `Added ${timeAgo(repo.created_at)}`}
                  </p>
                </div>
                <dl className="flex items-center gap-6 text-sm">
                  <div className="text-right">
                    <dt className="text-2xs text-faint">Health</dt>
                    <dd>
                      <ScoreCell value={repo.health_score} kind="health" />
                    </dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-2xs text-faint">Debt</dt>
                    <dd>
                      <ScoreCell value={repo.debt_score} kind="debt" />
                    </dd>
                  </div>
                </dl>
                <StatusBadge repository={repo} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
