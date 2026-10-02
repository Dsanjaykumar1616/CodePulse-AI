import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ExternalLink, FolderGit2, RefreshCw, Trash2 } from "lucide-react";
import { AnalyzeForm } from "../components/AnalyzeForm";
import { RepoLink, ScoreCell, StatusBadge } from "../components/RepoBits";
import { Button, Callout, EmptyState, Modal, Panel, SearchInput, Skeleton } from "../components/ui";
import { cellClass, rowClass, TableShell, Th, theadClass } from "../components/data";
import { useAnalyze, useDeleteRepository, useRepositories } from "../hooks/queries";
import { getCurrentRepoId, setCurrentRepoId } from "../hooks/currentRepo";
import { fmtDateTime, timeAgo } from "../lib/format";
import type { Repository } from "../types/api";

export default function Repositories() {
  const repositories = useRepositories();
  const analyze = useAnalyze();
  const remove = useDeleteRepository();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Repository | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const list = (repositories.data ?? []).filter((repo) =>
    repo.full_name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  const reanalyze = (repo: Repository) => {
    setActionError(null);
    analyze.mutate(repo.id, {
      onSuccess: (job) => navigate(`/app/analysis/${job.id}`),
      onError: (error) => setActionError(error.message),
    });
  };

  const confirmDelete = () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    remove.mutate(target.id, {
      onSuccess: () => {
        if (getCurrentRepoId() === target.id) setCurrentRepoId(null);
        setPendingDelete(null);
      },
      onError: (error) => {
        setActionError(error.message);
        setPendingDelete(null);
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Repositories</h1>
        <p className="mt-1 text-sm text-muted">Repositories you have added. Results are kept so you can come back later.</p>
      </div>

      <section className="panel p-5" aria-label="Add a repository">
        <AnalyzeForm />
      </section>

      {actionError && <Callout tone="error">{actionError}</Callout>}

      <Panel
        title="Your repositories"
        description={repositories.data ? `${repositories.data.length} total` : undefined}
        actions={<SearchInput value={query} onChange={setQuery} label="Filter repositories" placeholder="Filter" className="w-56" />}
      >
        {repositories.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : repositories.isError ? (
          <Callout tone="error">{repositories.error?.message}</Callout>
        ) : list.length === 0 ? (
          <EmptyState icon={<FolderGit2 className="h-6 w-6" />} title={query ? "No matches" : "No repositories yet"}>
            {query ? "No repository name matches that filter." : "Add a GitHub repository above to run your first analysis."}
          </EmptyState>
        ) : (
          <TableShell label="Repositories">
            <thead className={theadClass}>
              <tr>
                <Th>Repository</Th>
                <Th>Last analyzed</Th>
                <Th align="right">Health</Th>
                <Th align="right">Debt</Th>
                <Th align="right">Risk signal</Th>
                <Th>Status</Th>
                <Th align="right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((repo) => {
                const busy = repo.status === "queued" || repo.status === "running";
                return (
                  <tr key={repo.id} className={rowClass}>
                    <td className={cellClass}>
                      <div className="flex items-center gap-2">
                        <RepoLink repository={repo} />
                        <a href={repo.url} target="_blank" rel="noreferrer" aria-label={`${repo.full_name} on GitHub`}>
                          <ExternalLink className="h-3.5 w-3.5 text-faint hover:text-ink" />
                        </a>
                      </div>
                    </td>
                    <td className={cellClass}>
                      <span className="text-muted" title={fmtDateTime(repo.last_analyzed_at)}>
                        {timeAgo(repo.last_analyzed_at)}
                      </span>
                    </td>
                    <td className={`${cellClass} text-right`}>
                      <ScoreCell value={repo.health_score} kind="health" />
                    </td>
                    <td className={`${cellClass} text-right`}>
                      <ScoreCell value={repo.debt_score} kind="debt" />
                    </td>
                    <td className={`${cellClass} text-right`}>
                      <ScoreCell value={repo.risk_signal} kind="risk" />
                    </td>
                    <td className={cellClass}>
                      <StatusBadge repository={repo} />
                    </td>
                    <td className={`${cellClass} text-right`}>
                      <div className="flex justify-end gap-1">
                        {repo.has_results && (
                          <Link to={`/app/r/${repo.id}`}>
                            <Button size="sm">Open</Button>
                          </Link>
                        )}
                        {busy && repo.latest_job ? (
                          <Link to={`/app/analysis/${repo.latest_job.id}`}>
                            <Button size="sm">Progress</Button>
                          </Link>
                        ) : (
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<RefreshCw className="h-3.5 w-3.5" />}
                            loading={analyze.isPending && analyze.variables === repo.id}
                            onClick={() => reanalyze(repo)}
                          >
                            {repo.has_results ? "Re-analyze" : "Analyze"}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Delete ${repo.full_name}`}
                          onClick={() => setPendingDelete(repo)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableShell>
        )}
      </Panel>

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title="Delete repository"
        footer={
          <>
            <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
            <Button variant="danger" loading={remove.isPending} onClick={confirmDelete}>
              Delete
            </Button>
          </>
        }
      >
        Delete <span className="font-medium text-ink">{pendingDelete?.full_name}</span> and all of its analysis results from
        CodePulse? This cannot be undone. The repository on GitHub is not affected.
      </Modal>
    </div>
  );
}
