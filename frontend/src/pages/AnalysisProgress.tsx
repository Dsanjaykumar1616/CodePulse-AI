import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, Check, Circle, Loader2, MinusCircle, RefreshCw, XCircle } from "lucide-react";
import { useAnalyze, useInvalidateResults, useJob, useRepository } from "../hooks/queries";
import { Button, Callout, cx, EmptyState, PageLoading, Progress } from "../components/ui";
import { fmtDuration } from "../lib/format";
import type { Stage } from "../types/api";

const ERROR_HINTS: Record<string, string> = {
  repository_not_found: "Check the URL. CodePulse can only analyze public GitHub repositories.",
  private_repository: "Private repositories are not supported.",
  network_error: "The server could not reach GitHub. Check its internet connection and try again.",
  clone_failed: "Git could not download the repository. Try again; if it keeps failing, the repository may be too large or unavailable.",
  no_source_files: "This repository has no files in the supported languages.",
  dataset_unavailable: "There was not enough code and history to build the analysis dataset.",
  engine_unavailable: "The analysis engine's Python dependencies are missing on the server.",
  interrupted: "The server restarted during the analysis.",
  database_error: "The results could not be saved. Check the database connection.",
};

function StageIcon({ status }: { status: Stage["status"] }) {
  switch (status) {
    case "done":
      return (
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-low text-white">
          <Check className="h-3 w-3" strokeWidth={3} aria-hidden />
        </span>
      );
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-accent" aria-hidden />;
    case "skipped":
      return <MinusCircle className="h-5 w-5 text-medium" aria-hidden />;
    case "failed":
      return <XCircle className="h-5 w-5 text-critical" aria-hidden />;
    default:
      return <Circle className="h-5 w-5 text-line" aria-hidden />;
  }
}

const STATUS_TEXT: Record<Stage["status"], string> = {
  done: "Done",
  running: "In progress",
  skipped: "Skipped",
  failed: "Failed",
  pending: "Waiting",
};

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

export default function AnalysisProgress() {
  const { jobId } = useParams<"jobId">();
  const job = useJob(jobId);
  const repository = useRepository(job.data?.repository_id);
  const analyze = useAnalyze();
  const invalidate = useInvalidateResults();
  const navigate = useNavigate();
  const status = job.data?.status;
  const now = useNow(status === "running" || status === "queued");
  const handledCompletion = useRef(false);

  useEffect(() => {
    if (status === "completed" && job.data && !handledCompletion.current) {
      handledCompletion.current = true;
      invalidate(job.data.repository_id);
    }
  }, [status, job.data, invalidate]);

  if (job.isLoading) return <PageLoading />;
  if (job.isError || !job.data) {
    return (
      <EmptyState
        title="Analysis not found"
        action={
          <Link to="/app/repositories">
            <Button>Back to repositories</Button>
          </Link>
        }
      >
        {job.error?.message}
      </EmptyState>
    );
  }

  const data = job.data;
  const repo = repository.data;
  const started = data.started_at ? new Date(data.started_at).getTime() : null;
  const finished = data.finished_at ? new Date(data.finished_at).getTime() : null;
  const elapsed = started ? (finished ?? now) - started : null;
  const done = data.stages.filter((stage) => stage.status === "done" || stage.status === "skipped").length;
  const current = data.stages.find((stage) => stage.status === "running");

  const retry = () =>
    analyze.mutate(data.repository_id, {
      onSuccess: (created) => {
        handledCompletion.current = false;
        navigate(`/app/analysis/${created.id}`);
      },
    });

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <p className="text-xs text-muted">
          <Link to="/app/repositories" className="hover:text-ink">
            Repositories
          </Link>
          <span className="mx-1.5 text-faint">/</span>
          {repo?.full_name ?? "Repository"}
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">
          {data.status === "completed"
            ? "Analysis complete"
            : data.status === "failed"
              ? "Analysis failed"
              : data.status === "queued"
                ? "Waiting to start"
                : "Analyzing repository"}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {data.status === "queued"
            ? data.queue_position && data.queue_position > 1
              ? `Analyses run one at a time. ${data.queue_position - 1} ahead of this one.`
              : "Starting shortly."
            : current
              ? `${current.label}${current.message ? ` · ${current.message}` : ""}`
              : `${done} of ${data.stages.length} stages finished`}
          {elapsed !== null && <span className="tabular"> · {fmtDuration(elapsed)} elapsed</span>}
        </p>
      </div>

      <Progress
        value={data.status === "completed" ? 100 : data.progress}
        severity={data.status === "failed" ? "critical" : data.status === "completed" ? "low" : undefined}
        label="Analysis progress"
      />

      {data.status === "failed" && (
        <Callout tone="error" title={data.error_message ?? "The analysis failed."}>
          {data.error_code && ERROR_HINTS[data.error_code] && <p className="mt-1">{ERROR_HINTS[data.error_code]}</p>}
          <div className="mt-3 flex gap-2">
            <Button size="sm" icon={<RefreshCw className="h-3.5 w-3.5" />} loading={analyze.isPending} onClick={retry}>
              Try again
            </Button>
            <Link to="/app">
              <Button size="sm" variant="ghost">
                Analyze a different repository
              </Button>
            </Link>
          </div>
        </Callout>
      )}
      {analyze.error && <Callout tone="error">{analyze.error.message}</Callout>}

      <ol className="panel divide-y divide-line" aria-label="Analysis stages" aria-live="polite">
        {data.stages.map((stage) => {
          const duration =
            stage.started_at && stage.finished_at
              ? new Date(stage.finished_at).getTime() - new Date(stage.started_at).getTime()
              : stage.started_at && stage.status === "running"
                ? now - new Date(stage.started_at).getTime()
                : null;
          return (
            <li key={stage.key} className="flex items-start gap-3 px-4 py-3">
              <div className="pt-px">
                <StageIcon status={stage.status} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className={cx(
                      "text-sm",
                      stage.status === "pending" ? "text-faint" : "text-ink",
                      stage.status === "running" && "font-medium",
                    )}
                  >
                    {stage.label}
                  </span>
                  <span className="tabular shrink-0 text-xs text-faint">
                    <span className="sr-only">{STATUS_TEXT[stage.status]}. </span>
                    {duration !== null && duration >= 0 ? fmtDuration(duration) : ""}
                  </span>
                </div>
                {stage.message && stage.status !== "running" && (
                  <p className={cx("mt-0.5 text-xs", stage.status === "done" ? "text-muted" : "text-medium")}>{stage.message}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {data.warnings.length > 0 && data.status === "completed" && (
        <Callout tone="warning" title="Completed with notes">
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Callout>
      )}

      {data.status === "completed" && (
        <div className="flex gap-2">
          <Link to={`/app/r/${data.repository_id}`}>
            <Button variant="primary">Open repository dashboard</Button>
          </Link>
          <Link to={`/app/r/${data.repository_id}/opportunities`}>
            <Button>See contribution opportunities</Button>
          </Link>
        </div>
      )}

      {(data.status === "running" || data.status === "queued") && (
        <p className="flex items-center gap-2 text-xs text-faint">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
          You can leave this page. The analysis keeps running and its status is shown on the Repositories page.
        </p>
      )}
    </div>
  );
}
