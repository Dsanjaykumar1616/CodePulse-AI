import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, CircleDot, ExternalLink, Sparkles } from "lucide-react";
import {
  Badge,
  Button,
  Callout,
  EmptyState,
  Explainer,
  InfoTip,
  LevelBadge,
  PageLoading,
  Pagination,
  Panel,
  SearchInput,
  Segmented,
  Select,
} from "../../components/ui";
import { IssueStateBadge } from "../../components/FileIntelligence";
import { useIssues, useTable } from "../../hooks/queries";
import { timeAgo } from "../../lib/format";
import { hasSignal, isStale, sortIssues, suggestedIssues, type IssueSort } from "../../lib/issues";
import type { Issue, IssueDifficulty, IssueSignal, IssueState } from "../../types/api";

const SIGNAL_TEXT: Record<IssueSignal["kind"], string> = {
  beginner: "Beginner label",
  help_wanted: "Help wanted",
  documentation: "Documentation",
};

/** Estimated difficulty with the reasons behind it in a tooltip. */
export function IssueDifficultyBadge({ difficulty }: { difficulty?: IssueDifficulty }) {
  if (!difficulty) return null;
  if (difficulty.status === "UNAVAILABLE" || !difficulty.level) {
    return (
      <span className="inline-flex items-center gap-1">
        <Badge>Difficulty not estimated</Badge>
        <InfoTip label="difficulty not estimated">{difficulty.reason}</InfoTip>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-2xs text-faint">Estimated</span>
      <LevelBadge level={difficulty.level} />
      <InfoTip label="estimated difficulty">
        <span className="block font-medium">Why {difficulty.level.toLowerCase()}?</span>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {difficulty.basis.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {difficulty.reason && <span className="mt-1 block">{difficulty.reason}</span>}
      </InfoTip>
    </span>
  );
}

export function SignalBadges({ signals }: { signals?: IssueSignal[] }) {
  if (!signals?.length) return null;
  return (
    <>
      {signals.map((signal) => (
        <Badge key={signal.label} severity="low" title={`GitHub label: ${signal.label}`}>
          {SIGNAL_TEXT[signal.kind]}
        </Badge>
      ))}
    </>
  );
}

function ActivityLine({ issue }: { issue: Issue }) {
  const stale = isStale(issue);
  return (
    <p className="mt-1.5 text-xs text-faint">
      {issue.author ? `Opened by ${issue.author}` : "Opened"} {timeAgo(issue.created_at)}
      {issue.updated_at && ` · updated ${timeAgo(issue.updated_at)}`}
      {issue.comments !== null && issue.comments !== undefined && ` · ${issue.comments} ${issue.comments === 1 ? "comment" : "comments"}`}
      {stale && (
        <span className="ml-1.5 text-medium">· No activity for over a year. Ask on the issue whether it is still wanted.</span>
      )}
    </p>
  );
}

function workLink(repoId: string, issue: Issue) {
  return `/app/r/${repoId}/issues/${issue.number}`;
}

function SuggestedIssues({ repoId, issues }: { repoId: string; issues: Issue[] }) {
  const picks = useMemo(() => suggestedIssues(issues, 3), [issues]);
  if (picks.length === 0) {
    return (
      <Callout title="No obvious beginner issue right now">
        No open issue has a beginner label (such as “good first issue”) or an estimated Beginner difficulty. You can
        still pick any open issue below, or start from a file on the Contribute page.
      </Callout>
    );
  }
  return (
    <section className="rounded-md border-2 border-accent/40 bg-surface p-5" aria-labelledby="suggested-heading">
      <h2 id="suggested-heading" className="flex items-center gap-2 text-base font-semibold">
        <Sparkles className="h-4 w-4 text-accent" aria-hidden /> Good issues to start with
      </h2>
      <p className="mt-0.5 text-sm text-muted">Open issues that look friendliest for a new contributor, and why.</p>
      <ul className="mt-3 grid gap-3 lg:grid-cols-3">
        {picks.map(({ issue, reasons }) => (
          <li key={issue.number} className="flex flex-col rounded border border-line bg-canvas p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <IssueDifficultyBadge difficulty={issue.difficulty} />
            </div>
            <p className="mt-2 text-sm font-medium text-ink">
              <span className="tabular text-muted">#{issue.number}</span> {issue.title}
            </p>
            <ul className="mt-2 flex-1 space-y-0.5 text-xs text-muted">
              {reasons.map((reason) => (
                <li key={reason}>✓ {reason}</li>
              ))}
            </ul>
            <Link to={workLink(repoId, issue)} className="mt-3">
              <Button size="sm" variant="primary" className="w-full">
                Work on this issue <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Button>
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-3">
      <Explainer title="How are these picked?">
        Only open issues. Points for: a beginner label such as “good first issue” (+3), “help wanted” (+1), a
        documentation label (+1), estimated Beginner (+2) or Intermediate (+1) difficulty, and activity in the last month
        (+1). Points off for estimated Advanced (−1) and no activity for over a year (−2). Labels are detected from
        GitHub; difficulty is estimated by CodePulse.
      </Explainer>
      </div>
    </section>
  );
}

type LevelFilter = "any" | "BEGINNER" | "INTERMEDIATE" | "ADVANCED" | "none";
type LabelFilter = "any" | "beginner" | "help_wanted" | "documentation";

export default function IssuesPage() {
  const { repoId } = useParams<"repoId">();
  const issues = useIssues(repoId);
  const [state, setState] = useState<"all" | IssueState>("OPEN");
  const [level, setLevel] = useState<LevelFilter>("any");
  const [label, setLabel] = useState<LabelFilter>("any");
  const [sort, setSort] = useState<IssueSort>("beginner");

  const all = issues.data?.issues;
  const rows = useMemo(() => sortIssues(all ?? [], sort), [all, sort]);
  const filter = useMemo(
    () => (issue: Issue) => {
      if (state !== "all" && issue.state !== state) return false;
      if (level === "none" && issue.difficulty?.level) return false;
      if (level !== "any" && level !== "none" && issue.difficulty?.level !== level) return false;
      if (label !== "any" && !hasSignal(issue, label)) return false;
      return true;
    },
    [state, level, label],
  );
  const table = useTable(rows, {
    search: (issue, text) =>
      issue.title.toLowerCase().includes(text) ||
      String(issue.number).includes(text) ||
      issue.labels.some((item) => item.toLowerCase().includes(text)),
    filter,
    pageSize: 20,
  });

  if (issues.isLoading) return <PageLoading />;
  if (issues.isError || !issues.data) return <EmptyState title="Issues not available">{issues.error?.message}</EmptyState>;
  const data = issues.data;
  if (!data.available) {
    return (
      <EmptyState icon={<CircleDot className="h-6 w-6" />} title="GitHub issues not available">
        {data.reason} Re-analyze later, or set GITHUB_TOKEN on the server to raise the GitHub API limit.
      </EmptyState>
    );
  }
  const counts = data.counts ?? { OPEN: 0, CLOSED: 0, UNKNOWN: 0 };
  const open = data.issues.filter((issue) => issue.state === "OPEN");
  const enriched = data.issues.some((issue) => issue.difficulty);
  const resetPage = table.resetPage;

  return (
    <div className="space-y-6">
      <Explainer title="How to use this page">
        <ol className="list-decimal space-y-1 pl-5">
          <li>Pick an open issue. The suggestions at the top are the friendliest ones for a newcomer.</li>
          <li>Click “Work on this issue” to see which files are probably involved, what could break, and a step-by-step plan.</li>
          <li>Comment on the issue on GitHub before you start, so maintainers know you are working on it.</li>
        </ol>
      </Explainer>

      {enriched ? (
        <SuggestedIssues repoId={repoId!} issues={open} />
      ) : (
        <Callout title="Restart the backend for issue suggestions">
          Suggestions and difficulty estimates come from the latest server version. Restart the backend and refresh this page.
        </Callout>
      )}

      <Panel
        title="All repository issues"
        description={data.difficulty_note}
        actions={<SearchInput value={table.query} onChange={table.setQuery} label="Search issues" placeholder="Search title, number or label" className="w-64" />}
        bodyClassName="p-0"
      >
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
          <Segmented
            label="Issue state"
            value={state}
            onChange={(value) => {
              setState(value);
              resetPage();
            }}
            options={[
              { value: "OPEN", label: "Open", count: counts.OPEN },
              { value: "CLOSED", label: "Closed", count: counts.CLOSED },
              ...(counts.UNKNOWN ? [{ value: "UNKNOWN" as const, label: "Unknown", count: counts.UNKNOWN }] : []),
              { value: "all", label: "All", count: data.issues.length },
            ]}
          />
          <Select
            label="Estimated difficulty"
            value={level}
            onChange={(event) => {
              setLevel(event.target.value as LevelFilter);
              resetPage();
            }}
            className="h-8 text-xs"
          >
            <option value="any">Any difficulty</option>
            <option value="BEGINNER">Beginner</option>
            <option value="INTERMEDIATE">Intermediate</option>
            <option value="ADVANCED">Advanced</option>
            <option value="none">Not estimated</option>
          </Select>
          <Select
            label="Label"
            value={label}
            onChange={(event) => {
              setLabel(event.target.value as LabelFilter);
              resetPage();
            }}
            className="h-8 text-xs"
          >
            <option value="any">Any label</option>
            <option value="beginner">Beginner labels (good first issue…)</option>
            <option value="help_wanted">Help wanted</option>
            <option value="documentation">Documentation</option>
          </Select>
          <Select
            label="Sort issues"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as IssueSort);
              resetPage();
            }}
            className="h-8 text-xs"
          >
            <option value="beginner">Best for beginners first</option>
            <option value="updated">Recently updated</option>
            <option value="newest">Newest</option>
          </Select>
        </div>
        {table.total === 0 ? (
          <EmptyState title={data.issues.length === 0 ? "No issues" : "No issues match"}>
            {data.issues.length === 0 ? "GitHub returned no issues for this repository." : "Try a different filter or search."}
          </EmptyState>
        ) : (
          <ul>
            {table.rows.map((issue) => (
              <li key={issue.number} className="border-b border-line px-4 py-3.5 last:border-0">
                <div className="flex flex-wrap items-center gap-2">
                  <IssueStateBadge state={issue.state} />
                  <IssueDifficultyBadge difficulty={issue.difficulty} />
                  <SignalBadges signals={issue.signals} />
                  {issue.labels
                    .filter((item) => !(issue.signals ?? []).some((signal) => signal.label === item))
                    .map((item) => (
                      <Badge key={item}>{item}</Badge>
                    ))}
                </div>
                <div className="mt-1.5 flex items-start gap-2">
                  <Link to={workLink(repoId!, issue)} className="font-medium text-ink hover:underline">
                    <span className="tabular text-muted">#{issue.number}</span> {issue.title}
                  </Link>
                  {issue.url && (
                    <a href={issue.url} target="_blank" rel="noreferrer" className="mt-1 text-faint hover:text-ink" aria-label={`Open issue #${issue.number} on GitHub`}>
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </a>
                  )}
                </div>
                {issue.description && <p className="mt-1 max-w-3xl text-sm text-muted">{issue.description}</p>}
                <ActivityLine issue={issue} />
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <Link to={workLink(repoId!, issue)}>
                    <Button size="sm" variant={issue.state === "OPEN" ? "secondary" : "ghost"}>
                      {issue.state === "OPEN" ? "Work on this issue" : "See details"} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                    </Button>
                  </Link>
                  <span className="text-xs text-faint">
                    {(issue.match_count ?? issue.related_files.length) > 0
                      ? `${issue.match_count ?? issue.related_files.length} potentially related ${(issue.match_count ?? issue.related_files.length) === 1 ? "file" : "files"}`
                      : "No analyzed file is mentioned in this issue"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="px-4 pb-3">
          <Pagination page={table.page} pageCount={table.pageCount} total={table.total} pageSize={table.pageSize} onPage={table.setPage} />
        </div>
      </Panel>

      <p className="text-xs text-faint">
        Open issues may be contribution opportunities; closed issues are shown for context only. {data.note}
      </p>
    </div>
  );
}
