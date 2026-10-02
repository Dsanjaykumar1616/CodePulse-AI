import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { Download, ExternalLink, Loader2, RefreshCw, XCircle } from "lucide-react";
import { useAnalyze, useRepository } from "../hooks/queries";
import { repoSections } from "../hooks/currentRepo";
import { api } from "../services/api";
import { Button, Callout, cx, EmptyState, PageLoading } from "../components/ui";
import { FileDrawerHost } from "../components/FileIntelligence";
import { fmtDateTime, timeAgo } from "../lib/format";
import type { Repository } from "../types/api";

export interface RepoOutletContext {
  repository: Repository;
}

function ReportButton({ repository }: { repository: Repository }) {
  const [state, setState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  return (
    <span className="inline-flex flex-col items-end">
      <Button
        size="sm"
        icon={<Download className="h-3.5 w-3.5" />}
        loading={state.loading}
        disabled={!repository.has_results}
        onClick={async () => {
          setState({ loading: true, error: null });
          try {
            await api.downloadReport(repository.id, repository.full_name);
            setState({ loading: false, error: null });
          } catch (error) {
            setState({ loading: false, error: (error as Error).message });
          }
        }}
      >
        Export report
      </Button>
      {state.error && (
        <span className="mt-1 text-xs text-critical" role="alert">
          {state.error}
        </span>
      )}
    </span>
  );
}

export default function RepoLayout() {
  const { repoId } = useParams<"repoId">();
  const repository = useRepository(repoId);
  const analyze = useAnalyze();
  const navigate = useNavigate();

  if (repository.isLoading) return <PageLoading />;
  if (repository.isError || !repository.data) {
    const notFound = (repository.error as { status?: number } | null)?.status === 404;
    return (
      <EmptyState
        title={notFound ? "Repository not found" : "Could not load this repository"}
        action={
          <Link to="/app/repositories">
            <Button>Back to repositories</Button>
          </Link>
        }
      >
        {notFound ? "It may have been deleted, or it belongs to another account." : repository.error?.message}
      </EmptyState>
    );
  }

  const repo = repository.data;
  const job = repo.latest_job;
  const inFlight = repo.status === "queued" || repo.status === "running";

  const startAnalysis = () =>
    analyze.mutate(repo.id, { onSuccess: (created) => navigate(`/app/analysis/${created.id}`) });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <nav aria-label="Breadcrumb" className="text-xs text-muted">
            <Link to="/app/repositories" className="hover:text-ink">
              Repositories
            </Link>
            <span className="mx-1.5 text-faint">/</span>
            <span>{repo.owner}</span>
          </nav>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h1 className="truncate text-xl font-semibold tracking-tight">{repo.name}</h1>
            <a
              href={repo.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink"
            >
              github.com/{repo.full_name}
              <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </div>
          <p className="mt-1 text-xs text-muted">
            {repo.last_analyzed_at ? (
              <span title={fmtDateTime(repo.last_analyzed_at)}>Analyzed {timeAgo(repo.last_analyzed_at)}</span>
            ) : (
              "Not analyzed yet"
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {inFlight && job ? (
            <Link to={`/app/analysis/${job.id}`}>
              <Button size="sm" icon={<Loader2 className="h-3.5 w-3.5 animate-spin" />}>
                Analysis {job.status === "queued" ? "queued" : `${job.progress}%`}
              </Button>
            </Link>
          ) : (
            <Button
              size="sm"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              loading={analyze.isPending}
              onClick={startAnalysis}
            >
              {repo.has_results ? "Re-analyze" : "Analyze"}
            </Button>
          )}
          <ReportButton repository={repo} />
        </div>
      </header>

      {analyze.error && <Callout tone="error">{analyze.error.message}</Callout>}

      {repo.status === "failed" && job && (
        <Callout tone="error" title="The latest analysis failed">
          {job.error_message ?? "The analysis did not finish."}{" "}
          {repo.has_results && "The results below are from the previous successful analysis."}
        </Callout>
      )}

      {repo.has_results ? (
        <>
          <nav aria-label="Repository sections" className="scroll-thin -mx-1 overflow-x-auto border-b border-line">
            <div className="flex gap-1 px-1">
              {repoSections.map((section, index) => (
                <span key={section.path} className="flex items-center">
                  {index > 0 && repoSections[index - 1].group !== section.group && (
                    <span className="mx-2 h-4 w-px bg-line" aria-hidden />
                  )}
                <NavLink
                  to={section.path}
                  end={section.path === ""}
                  className={({ isActive }: { isActive: boolean }) =>
                    cx(
                      "-mb-px whitespace-nowrap border-b-2 px-2.5 py-2 text-sm transition-colors",
                      isActive ? "border-accent font-medium text-ink" : "border-transparent text-muted hover:text-ink",
                    )
                  }
                >
                  {section.label}
                </NavLink>
                </span>
              ))}
            </div>
          </nav>
          <Outlet context={{ repository: repo } satisfies RepoOutletContext} />
          <FileDrawerHost repositoryId={repo.id} />
        </>
      ) : inFlight ? (
        <EmptyState
          icon={<Loader2 className="h-6 w-6 animate-spin" />}
          title="Analysis in progress"
          action={
            job && (
              <Link to={`/app/analysis/${job.id}`}>
                <Button variant="primary">View progress</Button>
              </Link>
            )
          }
        >
          Results appear here as soon as the first analysis finishes.
        </EmptyState>
      ) : (
        <EmptyState
          icon={<XCircle className="h-6 w-6" />}
          title="No analysis results yet"
          action={
            <Button variant="primary" loading={analyze.isPending} onClick={startAnalysis}>
              Analyze repository
            </Button>
          }
        >
          Run an analysis to see health, risk, technical debt, architecture and contribution opportunities.
        </EmptyState>
      )}
    </div>
  );
}
