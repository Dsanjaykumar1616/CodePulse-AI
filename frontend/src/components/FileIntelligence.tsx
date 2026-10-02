import { useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Circle, ExternalLink, Maximize2, Network, X } from "lucide-react";
import { useFileIntelligence } from "../hooks/queries";
import { FileLink, FilePath, useOpenFile } from "./FilePath";
import {
  Badge,
  Button,
  Callout,
  cx,
  Drawer,
  EmptyState,
  EvidenceItem,
  Explainer,
  InfoTip,
  LevelBadge,
  NotAvailable,
  Progress,
  Skeleton,
  Tabs,
} from "./ui";
import { capitalize, debtSeverity, fmtDate, fmtNumber, fmtPercent, severityOf, severityText } from "../lib/format";
import type { FileIntelligence, IssueMatch, ReadinessItem } from "../types/api";

export const RISK_SIGNAL_NOTE =
  "Historical risk signal from a model trained on past bug-fix commits in this repository. It is not a confirmed probability of future defects.";

const TABS = [
  { value: "before", label: "Before you modify" },
  { value: "impact", label: "Change impact" },
  { value: "risk", label: "Risk" },
  { value: "debt", label: "Debt" },
  { value: "history", label: "Git history" },
  { value: "issues", label: "Issues" },
  { value: "review", label: "Review findings" },
  { value: "related", label: "Related files" },
  { value: "tests", label: "Tests" },
  { value: "plan", label: "Contribution plan" },
] as const;
type TabValue = (typeof TABS)[number]["value"];

function isTab(value: string | null): value is TabValue {
  return TABS.some((tab) => tab.value === value);
}

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

function Stat({ label, children, title }: { label: string; children: ReactNode; title?: string }) {
  return (
    <div className="min-w-0" title={title}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="tabular mt-0.5 text-base font-semibold text-ink">{children}</dd>
    </div>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="divide-y divide-line rounded border border-line bg-surface">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
          <dt className="text-muted">{label}</dt>
          <dd className="tabular text-right text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="space-y-2.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Reasons({ items, empty }: { items: string[] | undefined; empty: string }) {
  if (!items || items.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex gap-2 text-sm">
          <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-high" aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function IssueStateBadge({ state }: { state: string }) {
  const upper = (state || "UNKNOWN").toUpperCase();
  if (upper === "OPEN") return <Badge severity="low">Open</Badge>;
  if (upper === "CLOSED") return <Badge>Closed</Badge>;
  return <Badge>Unknown</Badge>;
}

function IssueMatches({ issues }: { issues: IssueMatch[] }) {
  const open = issues.filter((issue) => issue.state.toUpperCase() === "OPEN");
  const other = issues.filter((issue) => issue.state.toUpperCase() !== "OPEN");
  const render = (list: IssueMatch[]) => (
    <ul className="space-y-2">
      {list.map((issue) => (
        <li key={issue.number} className="rounded border border-line bg-surface px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <IssueStateBadge state={issue.state} />
            <Badge severity={issue.relevance === "HIGH" ? "medium" : "none"}>{capitalize(issue.relevance)} relevance</Badge>
            {issue.labels.slice(0, 4).map((label) => (
              <Badge key={label}>{label}</Badge>
            ))}
          </div>
          <a
            href={issue.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="mt-1.5 inline-flex items-start gap-1 text-sm font-medium text-ink hover:underline"
          >
            <span className="text-muted">#{issue.number}</span> {issue.title}
            <ExternalLink className="mt-1 h-3 w-3 shrink-0 text-faint" aria-hidden />
          </a>
          {issue.evidence.length > 0 && <p className="mt-1 text-xs text-muted">Matched by: {issue.evidence.join("; ")}</p>}
        </li>
      ))}
    </ul>
  );
  return (
    <div className="space-y-5">
      <Section title={`Open issues (${open.length})`}>
        <p className="text-xs text-muted">Open issues may be active contribution opportunities. Check the issue before starting work.</p>
        {open.length ? render(open) : <p className="text-sm text-muted">No open issues mention this file.</p>}
      </Section>
      {other.length > 0 && (
        <Section title={`Closed or unknown (${other.length})`}>
          <p className="text-xs text-muted">Closed issues are historical context only, not open work.</p>
          {render(other)}
        </Section>
      )}
    </div>
  );
}

const DEBT_COMPONENTS = [
  { key: "complexity_component", label: "Complexity", weight: 0.35 },
  { key: "ml_component", label: "Historical risk", weight: 0.25 },
  { key: "duplication_component", label: "Duplication", weight: 0.2 },
  { key: "maintainability_component", label: "Maintainability", weight: 0.1 },
  { key: "churn_component", label: "Churn", weight: 0.1 },
] as const;

// ---------------------------------------------------------------------------
// Contribution plan (also used on the full file page)
// ---------------------------------------------------------------------------

export function ContributionPlanView({ data }: { data: FileIntelligence }) {
  const plan = data.plan;
  const [done, setDone] = useState<Set<number>>(new Set());
  if (!plan) {
    return <EmptyState title="No contribution plan">A plan could not be generated for this file.</EmptyState>;
  }
  const opportunity = data.opportunity;
  const reasons = opportunity?.reasons?.length ? opportunity.reasons : data.explanation?.reasons ?? [];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="panel px-3 py-2.5">
          <p className="text-xs text-muted">Suggested contribution</p>
          <p className="mt-0.5 text-sm font-medium">{plan.contribution_type}</p>
        </div>
        <div className="panel px-3 py-2.5">
          <p className="text-xs text-muted">Difficulty</p>
          <div className="mt-1">
            <LevelBadge level={plan.difficulty} />
          </div>
        </div>
        <div className="panel px-3 py-2.5">
          <p className="text-xs text-muted">Dependency impact</p>
          <div className="mt-1">
            <LevelBadge level={data.impact?.impact_level ?? null} />
          </div>
        </div>
        <div className="panel px-3 py-2.5">
          <p className="text-xs text-muted">Priority</p>
          <div className="mt-1">
            <LevelBadge level={plan.priority} />
          </div>
        </div>
      </div>

      {data.difficulty_basis && (
        <Explainer title={`Why is this estimated as ${data.difficulty_basis.level ? data.difficulty_basis.level.toLowerCase() : "this level"}?`}>
          <p className="text-ink">{data.difficulty_basis.summary}</p>
          <ul className="mt-2 list-disc space-y-0.5 pl-4">
            {data.difficulty_basis.conditions_met.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-faint">
            {data.difficulty_basis.rule} {data.difficulty_basis.disclaimer}
          </p>
        </Explainer>
      )}

      {data.readiness && (
        <Section title="Contribution readiness">
          <ReadinessList items={data.readiness} />
        </Section>
      )}

      <Section title="Why this file">
        <Reasons items={reasons} empty="No specific risk factors were found; the plan suggests a small, safe improvement." />
        {data.open_issue_number && (
          <p className="text-sm text-muted">
            An open GitHub issue (#{data.open_issue_number}) mentions this file. Review it before starting.
          </p>
        )}
      </Section>

      <Section
        title="Plan"
        aside={
          <span className="tabular text-xs text-muted">
            {done.size} of {plan.steps.length} done
          </span>
        }
      >
        <ol className="space-y-1.5">
          {plan.steps.map((step, index) => {
            const checked = done.has(index);
            return (
              <li key={index}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={checked}
                  onClick={() =>
                    setDone((current) => {
                      const next = new Set(current);
                      if (next.has(index)) next.delete(index);
                      else next.add(index);
                      return next;
                    })
                  }
                  className="flex w-full items-start gap-3 rounded border border-line bg-surface px-3 py-2.5 text-left text-sm hover:bg-raised/50"
                >
                  <span className="tabular mt-px w-5 shrink-0 text-right text-xs text-faint">{index + 1}</span>
                  <span className={cx("flex-1", checked && "text-muted line-through decoration-faint")}>{step}</span>
                  {checked ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-low" aria-hidden />
                  ) : (
                    <Circle className="h-4 w-4 shrink-0 text-faint" aria-hidden />
                  )}
                </button>
              </li>
            );
          })}
        </ol>
        <p className="text-xs text-faint">
          Steps come from CodePulse's plan generator using this file's metrics, history, dependencies and issues. Progress is
          not saved.
        </p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contributor sections
// ---------------------------------------------------------------------------

export function ReadinessList({ items }: { items: ReadinessItem[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <EvidenceItem key={item.key} status={item.status}>
          {item.label}
        </EvidenceItem>
      ))}
    </ul>
  );
}

function KnowRow({ label, children, onClick, hint }: { label: string; children: ReactNode; onClick?: () => void; hint?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-3 py-2.5 text-sm">
      <dt className="flex shrink-0 items-center gap-1 text-muted">
        {label}
        {hint && <InfoTip label={label}>{hint}</InfoTip>}
      </dt>
      <dd className="min-w-0 text-right">
        {onClick ? (
          <button type="button" onClick={onClick} className="text-right text-ink decoration-faint hover:underline">
            {children}
          </button>
        ) : (
          children
        )}
      </dd>
    </div>
  );
}

function BeforeYouModify({ data, path, onTab }: { data: FileIntelligence; path: string; onTab: (tab: string) => void }) {
  const summary = data.summary;
  const explanation = data.explanation;
  const impact = data.change_impact;
  const history = data.history;
  const tests = data.tests;
  const testCount = (tests?.detected.length ?? 0) + (tests?.heuristic.length ?? 0);
  const openIssues = (data.issues ?? []).filter((issue) => issue.state.toUpperCase() === "OPEN").length;
  const met = data.why?.checks.filter((check) => check.met) ?? [];
  const complexity = explanation?.metrics.complexity ?? summary?.complexity;

  return (
    <div className="space-y-6">
      {data.explanation_error && <Callout tone="warning">{data.explanation_error}</Callout>}

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-muted">{data.directory ?? ""}/</span>
        {(data.roles ?? []).map((role) => (
          <Badge key={role.role} title={role.basis}>
            {role.role}
          </Badge>
        ))}
        {data.connectivity && <Badge>{data.connectivity}</Badge>}
      </div>

      <Section title="What you should know before changing this file">
        <dl className="divide-y divide-line rounded border border-line bg-surface">
          <KnowRow label="What it contains" hint="From code metrics. CodePulse measures structure; it does not summarise what the code does.">
            <span className="text-ink">
              {summary?.language ?? "Source"} · {fmtNumber(summary?.loc)} lines · {fmtNumber(summary?.functions)} functions ·{" "}
              {fmtNumber(summary?.classes)} classes
            </span>
          </KnowRow>
          <KnowRow label="Depends on" onClick={impact?.available ? () => onTab("impact") : undefined}>
            {impact?.available ? `${impact.upstream.length} local files` : "Not determined"}
          </KnowRow>
          <KnowRow label="Used by" onClick={impact?.available ? () => onTab("impact") : undefined}>
            {impact?.available
              ? `${impact.downstream.length} files directly${impact.indirect.length ? `, ${impact.indirect.length} more indirectly` : ""}`
              : "Not determined"}
          </KnowRow>
          <KnowRow label="Complexity" hint="Cyclomatic complexity: the number of independent paths through the code. Higher means more branches to understand and test.">
            {fmtNumber(complexity)}
            {explanation?.complexity_high && <span className="ml-1.5 text-xs text-high">top quarter of this repository</span>}
          </KnowRow>
          <KnowRow label="Historical risk" onClick={() => onTab("risk")} hint={RISK_SIGNAL_NOTE}>
            {summary?.risk_level ? `${summary.risk_level} · ${fmtPercent(summary.risk_probability)}` : "Unavailable"}
          </KnowRow>
          <KnowRow label="Technical debt" onClick={data.debt ? () => onTab("debt") : undefined}>
            {data.debt ? `${capitalize(data.debt.technical_debt_level)} · ${fmtNumber(data.debt.technical_debt_score, 0)}/100` : "Not calculated"}
          </KnowRow>
          <KnowRow label="Git history" onClick={history ? () => onTab("history") : undefined}>
            {history
              ? `${history.commit_count} commits by ${history.contributors} contributors · ${history.bug_fix_commits} bug fixes`
              : "No history recorded"}
          </KnowRow>
          <KnowRow label="Related issues" onClick={() => onTab("issues")}>
            {data.issues_available === false
              ? "Issue data unavailable"
              : openIssues
                ? `${openIssues} open (inferred)`
                : (data.issues?.length ?? 0) > 0
                  ? `${data.issues!.length} closed, history only`
                  : "No related open issue"}
          </KnowRow>
          <KnowRow label="Related files" onClick={() => onTab("related")}>
            {(data.related_files?.length ?? 0) + (data.duplicates?.length ?? 0) || "None found"}
          </KnowRow>
          <KnowRow label="Review findings" onClick={() => onTab("review")}>
            {data.review_findings?.length || "None"}
          </KnowRow>
          <KnowRow label="Potential tests" onClick={() => onTab("tests")}>
            {testCount ? `${testCount} found` : tests?.available === false ? "No test files in the repository" : "Not identified"}
          </KnowRow>
        </dl>
      </Section>

      {data.readiness && (
        <Section title="Contribution readiness">
          <ReadinessList items={data.readiness} />
          <p className="text-xs text-faint">An evidence checklist, not a score.</p>
        </Section>
      )}

      {data.why && (
        <Section title="Why this file?">
          {met.length ? (
            <ul className="space-y-1">
              {met.map((check) => (
                <EvidenceItem key={check.key} status="ok" detail={check.detail}>
                  {check.label}
                </EvidenceItem>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No strong risk factors were found for this file.</p>
          )}
          <p className="text-sm">{data.why.why_it_matters}</p>
          <p className="text-xs text-faint">{data.why.note}</p>
        </Section>
      )}

      {explanation?.recommendation && (
        <Section title="Recommendation">
          <p className="text-sm">{explanation.recommendation}</p>
        </Section>
      )}

      {data.plan && (
        <Button size="sm" variant="primary" onClick={() => onTab("plan")}>
          View contribution plan
        </Button>
      )}
      <span className="sr-only">{path}</span>
    </div>
  );
}

function ImpactColumn({ title, hint, files, empty }: { title: string; hint: string; files: string[]; empty: string }) {
  return (
    <div className="min-w-0">
      <h4 className="text-xs font-medium text-muted">
        {title} <span className="tabular text-faint">({files.length})</span>
      </h4>
      <p className="mb-2 text-2xs text-faint">{hint}</p>
      {files.length === 0 ? (
        <p className="rounded border border-dashed border-line px-3 py-3 text-xs text-faint">{empty}</p>
      ) : (
        <ul className="space-y-1 rounded border border-line bg-surface p-1.5">
          {files.map((file) => (
            <li key={file} className="rounded px-1.5 py-1 hover:bg-raised/60">
              <FileLink path={file} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChangeImpactView({ data, repositoryId, path }: { data: FileIntelligence; repositoryId: string; path: string }) {
  const impact = data.change_impact;
  if (!impact || !impact.available) {
    return (
      <EmptyState title="Change impact not available">
        {impact?.reason ?? "The dependency graph was not built for this analysis."}
      </EmptyState>
    );
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        {data.impact && <LevelBadge level={data.impact.impact_level} />}
        <span className="text-sm text-muted">{data.impact?.reason}</span>
        <Link to={`/app/r/${repositoryId}/architecture?mode=impact&focus=${encodeURIComponent(path)}`} className="ml-auto">
          <Button size="sm" icon={<Network className="h-3.5 w-3.5" />}>
            Show impact graph
          </Button>
        </Link>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[1fr_auto_1fr_1fr]">
        <ImpactColumn title="Depends on" hint="Upstream: files this file imports" files={impact.upstream} empty="Imports no local files" />
        <div className="hidden self-center rounded border border-accent/40 bg-accent/10 px-3 py-2 text-center lg:block">
          <p className="text-2xs text-muted">Target</p>
          <FilePath path={path} className="max-w-[12rem]" />
        </div>
        <ImpactColumn title="Used by" hint="Downstream: files that import it" files={impact.downstream} empty="No local file imports it" />
        <ImpactColumn title="Indirectly affected" hint="Files that import its dependents" files={impact.indirect} empty="No second-level dependents" />
      </div>
      {impact.affected_areas.length > 0 && (
        <Section title="Potentially affected areas">
          <ul className="flex flex-wrap gap-2">
            {impact.affected_areas.map((area) => (
              <li key={area.directory} className="rounded border border-line bg-surface px-2 py-1 text-xs">
                <span className="font-mono">{area.directory}/</span> <span className="text-muted">{area.files} files</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {impact.unresolved_imports.length > 0 && (
        <Section title="Imports static analysis could not resolve">
          <p className="font-mono text-xs text-muted">{impact.unresolved_imports.join(", ")}</p>
          <p className="text-xs text-faint">Usually third-party packages or the standard library. Not drawn as dependencies.</p>
        </Section>
      )}
      {data.impact?.checklist && (
        <Section title="Before submitting a change">
          <Reasons items={data.impact.checklist} empty="" />
        </Section>
      )}
      <p className="text-xs text-muted">{impact.note}</p>
    </div>
  );
}

function TestsView({ data }: { data: FileIntelligence }) {
  const tests = data.tests;
  if (!tests) return <EmptyState title="Test discovery not available">Re-open this file after the analysis loads.</EmptyState>;
  const list = (items: { file: string; basis: string }[]) => (
    <ul className="divide-y divide-line rounded border border-line bg-surface">
      {items.map((item) => (
        <li key={item.file} className="px-3 py-2">
          <FileLink path={item.file} />
          <p className="text-xs text-muted">{item.basis}</p>
        </li>
      ))}
    </ul>
  );
  return (
    <div className="space-y-6">
      <Section title="Detected relationship">
        <p className="text-xs text-muted">A test file statically imports this file.</p>
        {tests.detected.length ? list(tests.detected) : <p className="text-sm text-faint">None detected.</p>}
      </Section>
      <Section title="Heuristic relationship">
        <p className="text-xs text-muted">A test file's name matches this file's name. Likely, but not confirmed.</p>
        {tests.heuristic.length ? list(tests.heuristic) : <p className="text-sm text-faint">None found.</p>}
      </Section>
      {tests.reason && <Callout>{tests.reason}</Callout>}
      <p className="text-xs text-faint">
        CodePulse never invents test mappings. Tests that exercise this file through other modules, fixtures or dynamic
        imports are not detected.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The intelligence view
// ---------------------------------------------------------------------------

export function FileIntelligenceView({
  repositoryId,
  path,
  tab,
  onTabChange,
  onClose,
  showOpenPage,
}: {
  repositoryId: string;
  path: string;
  tab: string | null;
  onTabChange: (tab: string) => void;
  onClose?: () => void;
  showOpenPage?: boolean;
}) {
  const query = useFileIntelligence(repositoryId, path);
  const active: TabValue = isTab(tab) ? tab : tab === "dependencies" ? "impact" : "before";
  const data = query.data;

  const header = (
    <header className="flex items-start gap-3 border-b border-line bg-surface px-5 py-4">
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted">File intelligence</p>
        <h2 className="mt-0.5 min-w-0 text-base">
          <FilePath path={path} className="!text-[15px]" />
        </h2>
        {data && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <LevelBadge level={data.explanation?.risk_level ?? data.summary?.risk_level ?? null} fallback="Risk not available" />
            {data.debt && (
              <Badge severity={severityOf(data.debt.technical_debt_level)}>
                Debt {fmtNumber(data.debt.technical_debt_score, 0)} · {capitalize(data.debt.technical_debt_level)}
              </Badge>
            )}
            {data.summary?.language && <Badge>{data.summary.language}</Badge>}
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {showOpenPage && (
          <Link to={`/app/r/${repositoryId}/file?path=${encodeURIComponent(path)}`}>
            <Button size="sm" variant="ghost" aria-label="Open as page" title="Open as page">
              <Maximize2 className="h-4 w-4" />
            </Button>
          </Link>
        )}
        {onClose && (
          <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close file intelligence">
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </header>
  );

  if (query.isLoading) {
    return (
      <div className="flex h-full flex-col">
        {header}
        <div className="space-y-3 p-5">
          <Skeleton className="h-16" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }
  if (query.isError || !data) {
    return (
      <div className="flex h-full flex-col">
        {header}
        <EmptyState title="File intelligence is not available">{query.error?.message}</EmptyState>
      </div>
    );
  }

  const explanation = data.explanation;
  const summary = data.summary;
  const impact = data.impact;
  const history = data.history;

  const strip = (
    <dl className="grid grid-cols-3 gap-x-4 gap-y-3 border-b border-line px-5 py-4 sm:grid-cols-5">
      <Stat label="Risk signal" title={RISK_SIGNAL_NOTE}>
        {summary?.risk_probability !== null && summary?.risk_probability !== undefined
          ? fmtPercent(summary.risk_probability)
          : "—"}
      </Stat>
      <Stat label="Technical debt">{data.debt ? fmtNumber(data.debt.technical_debt_score, 0) : "—"}</Stat>
      <Stat label="Complexity">{fmtNumber(explanation?.metrics.complexity ?? summary?.complexity)}</Stat>
      <Stat label="Maintainability">{fmtNumber(explanation?.metrics.maintainability ?? summary?.maintainability, 1)}</Stat>
      <Stat label="Churn">{fmtNumber(explanation?.metrics.code_churn ?? summary?.code_churn)}</Stat>
      <Stat label="Bug-fix commits">{fmtNumber(explanation?.metrics.bug_fix_commits ?? summary?.bug_fix_commits)}</Stat>
      <Stat label="Connections">{impact?.available ? fmtNumber(impact.total_connections ?? null) : "—"}</Stat>
      <Stat label="Used by">{impact?.available ? fmtNumber(impact.used_by.length) : "—"}</Stat>
      <Stat label="Depends on">{impact?.available ? fmtNumber(impact.depends_on.length) : "—"}</Stat>
      <Stat label="Lines of code">{fmtNumber(explanation?.metrics.loc ?? summary?.loc)}</Stat>
    </dl>
  );

  const counts: Partial<Record<TabValue, number>> = {
    issues: data.issues?.length ?? 0,
    review: data.review_findings?.length ?? 0,
    related: (data.related_files?.length ?? 0) + (data.duplicates?.length ?? 0),
    tests: (data.tests?.detected.length ?? 0) + (data.tests?.heuristic.length ?? 0),
    impact: data.change_impact?.available ? data.change_impact.downstream.length : undefined,
  };

  let body: ReactNode = null;
  switch (active) {
    case "before":
      body = (
        <BeforeYouModify
          data={data}
          path={path}
          onTab={onTabChange}
        />
      );
      break;
    case "risk":
      body = (
        <div className="space-y-6">
          <Callout title="About this signal">{RISK_SIGNAL_NOTE}</Callout>
          {explanation ? (
            <>
              <div className="flex flex-wrap items-center gap-6">
                <Stat label="Historical risk signal">
                  {explanation.risk_level === "Not available" ? (
                    <NotAvailable reason="The ML model did not run for this repository." />
                  ) : (
                    fmtPercent(explanation.bug_probability)
                  )}
                </Stat>
                <Stat label="Risk level">
                  <LevelBadge level={explanation.risk_level} />
                </Stat>
                <Stat label="High complexity">{explanation.complexity_high ? "Yes" : "No"}</Stat>
                <Stat label="High churn">{explanation.churn_high ? "Yes" : "No"}</Stat>
              </div>
              <Section title="Contributing factors">
                <Reasons items={explanation.reasons} empty="No rule-based risk factors exceeded the repository's thresholds." />
              </Section>
              <p className="text-xs text-muted">
                Factors are flagged when a metric is in the top quarter of this repository (or the bottom quarter for
                maintainability).
              </p>
            </>
          ) : (
            <NotAvailable reason={data.explanation_error} />
          )}
        </div>
      );
      break;
    case "debt":
      body = data.debt ? (
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <span className={cx("tabular text-3xl font-semibold", severityText[debtSeverity(data.debt.technical_debt_score)])}>
              {fmtNumber(data.debt.technical_debt_score, 1)}
            </span>
            <div>
              <LevelBadge level={data.debt.technical_debt_level} />
              <p className="mt-1 text-xs text-muted">Technical debt score, 0–100</p>
            </div>
          </div>
          <Section title="Score components">
            <ul className="space-y-3">
              {DEBT_COMPONENTS.map((component) => {
                const value = data.debt![component.key];
                return (
                  <li key={component.key}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>
                        {component.label} <span className="text-xs text-faint">weight {component.weight * 100}%</span>
                      </span>
                      <span className="tabular text-muted">{value === null ? "Not available" : fmtNumber(value, 0)}</span>
                    </div>
                    {value !== null && <Progress value={value} severity={debtSeverity(value)} label={`${component.label} component`} />}
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-muted">
              Components are relative to this repository. Unavailable components are excluded and the remaining weights are
              rescaled.
            </p>
          </Section>
          <Section title="Evidence">
            <Reasons items={data.debt.debt_reasons} empty="No component reached the evidence threshold." />
          </Section>
        </div>
      ) : (
        <EmptyState title="Technical debt not available">Technical debt was not calculated for this file.</EmptyState>
      );
      break;
    case "impact":
      body = <ChangeImpactView data={data} repositoryId={repositoryId} path={path} />;
      break;
    case "history":
      body = history ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <LevelBadge level={history.recent_activity} />
            <span className="text-sm text-muted">{history.explanation}</span>
          </div>
          <Facts
            rows={[
              ["Commits", fmtNumber(history.commit_count)],
              ["Contributors", fmtNumber(history.contributors)],
              ["Lines added", fmtNumber(history.lines_added ?? null)],
              ["Lines deleted", fmtNumber(history.lines_deleted ?? null)],
              ["Code churn", fmtNumber(history.code_churn)],
              ["Bug-fix commits", fmtNumber(history.bug_fix_commits)],
              ["File age", history.file_age_days !== undefined ? `${fmtNumber(history.file_age_days)} days` : "—"],
              ["First change", fmtDate(history.first_modified)],
              ["Last change", fmtDate(history.last_modified)],
            ]}
          />
          <p className="text-xs text-muted">Bug-fix commits are identified from keywords in commit messages.</p>
        </div>
      ) : (
        <EmptyState title="No Git history found">No commit history was recorded for this file.</EmptyState>
      );
      break;
    case "issues":
      body = data.issues && data.issues.length > 0 ? (
        <IssueMatches issues={data.issues} />
      ) : (
        <EmptyState title="No related GitHub issues">
          No issues matched this file's path, name or keywords, or issue data was unavailable for this analysis.
        </EmptyState>
      );
      break;
    case "review":
      body = data.review_findings && data.review_findings.length > 0 ? (
        <ul className="space-y-2">
          {data.review_findings.map((finding) => (
            <li key={`${finding.rule_id}`} className="rounded border border-line bg-surface px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <LevelBadge level={finding.severity} />
                <span className="text-sm font-medium">{finding.title}</span>
                <code className="text-xs text-faint">{finding.rule_id}</code>
              </div>
              <p className="tabular mt-1 text-sm text-muted">{finding.evidence}</p>
              <p className="mt-1 text-sm">{finding.recommendation}</p>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No review findings">No rule-based review rule was triggered for this file.</EmptyState>
      );
      break;
    case "related":
      body = (
        <div className="space-y-6">
          <Section title="Related by imports">
            {data.related_files && data.related_files.length > 0 ? (
              <ul className="divide-y divide-line rounded border border-line bg-surface">
                {data.related_files.map((related) => (
                  <li key={related.file} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <FileLink path={related.file} className="min-w-0 flex-1" />
                    <span className="text-xs text-muted">{related.reason}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No related files were found through static imports.</p>
            )}
          </Section>
          <Section title="Similar code">
            {data.duplicates && data.duplicates.length > 0 ? (
              <ul className="divide-y divide-line rounded border border-line bg-surface">
                {data.duplicates.map((pair) => {
                  const other = pair.file_a === path ? pair.file_b : pair.file_a;
                  return (
                    <li key={other} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                      <FileLink path={other} className="min-w-0 flex-1" />
                      <Badge severity={severityOf(pair.similarity_level)}>{fmtNumber(pair.similarity_score, 1)}% similar</Badge>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-muted">No files with similar code were detected.</p>
            )}
          </Section>
        </div>
      );
      break;
    case "tests":
      body = <TestsView data={data} />;
      break;
    case "plan":
      body = <ContributionPlanView data={data} />;
      break;
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {header}
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {strip}
        <div className="border-b border-line px-5">
          <Tabs
            label="File intelligence sections"
            value={active}
            onChange={(value) => onTabChange(value)}
            tabs={TABS.map((item) => ({ ...item, count: counts[item.value] }))}
          />
        </div>
        <div className="px-5 py-5" role="tabpanel">
          {body}
        </div>
      </div>
    </div>
  );
}

/** Renders the drawer whenever ?file= is present on a repository page. */
export function FileDrawerHost({ repositoryId }: { repositoryId: string }) {
  const { file, tab, close } = useOpenFile();
  const [params, setParams] = useSearchParams();
  return (
    <Drawer open={Boolean(file)} onClose={close} label={file ? `File intelligence for ${file}` : "File intelligence"}>
      {file && (
        <FileIntelligenceView
          repositoryId={repositoryId}
          path={file}
          tab={tab}
          showOpenPage
          onClose={close}
          onTabChange={(value) => {
            const next = new URLSearchParams(params);
            next.set("tab", value);
            setParams(next, { replace: true });
          }}
        />
      )}
    </Drawer>
  );
}
