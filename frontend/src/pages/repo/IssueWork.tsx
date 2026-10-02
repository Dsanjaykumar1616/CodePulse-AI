import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, FileSearch, ListChecks, Search, Target } from "lucide-react";
import { Badge, Button, Callout, EmptyState, InfoTip, LevelBadge, PageLoading, Panel, cx } from "../../components/ui";
import { FileLink, useOpenFile } from "../../components/FilePath";
import { IssueStateBadge } from "../../components/FileIntelligence";
import { githubFileUrl } from "../../components/Guidance";
import { useIssueWork, useRepository } from "../../hooks/queries";
import { timeAgo } from "../../lib/format";
import { isStale } from "../../lib/issues";
import type { IssueDifficulty, IssueWorkFile, IssueWorkStep } from "../../types/api";
import { SignalBadges } from "./Issues";

function DifficultyCard({ difficulty }: { difficulty: IssueDifficulty }) {
  return (
    <Panel title="How hard is this?" description="Estimated by CodePulse from the related files.">
      {difficulty.status === "UNAVAILABLE" || !difficulty.level ? (
        <>
          <Badge>Not estimated</Badge>
          <p className="mt-2 text-sm text-muted">{difficulty.reason}</p>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <span className="text-xs text-faint">Estimated</span>
            <LevelBadge level={difficulty.level} />
          </div>
          <ul className="mt-3 space-y-1.5 text-sm text-muted">
            {difficulty.basis.map((line) => (
              <li key={line} className={cx(line.endsWith(":") ? "font-medium text-ink" : "pl-3")}>
                {line}
              </li>
            ))}
          </ul>
          {difficulty.reason && <p className="mt-3 text-xs text-medium">{difficulty.reason}</p>}
          <p className="mt-3 text-xs text-faint">
            Rule: start from the hardest file's difficulty, then go up one level if a file has High or Critical risk, is
            used by many files, or the issue touches three or more files.
          </p>
        </>
      )}
    </Panel>
  );
}

function PlanStep({
  step,
  index,
  done,
  onToggle,
  search,
}: {
  step: IssueWorkStep;
  index: number;
  done: boolean;
  onToggle: () => void;
  search: { terms: string[]; url: string } | null;
}) {
  return (
    <li className="flex gap-3 border-b border-line py-3 last:border-0">
      <input
        type="checkbox"
        checked={done}
        onChange={onToggle}
        aria-label={`Mark step ${index + 1} as done`}
        className="mt-1 h-4 w-4 shrink-0 accent-accent"
      />
      <div className="min-w-0 flex-1">
        <p className={cx("text-sm font-medium", done ? "text-faint line-through" : "text-ink")}>
          <span className="tabular mr-1.5 text-faint">{index + 1}.</span>
          {step.title}
        </p>
        <p className="mt-0.5 text-sm text-muted">{step.detail}</p>
        {step.files.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {step.files.map((file) => (
              <li key={file} className="max-w-full">
                <FileLink path={file} />
              </li>
            ))}
          </ul>
        )}
        {step.key === "find_code" && search && (
          <a href={search.url} target="_blank" rel="noreferrer" className="mt-2 inline-block">
            <Button size="sm" icon={<Search className="h-3.5 w-3.5" />}>
              Search the code on GitHub
            </Button>
          </a>
        )}
      </div>
    </li>
  );
}

function testsText(file: IssueWorkFile) {
  const tests = file.tests;
  const found = tests.detected.length + tests.heuristic.length;
  if (!tests.available) return { status: "unavailable" as const, text: "Unavailable: no test files in the analysis" };
  if (tests.detected.length) return { status: "ok" as const, text: `${found} related ${found === 1 ? "test" : "tests"} (detected)` };
  if (tests.heuristic.length) return { status: "ok" as const, text: `${found} related ${found === 1 ? "test" : "tests"} (matched by name)` };
  return { status: "missing" as const, text: "No related test found" };
}

function RelatedFileCard({ file, repoUrl }: { file: IssueWorkFile; repoUrl: string | undefined }) {
  const { open } = useOpenFile();
  const github = githubFileUrl(repoUrl, file.file);
  const tests = testsText(file);
  return (
    <li className="rounded border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge severity={file.primary ? "medium" : "none"}>{file.primary ? "Most likely" : "Possibly related"}</Badge>
        {file.difficulty && <LevelBadge level={file.difficulty} />}
        {file.roles
          .filter((role) => role !== "Isolated")
          .map((role) => (
            <Badge key={role}>{role}</Badge>
          ))}
      </div>
      <div className="mt-2">
        <FileLink path={file.file} className="!text-[13.5px] font-medium" />
      </div>
      <p className="mt-1 text-xs text-muted">
        <span className="font-medium text-ink">Why it matched: </span>
        {file.evidence.join("; ") || "Mentioned in the issue text"}
      </p>
      <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
        <div>
          <dt className="text-faint">Risk</dt>
          <dd>
            <LevelBadge level={file.risk_level} />
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-faint">
            Used by <InfoTip label="used by">Files that import this file. A change here can affect them.</InfoTip>
          </dt>
          <dd className="tabular text-ink">{file.connectivity === null ? "Not available" : `${file.used_by.length} files`}</dd>
        </div>
        <div>
          <dt className="text-faint">Depends on</dt>
          <dd className="tabular text-ink">{file.connectivity === null ? "Not available" : `${file.depends_on.length} files`}</dd>
        </div>
        <div>
          <dt className="text-faint">Tests</dt>
          <dd className={tests.status === "ok" ? "text-low" : tests.status === "missing" ? "text-medium" : "text-faint"}>{tests.text}</dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" icon={<FileSearch className="h-3.5 w-3.5" />} onClick={() => open(file.file, "before")}>
          Before you modify
        </Button>
        <Button size="sm" variant="ghost" onClick={() => open(file.file, "impact")}>
          What could break
        </Button>
        {github && (
          <a href={github} target="_blank" rel="noreferrer">
            <Button size="sm" variant="ghost">
              Open on GitHub <ExternalLink className="h-3 w-3" aria-hidden />
            </Button>
          </a>
        )}
      </div>
    </li>
  );
}

export default function IssueWorkPage() {
  const { repoId, issueNumber } = useParams<"repoId" | "issueNumber">();
  const number = Number(issueNumber);
  const valid = Number.isInteger(number) && number > 0;
  const work = useIssueWork(repoId, valid ? number : null);
  const repo = useRepository(repoId);
  const [done, setDone] = useState<Record<string, boolean>>({});

  const back = (
    <Link to={`/app/r/${repoId}/issues`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
      <ArrowLeft className="h-4 w-4" aria-hidden /> All issues
    </Link>
  );

  if (!valid) return <EmptyState title="Issue not found" action={back}>That is not a valid issue number.</EmptyState>;
  if (work.isLoading) return <PageLoading />;
  if (work.isError || !work.data) {
    return (
      <EmptyState title="Issue not available" action={back}>
        {work.error?.message}
      </EmptyState>
    );
  }
  const data = work.data;
  const issue = data.issue;
  const doneCount = data.steps.filter((step) => done[step.key]).length;

  return (
    <div className="space-y-5">
      {back}

      <header className="panel p-5">
        <div className="flex flex-wrap items-center gap-2">
          <IssueStateBadge state={issue.state} />
          <SignalBadges signals={issue.signals} />
          {issue.labels
            .filter((label) => !issue.signals.some((signal) => signal.label === label))
            .map((label) => (
              <Badge key={label}>{label}</Badge>
            ))}
        </div>
        <h1 className="mt-2 text-xl font-semibold">
          <span className="tabular text-muted">#{issue.number}</span> {issue.title}
        </h1>
        <p className="mt-1 text-xs text-faint">
          {issue.author ? `Opened by ${issue.author}` : "Opened"} {timeAgo(issue.created_at)}
          {issue.updated_at && ` · updated ${timeAgo(issue.updated_at)}`}
          {issue.comments !== null && issue.comments !== undefined && ` · ${issue.comments} ${issue.comments === 1 ? "comment" : "comments"}`}
        </p>
        {issue.description && <p className="mt-3 max-w-3xl text-sm text-muted">{issue.description}</p>}
        {issue.url && (
          <a href={issue.url} target="_blank" rel="noreferrer" className="mt-3 inline-block">
            <Button size="sm" icon={<ExternalLink className="h-3.5 w-3.5" />}>
              Read the full issue on GitHub
            </Button>
          </a>
        )}
      </header>

      {issue.state !== "OPEN" && (
        <Callout title="This issue is closed">It is shown so you can learn from it. Pick an open issue to contribute.</Callout>
      )}
      {isStale(issue) && (
        <Callout tone="warning" title="No activity for over a year">
          Before starting, comment on the issue and ask whether it is still wanted.
        </Callout>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel
          title={
            <span className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-accent" aria-hidden /> Your plan
            </span>
          }
          description={`Step by step, from reading the issue to opening a pull request. ${doneCount} of ${data.steps.length} done.`}
          bodyClassName="px-4 py-1"
        >
          <ol>
            {data.steps.map((step, index) => (
              <PlanStep
                key={step.key}
                step={step}
                index={index}
                done={Boolean(done[step.key])}
                onToggle={() => setDone((current) => ({ ...current, [step.key]: !current[step.key] }))}
                search={data.search}
              />
            ))}
          </ol>
        </Panel>
        <div className="space-y-5">
          <DifficultyCard difficulty={data.difficulty} />
          <Panel title="Before you start">
            <ul className="space-y-2 text-sm text-muted">
              <li>✓ Comment on the issue to say you would like to work on it.</li>
              <li>✓ Read the project's CONTRIBUTING guide, if it has one.</li>
              <li>✓ Fork the repository and create a branch, for example <code className="font-mono text-xs text-ink">fix-issue-{issue.number}</code>.</li>
            </ul>
          </Panel>
        </div>
      </div>

      <section aria-labelledby="files-heading" className="space-y-3">
        <h2 id="files-heading" className="flex items-center gap-2 text-base font-semibold">
          <Target className="h-4 w-4 text-accent" aria-hidden /> Files probably involved
        </h2>
        <Callout title="CodePulse inferred relationship">{data.basis}</Callout>
        {data.files.length === 0 ? (
          <EmptyState title="No analyzed file matched this issue">
            The issue does not mention any file, module or folder name that CodePulse found in the code.
            {data.search && " Use the search step in the plan above to find where to look."}
            {data.files_limited && " This repository is large, so detailed file data was only kept for part of it."}
          </EmptyState>
        ) : (
          <>
            <ul className="grid gap-3 xl:grid-cols-2">
              {data.files.map((file) => (
                <RelatedFileCard key={file.file} file={file} repoUrl={repo.data?.url} />
              ))}
            </ul>
            {data.more_files > 0 && (
              <p className="text-xs text-faint">
                {data.more_files} more weakly matching {data.more_files === 1 ? "file is" : "files are"} not shown.
              </p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
