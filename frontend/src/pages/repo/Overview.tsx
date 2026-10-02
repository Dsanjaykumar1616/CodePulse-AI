import { Link, useParams } from "react-router-dom";
import { Callout, Panel, PageLoading, EmptyState, LevelBadge, Button, cx } from "../../components/ui";
import { MetricCard } from "../../components/data";
import { FileLink } from "../../components/FilePath";
import { RISK_SIGNAL_NOTE } from "../../components/FileIntelligence";
import { useOpportunities, useOverview, useRisk } from "../../hooks/queries";
import { debtSeverity, fmtDateTime, fmtNumber, fmtPercent, riskSeverity, scoreSeverity, severityText } from "../../lib/format";

const LANGUAGE_COLORS = [
  "rgb(var(--accent))",
  "rgb(var(--sev-low))",
  "rgb(var(--sev-medium))",
  "rgb(var(--sev-high))",
  "rgb(var(--sev-critical))",
  "rgb(var(--muted))",
  "rgb(var(--faint))",
];

export function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const entries = Object.entries(languages).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  if (!total) return <p className="text-sm text-muted">No supported languages detected.</p>;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-raised" role="img" aria-label="Language distribution">
        {entries.map(([language, count], index) => (
          <span
            key={language}
            style={{ width: `${(100 * count) / total}%`, background: LANGUAGE_COLORS[index % LANGUAGE_COLORS.length] }}
            title={`${language}: ${count} files`}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {entries.map(([language, count], index) => (
          <li key={language} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: LANGUAGE_COLORS[index % LANGUAGE_COLORS.length] }} aria-hidden />
            <span>{language}</span>
            <span className="tabular text-muted">
              {count} {count === 1 ? "file" : "files"} · {((100 * count) / total).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function RepoOverview() {
  const { repoId } = useParams<"repoId">();
  const overview = useOverview(repoId);
  const risk = useRisk(repoId);
  const opportunities = useOpportunities(repoId);

  if (overview.isLoading) return <PageLoading />;
  if (overview.isError || !overview.data) {
    return <EmptyState title="Overview not available">{overview.error?.message}</EmptyState>;
  }
  const data = overview.data;
  const m = data.metrics;
  const topRisk = (risk.data?.files ?? []).filter((file) => file.risk_probability !== null).slice(0, 6);
  const topOpportunities = (opportunities.data?.items ?? []).slice(0, 6);

  return (
    <div className="space-y-6">
      {data.warnings.length > 0 && (
        <Callout tone="warning" title="Notes from this analysis">
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Callout>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <MetricCard
          label="Health score"
          metric={m.health_score}
          format={(value) => fmtNumber(value, 0)}
          severity={scoreSeverity(m.health_score.value)}
          suffix="/ 100"
          detail={m.health_level}
          hint="Weighted combination of code quality, Git stability, historical risk and maintainability."
        />
        <MetricCard label="Code quality" metric={m.code_quality} format={(v) => fmtNumber(v, 0)} suffix="/ 100" severity={scoreSeverity(m.code_quality.value)} hint="Lower complexity and nesting and more comments score higher." />
        <MetricCard label="Git stability" metric={m.git_stability} format={(v) => fmtNumber(v, 0)} suffix="/ 100" severity={scoreSeverity(m.git_stability.value)} hint="Lower churn, fewer repeated changes and fewer historical bug fixes score higher." />
        <MetricCard label="Maintainability" metric={m.maintainability} format={(v) => fmtNumber(v, 0)} suffix="/ 100" severity={scoreSeverity(m.maintainability.value)} hint="Average maintainability index of Python files." />
        <MetricCard
          label="Historical risk signal"
          metric={m.historical_risk_signal}
          format={(v) => `${fmtNumber(v, 1)}%`}
          severity={riskSeverity(m.historical_risk_signal.value)}
          hint={RISK_SIGNAL_NOTE}
          detail={m.elevated_risk_files !== null ? `${m.elevated_risk_files} files high or critical` : undefined}
        />
        <MetricCard
          label="Technical debt"
          metric={m.technical_debt}
          format={(v) => fmtNumber(v, 0)}
          suffix="/ 100"
          severity={debtSeverity(m.technical_debt.value)}
          detail={m.technical_debt_level ? `Level ${m.technical_debt_level.toLowerCase()}` : undefined}
          hint="Average technical-debt score of analyzed files. Higher means more debt."
        />
        <MetricCard label="Duplicate groups" metric={m.duplicate_groups} hint="Groups of files with 75% or more similar normalized code." />
        <MetricCard label="Dependencies" metric={m.dependencies} hint="Static import and include relationships between repository files." />
        <MetricCard label="Contributors" metric={m.contributors} hint="Distinct commit author emails." />
        <MetricCard
          label="Files analyzed"
          metric={{ value: data.analyzed_files, available: true, reason: null }}
          detail={data.total_files !== null ? `of ${fmtNumber(data.total_files)} files in the repository` : undefined}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
        <Panel title="Languages" description="Analyzed source files by language">
          <LanguageBar languages={data.analyzed_languages} />
          <dl className="mt-5 grid grid-cols-3 gap-3 border-t border-line pt-4 text-sm">
            <div>
              <dt className="text-xs text-muted">Commits</dt>
              <dd className="tabular font-medium">{fmtNumber(data.commits)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Unsupported files</dt>
              <dd className="tabular font-medium">{fmtNumber(data.unsupported_files)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Analyzed</dt>
              <dd className="font-medium">{fmtDateTime(data.analyzed_at ?? data.repository.analyzed_at)}</dd>
            </div>
          </dl>
        </Panel>

        <Panel
          title="Highest historical risk"
          description="Files whose history most resembles past bug-fix activity"
          actions={
            <Link to="../risk">
              <Button size="sm" variant="ghost">
                All files
              </Button>
            </Link>
          }
        >
          {risk.data && !risk.data.available ? (
            <p className="text-sm text-muted">{risk.data.reason}</p>
          ) : topRisk.length === 0 ? (
            <p className="text-sm text-muted">No risk scores available.</p>
          ) : (
            <ul className="space-y-2.5">
              {topRisk.map((file) => (
                <li key={file.file} className="flex items-center gap-3">
                  <FileLink path={file.file} className="min-w-0 flex-1" />
                  <span className={cx("tabular w-12 text-right text-sm font-medium", severityText[riskSeverity((file.risk_probability ?? 0) * 100)])}>
                    {fmtPercent(file.risk_probability)}
                  </span>
                  <LevelBadge level={file.risk_level} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Top contribution opportunities"
        description="CodePulse's calculated guidance on where a contribution could help most"
        actions={
          <Link to="../opportunities">
            <Button size="sm" variant="ghost">
              All opportunities
            </Button>
          </Link>
        }
      >
        {topOpportunities.length === 0 ? (
          <p className="text-sm text-muted">{opportunities.data?.reason ?? "No opportunities were generated."}</p>
        ) : (
          <ul className="divide-y divide-line">
            {topOpportunities.map((item) => (
              <li key={item.file} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 first:pt-0 last:pb-0">
                <div className="min-w-0 flex-1">
                  <FileLink path={item.file} />
                  <p className="truncate text-xs text-muted">{item.title}</p>
                </div>
                <LevelBadge level={item.difficulty} />
                <span className="tabular w-14 text-right text-sm text-muted">{fmtNumber(item.opportunity_score, 1)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
