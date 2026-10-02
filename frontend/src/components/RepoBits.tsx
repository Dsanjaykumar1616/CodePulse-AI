import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Clock, Loader2 } from "lucide-react";
import { Badge, cx } from "./ui";
import type { Repository } from "../types/api";
import { fmtNumber, scoreSeverity, debtSeverity, riskSeverity, severityText } from "../lib/format";

export function StatusBadge({ repository }: { repository: Repository }) {
  const job = repository.latest_job;
  switch (repository.status) {
    case "queued":
      return (
        <Badge>
          <Clock className="h-3 w-3" aria-hidden /> Queued
        </Badge>
      );
    case "running":
      return (
        <Badge severity="medium">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> Analyzing {job ? `${job.progress}%` : ""}
        </Badge>
      );
    case "failed":
      return (
        <Badge severity="critical" title={job?.error_message ?? undefined}>
          <AlertTriangle className="h-3 w-3" aria-hidden /> Failed
        </Badge>
      );
    case "completed":
      return (
        <Badge severity="low">
          <CheckCircle2 className="h-3 w-3" aria-hidden /> Analyzed
        </Badge>
      );
    default:
      return <Badge>Not analyzed</Badge>;
  }
}

export function ScoreCell({ value, kind }: { value: number | null; kind: "health" | "debt" | "risk" }): ReactNode {
  if (value === null || value === undefined) return <span className="text-faint">—</span>;
  const severity =
    kind === "health" ? scoreSeverity(value) : kind === "debt" ? debtSeverity(value) : riskSeverity(value);
  return (
    <span className={cx("tabular font-medium", severityText[severity])}>
      {fmtNumber(value, kind === "risk" ? 1 : 0)}
      {kind === "risk" && "%"}
    </span>
  );
}

export function RepoLink({ repository }: { repository: Repository }) {
  const target = repository.has_results
    ? `/app/r/${repository.id}`
    : repository.latest_job && (repository.status === "queued" || repository.status === "running")
      ? `/app/analysis/${repository.latest_job.id}`
      : `/app/r/${repository.id}`;
  return (
    <Link to={target} className="min-w-0 font-medium text-ink hover:underline">
      <span className="text-muted">{repository.owner}/</span>
      {repository.name}
    </Link>
  );
}
