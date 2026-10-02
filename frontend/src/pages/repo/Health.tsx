import { useParams } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { EmptyState, NotAvailable, PageLoading, Panel, Progress } from "../../components/ui";
import { ScoreRing } from "../../components/data";
import { FileLink } from "../../components/FilePath";
import { RISK_SIGNAL_NOTE } from "../../components/FileIntelligence";
import { useHealth } from "../../hooks/queries";
import { fmtNumber, fmtPercent, scoreSeverity, severityOf } from "../../lib/format";
import type { HealthAvailable, TopFile } from "../../types/api";

function TopFiles({ title, files, format }: { title: string; files: TopFile[]; format: (value: number) => string }) {
  return (
    <div className="min-w-0">
      <h4 className="mb-1.5 text-xs text-muted">{title}</h4>
      {files.length === 0 ? (
        <p className="text-sm text-faint">None</p>
      ) : (
        <ul className="space-y-1.5">
          {files.map((item) => (
            <li key={item.file} className="flex items-center gap-3">
              <FileLink path={item.file} className="min-w-0 flex-1" />
              <span className="tabular shrink-0 text-sm text-muted">{format(item.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Average({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="tabular text-base font-semibold">{value}</dd>
    </div>
  );
}

const RISK_ORDER = ["Low", "Medium", "High", "Critical"];

function Evidence({ data }: { data: HealthAvailable }) {
  const { evidence } = data;
  const riskCounts = RISK_ORDER.map((level) => ({ level, count: evidence.defect_risk.risk_level_counts[level] ?? 0 }));
  const hasRisk = riskCounts.some((item) => item.count > 0);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Panel title="Code quality" description="Complexity, nesting depth and comment ratio across files">
        <dl className="mb-4 grid grid-cols-3 gap-3">
          <Average label="Avg. complexity" value={fmtNumber(evidence.code_quality.average_complexity, 1)} />
          <Average label="Avg. nesting" value={fmtNumber(evidence.code_quality.average_nesting_depth, 1)} />
          <Average
            label="Avg. comment ratio"
            value={evidence.code_quality.average_comment_ratio === null ? "—" : fmtPercent(evidence.code_quality.average_comment_ratio)}
          />
        </dl>
        <div className="grid gap-4 sm:grid-cols-2">
          <TopFiles title="Most complex" files={evidence.code_quality.most_complex_files} format={(v) => fmtNumber(v)} />
          <TopFiles title="Deepest nesting" files={evidence.code_quality.deepest_nesting_files} format={(v) => fmtNumber(v)} />
        </div>
      </Panel>

      <Panel title="Git stability" description="Churn and historical bug-fix commits">
        <dl className="mb-4 grid grid-cols-2 gap-3">
          <Average label="Total churn (lines)" value={fmtNumber(evidence.git_stability.total_churn)} />
          <Average label="Files with bug-fix history" value={fmtNumber(evidence.git_stability.files_with_bug_fix_activity)} />
        </dl>
        <div className="grid gap-4 sm:grid-cols-2">
          <TopFiles title="Highest churn" files={evidence.git_stability.highest_churn_files} format={(v) => fmtNumber(v)} />
          <TopFiles title="Most bug-fix commits" files={evidence.git_stability.most_bug_fix_activity} format={(v) => fmtNumber(v)} />
        </div>
      </Panel>

      <Panel title="Historical risk" description={RISK_SIGNAL_NOTE}>
        {hasRisk ? (
          <>
            <dl className="mb-3">
              <Average
                label="Average signal"
                value={evidence.defect_risk.average_signal === null ? "—" : fmtPercent(evidence.defect_risk.average_signal, 1)}
              />
            </dl>
            <div className="h-36" role="img" aria-label="Number of files at each historical risk level">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskCounts} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <XAxis dataKey="level" tick={{ fill: "rgb(var(--muted))", fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fill: "rgb(var(--faint))", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <ChartTooltip
                    cursor={{ fill: "rgb(var(--raised))" }}
                    contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 6, fontSize: 12 }}
                    formatter={(value: number) => [`${value} files`, "Files"]}
                  />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {riskCounts.map((item) => (
                      <Cell key={item.level} fill={`rgb(var(--sev-${severityOf(item.level)}))`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4">
              <TopFiles title="Highest signal" files={evidence.defect_risk.highest_signal_files} format={(v) => fmtPercent(v)} />
            </div>
          </>
        ) : (
          <NotAvailable reason={data.components.find((c) => c.key === "defect_risk")?.reason} />
        )}
      </Panel>

      <Panel title="Maintainability" description="Maintainability index (Python files only)">
        {evidence.maintainability.average_index === null ? (
          <NotAvailable reason={data.components.find((c) => c.key === "maintainability")?.reason} />
        ) : (
          <>
            <dl className="mb-4">
              <Average label="Average index" value={fmtNumber(evidence.maintainability.average_index, 1)} />
            </dl>
            <TopFiles
              title="Lowest maintainability"
              files={evidence.maintainability.lowest_maintainability_files}
              format={(v) => fmtNumber(v, 1)}
            />
          </>
        )}
      </Panel>
    </div>
  );
}

export default function HealthPage() {
  const { repoId } = useParams<"repoId">();
  const health = useHealth(repoId);
  if (health.isLoading) return <PageLoading />;
  if (health.isError || !health.data) return <EmptyState title="Health not available">{health.error?.message}</EmptyState>;
  const data = health.data;
  if (!data.available) return <EmptyState title="Health score not available">{data.reason}</EmptyState>;

  const weakest = data.components
    .filter((component) => component.available && component.value !== null)
    .sort((a, b) => (a.value ?? 0) - (b.value ?? 0))[0];

  return (
    <div className="space-y-6">
      <section className="panel grid gap-6 p-5 md:grid-cols-[auto_1fr] md:items-center">
        <div className="flex items-center gap-5">
          <ScoreRing value={data.overall_score} severity={scoreSeverity(data.overall_score)} label="Overall health score" caption="of 100" size={128} />
          <div>
            <h2 className="text-lg font-semibold">{data.health_level ?? "Health"}</h2>
            <p className="mt-1 max-w-[16rem] text-sm text-muted">
              {weakest ? `${weakest.label} is the lowest component and pulls the score down most.` : "Overall repository health."}
            </p>
          </div>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2">
          {data.components.map((component) => (
            <li key={component.key} className="min-w-0">
              <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{component.label}</span>
                {component.available && component.value !== null ? (
                  <span className="tabular">
                    {fmtNumber(component.value, 1)}
                    <span className="ml-1.5 text-xs text-faint">
                      weight {Math.round((component.effective_weight ?? component.weight) * 100)}%
                    </span>
                  </span>
                ) : (
                  <span className="text-xs text-faint">Not available</span>
                )}
              </div>
              {component.available && component.value !== null ? (
                <Progress value={component.value} severity={scoreSeverity(component.value)} label={component.label} />
              ) : (
                <div className="h-1.5 rounded-full bg-raised" />
              )}
              <p className="mt-1 text-xs text-muted">{component.reason ?? component.description}</p>
            </li>
          ))}
        </ul>
      </section>

      <div>
        <h2 className="text-base font-semibold">What is affecting the score?</h2>
        <p className="mt-0.5 text-sm text-muted">
          The files and averages behind each component. Scores are calculated by the analysis engine; unavailable components
          are left out and the remaining weights are rescaled.
        </p>
      </div>
      <Evidence data={data} />
    </div>
  );
}
