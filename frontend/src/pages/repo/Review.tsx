import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { EmptyState, LevelBadge, PageLoading, Pagination, Panel, SearchInput, Segmented, Select, cx } from "../../components/ui";
import { FilePath, useOpenFile } from "../../components/FilePath";
import { useReview, useTable } from "../../hooks/queries";
import { fmtNumber } from "../../lib/format";
import type { Finding } from "../../types/api";

type SeverityFilter = "all" | "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
const SEVERITY_RANK: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

function formatValue(value: Finding["value"]) {
  if (typeof value === "number") return Number.isInteger(value) ? fmtNumber(value) : fmtNumber(value, 2);
  return value ?? "—";
}

export default function ReviewPage() {
  const { repoId } = useParams<"repoId">();
  const review = useReview(repoId);
  const { open } = useOpenFile();
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [rule, setRule] = useState("all");
  const findings = useMemo(
    () =>
      review.data && review.data.available
        ? [...review.data.findings].sort((a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9))
        : [],
    [review.data],
  );
  const rules = useMemo(() => {
    const map = new Map<string, string>();
    findings.forEach((finding) => map.set(finding.rule_id, finding.title));
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [findings]);
  const filter = useMemo(
    () => (finding: Finding) => (severity === "all" || finding.severity === severity) && (rule === "all" || finding.rule_id === rule),
    [severity, rule],
  );
  const table = useTable(findings, {
    search: (finding, text) => finding.file.toLowerCase().includes(text) || finding.title.toLowerCase().includes(text),
    filter,
  });

  if (review.isLoading) return <PageLoading />;
  if (review.isError || !review.data) return <EmptyState title="Code review not available">{review.error?.message}</EmptyState>;
  const data = review.data;
  if (!data.available) return <EmptyState title="Code review not available">{data.reason}</EmptyState>;

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <div className="panel px-4 py-3">
          <dt className="text-xs text-muted">Findings</dt>
          <dd className="tabular mt-1 text-2xl font-semibold">{fmtNumber(data.total_findings)}</dd>
          <p className="text-xs text-faint">{fmtNumber(data.files_reviewed)} files reviewed</p>
        </div>
        {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((level) => (
          <div key={level} className="panel px-4 py-3">
            <dt className="text-xs text-muted">
              <LevelBadge level={level} />
            </dt>
            <dd className="tabular mt-1.5 text-2xl font-semibold">{fmtNumber(data.counts[level] ?? 0)}</dd>
          </div>
        ))}
      </dl>

      <Panel
        title="Findings"
        description="Deterministic rules. Thresholds are relative to this repository, with a minimum floor for each rule."
        actions={
          <>
            <SearchInput value={table.query} onChange={table.setQuery} label="Search findings by file or title" placeholder="Search file or title" className="w-60" />
            <Select label="Rule" value={rule} onChange={(event) => { setRule(event.target.value); table.resetPage(); }}>
              <option value="all">All rules</option>
              {rules.map(([id, title]) => (
                <option key={id} value={id}>
                  {title}
                </option>
              ))}
            </Select>
          </>
        }
        bodyClassName="p-0"
      >
        <div className="border-b border-line px-4 py-3">
          <Segmented<SeverityFilter>
            label="Severity"
            value={severity}
            onChange={(value) => {
              setSeverity(value);
              table.resetPage();
            }}
            options={[
              { value: "all", label: "All", count: findings.length },
              { value: "CRITICAL", label: "Critical", count: data.counts.CRITICAL ?? 0 },
              { value: "HIGH", label: "High", count: data.counts.HIGH ?? 0 },
              { value: "MEDIUM", label: "Medium", count: data.counts.MEDIUM ?? 0 },
              { value: "LOW", label: "Low", count: data.counts.LOW ?? 0 },
            ]}
          />
        </div>
        {findings.length === 0 ? (
          <EmptyState icon={<ShieldCheck className="h-6 w-6" />} title="No findings">
            No review rule was triggered in this repository.
          </EmptyState>
        ) : table.total === 0 ? (
          <EmptyState title="No findings match">Try a different filter.</EmptyState>
        ) : (
          <ul>
            {table.rows.map((finding) => (
              <li key={finding.id} className="border-b border-line last:border-0">
                <button
                  type="button"
                  onClick={() => open(finding.file, "review")}
                  className="grid w-full gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-raised/40 md:grid-cols-[96px_minmax(0,1fr)_minmax(0,1.2fr)]"
                >
                  <div>
                    <LevelBadge level={finding.severity} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{finding.title}</p>
                    <FilePath path={finding.file} className="mt-0.5" />
                    <code className="mt-1 block text-2xs text-faint">{finding.rule_id}</code>
                  </div>
                  <div className="min-w-0 text-sm">
                    <p className={cx("tabular text-muted")}>
                      {finding.metric}: <span className="font-medium text-ink">{formatValue(finding.value)}</span>
                    </p>
                    <p className="mt-0.5">{finding.recommendation}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="px-4 pb-3">
          <Pagination page={table.page} pageCount={table.pageCount} total={table.total} pageSize={table.pageSize} onPage={table.setPage} />
        </div>
      </Panel>
    </div>
  );
}
