import { useMemo, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowRight, GitPullRequestArrow } from "lucide-react";
import {
  Badge,
  Button,
  EmptyState,
  Explainer,
  EvidenceItem,
  InfoTip,
  LevelBadge,
  PageLoading,
  Pagination,
  SearchInput,
  Segmented,
  Select,
} from "../../components/ui";
import { FilePath, useOpenFile } from "../../components/FilePath";
import { RISK_SIGNAL_NOTE } from "../../components/FileIntelligence";
import { useOpportunities, useRepository, useTable } from "../../hooks/queries";
import { FirstContribution, Glossary } from "../../components/Guidance";
import { capitalize, debtSeverity, fmtNumber, fmtPercent, riskSeverity, severityText } from "../../lib/format";
import type { Difficulty, EnrichedOpportunity, IssueStatus } from "../../types/api";

type SortKey = "opportunity_score" | "risk_probability" | "debt_score" | "centrality";
const DIFFICULTIES: Difficulty[] = ["BEGINNER", "INTERMEDIATE", "ADVANCED"];

function Metric({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1 text-2xs text-faint">
        {label}
        {hint && <InfoTip label={label}>{hint}</InfoTip>}
      </dt>
      <dd className="tabular truncate text-sm">{children}</dd>
    </div>
  );
}

function IssueContext({ row }: { row: EnrichedOpportunity }) {
  if (row.issue_status === "UNAVAILABLE") return <span className="text-faint">Unavailable</span>;
  if (row.open_issue_count > 0) return <Badge severity="low">{row.open_issue_count} open</Badge>;
  if (row.closed_issue_count > 0) return <span className="text-muted">{row.closed_issue_count} closed (history)</span>;
  return <span className="text-faint">No related open issue</span>;
}

function OpportunityCard({ row, repoId, maxScore }: { row: EnrichedOpportunity; repoId: string; maxScore: number }) {
  const { open } = useOpenFile();
  const met = row.why.checks.filter((check) => check.met);
  return (
    <li className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <span className="tabular w-6 pt-0.5 text-right text-sm text-faint">{row.rank}</span>
        <div className="min-w-0 flex-1">
          <button type="button" onClick={() => open(row.file)} className="max-w-full text-left decoration-faint hover:underline">
            <FilePath path={row.file} className="!text-[13.5px]" />
          </button>
          <p className="mt-0.5 text-sm text-muted">{row.suggested_action}</p>
          {row.roles.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {row.roles.map((role) => (
                <Badge key={role}>{role}</Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <LevelBadge level={row.difficulty} />
          <div className="w-28" title="Opportunity score relative to the top-ranked opportunity">
            <div className="flex justify-between text-2xs text-faint">
              <span>Score</span>
              <span className="tabular text-ink">{fmtNumber(row.opportunity_score, 1)}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-raised">
              <div className="h-full rounded-full bg-accent" style={{ width: `${(100 * row.opportunity_score) / maxScore}%` }} />
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-5 pl-10 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <h3 className="text-xs font-medium text-muted">Why this file?</h3>
          {met.length === 0 ? (
            <p className="mt-1.5 text-sm text-muted">No strong risk factors; recommended as a lower-risk change.</p>
          ) : (
            <ul className="mt-1.5 space-y-1">
              {met.map((check) => (
                <EvidenceItem key={check.key} status="ok" detail={check.detail}>
                  {check.label}
                </EvidenceItem>
              ))}
            </ul>
          )}
          <p className="mt-2.5 text-sm">{row.why.why_it_matters}</p>
        </div>

        <dl className="grid grid-cols-2 content-start gap-x-4 gap-y-3 sm:grid-cols-3">
          <Metric label="Risk signal" hint={RISK_SIGNAL_NOTE}>
            <span className={severityText[riskSeverity(row.risk_probability === null ? null : row.risk_probability * 100)]}>
              {row.risk_probability === null ? "Unavailable" : fmtPercent(row.risk_probability)}
            </span>
          </Metric>
          <Metric label="Technical debt" hint="0–100 from complexity, historical risk, duplication, maintainability and churn. Higher means more debt.">
            <span className={severityText[debtSeverity(row.debt_score)]}>
              {row.debt_level ? `${capitalize(row.debt_level)} · ${fmtNumber(row.debt_score, 0)}` : "—"}
            </span>
          </Metric>
          <Metric label="Connections" hint="Direct static-import relationships with other repository files. Highly connected files affect more of the code.">
            {row.connectivity ?? "—"}
            {row.used_by !== null && <span className="block text-2xs text-faint">used by {row.used_by}</span>}
          </Metric>
          <Metric label="Change impact" hint="How far a change could reach, from the number of files that import this one.">
            <LevelBadge level={row.impact} fallback="—" />
          </Metric>
          <Metric label="Review findings">{row.review_finding_count || "None"}</Metric>
          <Metric label="GitHub issues" hint="Issues whose text mentions this file. CodePulse inferred relationship.">
            <IssueContext row={row} />
          </Metric>
        </dl>
      </div>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3 pl-10">
        {row.difficulty_basis ? (
          <div className="min-w-0 flex-1">
            <Explainer title={`Why ${capitalize(row.difficulty)}?`}>
              <p className="text-ink">{row.difficulty_basis.summary}</p>
              <ul className="mt-2 list-disc space-y-0.5 pl-4">
                {row.difficulty_basis.conditions_met.map((condition) => (
                  <li key={condition}>{condition}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-faint">
                {row.difficulty_basis.rule} {row.difficulty_basis.disclaimer}
              </p>
            </Explainer>
          </div>
        ) : (
          <span />
        )}
        <Link to={`/app/r/${repoId}/file?path=${encodeURIComponent(row.file)}&tab=before`}>
          <Button variant="primary" size="sm">
            Explore opportunity <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </Link>
      </div>
    </li>
  );
}

export default function OpportunitiesPage() {
  const { repoId } = useParams<"repoId">();
  const opportunities = useOpportunities(repoId);
  const repository = useRepository(repoId);
  const [params, setParams] = useSearchParams();
  const difficultyParam = params.get("difficulty");
  const difficulty: "all" | Difficulty = DIFFICULTIES.includes(difficultyParam as Difficulty)
    ? (difficultyParam as Difficulty)
    : "all";
  const [riskLevel, setRiskLevel] = useState("all");
  const [issueStatus, setIssueStatus] = useState<"all" | IssueStatus>("all");
  const [sortKey, setSortKey] = useState<SortKey>("opportunity_score");
  const rows = opportunities.data?.items ?? [];

  const filter = useMemo(
    () => (row: EnrichedOpportunity) =>
      (difficulty === "all" || row.difficulty === difficulty) &&
      (riskLevel === "all" || (riskLevel === "none" ? row.risk_level === null : row.risk_level === riskLevel)) &&
      (issueStatus === "all" || row.issue_status === issueStatus),
    [difficulty, riskLevel, issueStatus],
  );
  const table = useTable(rows, {
    search: (row, text) => row.file.toLowerCase().includes(text) || row.title.toLowerCase().includes(text),
    filter,
    initialSort: { key: "opportunity_score", dir: "desc" },
    pageSize: 12,
  });

  if (opportunities.isLoading) return <PageLoading />;
  if (opportunities.isError || !opportunities.data) {
    return <EmptyState title="Opportunities not available">{opportunities.error?.message}</EmptyState>;
  }
  const data = opportunities.data;
  if (!data.available) return <EmptyState title="Opportunities not available">{data.reason}</EmptyState>;

  const countOf = (level: Difficulty) => rows.filter((row) => row.difficulty === level).length;
  const recommended =
    rows.find((row) => row.difficulty === "BEGINNER") ??
    rows.find((row) => row.difficulty === "INTERMEDIATE") ??
    rows[0];
  const maxScore = Math.max(1, ...rows.map((row) => row.opportunity_score));
  const setDifficulty = (value: "all" | Difficulty) => {
    const next = new URLSearchParams(params);
    if (value === "all") next.delete("difficulty");
    else next.set("difficulty", value);
    setParams(next, { replace: true });
    table.resetPage();
  };

  return (
    <div className="space-y-5">
      {recommended && difficulty === "all" && (
        <FirstContribution
          repoId={repoId!}
          repoUrl={repository.data?.url}
          file={recommended.file}
          difficulty={recommended.difficulty}
          reason={`${recommended.suggested_action} ${recommended.why.why_it_matters}`}
        />
      )}

      <div>
        <h2 className="text-base font-semibold">All contribution opportunities</h2>
        <p className="mt-0.5 max-w-3xl text-sm text-muted">
          Every analyzed file, ranked by how useful a change there could be. Pick a difficulty that matches your
          experience. {data.disclaimer}
        </p>
      </div>
      <Glossary />

      {rows.length === 0 ? (
        <EmptyState icon={<GitPullRequestArrow className="h-6 w-6" />} title="No opportunities">
          CodePulse did not generate contribution opportunities for this repository.
        </EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented<"all" | Difficulty>
              label="Estimated difficulty"
              value={difficulty}
              onChange={setDifficulty}
              options={[
                { value: "all", label: "All", count: rows.length },
                { value: "BEGINNER", label: "Beginner", count: countOf("BEGINNER") },
                { value: "INTERMEDIATE", label: "Intermediate", count: countOf("INTERMEDIATE") },
                { value: "ADVANCED", label: "Advanced", count: countOf("ADVANCED") },
              ]}
            />
            <Select label="Risk level" value={riskLevel} onChange={(event) => { setRiskLevel(event.target.value); table.resetPage(); }}>
              <option value="all">Any risk</option>
              {["Low", "Medium", "High", "Critical"].map((level) => (
                <option key={level} value={level}>
                  {level} risk
                </option>
              ))}
              <option value="none">Risk unavailable</option>
            </Select>
            <Select
              label="Issue status"
              value={issueStatus}
              onChange={(event) => {
                setIssueStatus(event.target.value as "all" | IssueStatus);
                table.resetPage();
              }}
            >
              <option value="all">Any issue status</option>
              <option value="ISSUE_AVAILABLE">Issue available</option>
              <option value="NO_ISSUE">No issue found</option>
              <option value="UNAVAILABLE">Issue data unavailable</option>
            </Select>
            <Select
              label="Sort by"
              value={sortKey}
              onChange={(event) => {
                const key = event.target.value as SortKey;
                setSortKey(key);
                if (table.sort?.key !== key) table.toggleSort(key);
              }}
            >
              <option value="opportunity_score">Sort by score</option>
              <option value="risk_probability">Sort by risk</option>
              <option value="debt_score">Sort by debt</option>
              <option value="centrality">Sort by connections</option>
            </Select>
            <SearchInput value={table.query} onChange={table.setQuery} label="Search opportunities" placeholder="Search files" className="ml-auto w-full sm:w-60" />
          </div>

          {!data.issues_available && (
            <p className="text-xs text-muted">GitHub issue data was unavailable for this analysis, so issue context is not shown.</p>
          )}

          {table.total === 0 ? (
            <EmptyState title="No opportunities match">Try a different filter.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {table.rows.map((row) => (
                <OpportunityCard key={row.file} row={row} repoId={repoId!} maxScore={maxScore} />
              ))}
            </ul>
          )}
          <Pagination page={table.page} pageCount={table.pageCount} total={table.total} pageSize={table.pageSize} onPage={table.setPage} />
        </>
      )}
    </div>
  );
}
