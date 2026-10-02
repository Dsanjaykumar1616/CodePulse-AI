import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Callout, EmptyState, LevelBadge, PageLoading, Pagination, Panel, SearchInput, Segmented, Select, cx } from "../../components/ui";
import { cellClass, rowClass, SortHeader, TableShell, theadClass } from "../../components/data";
import { FilePath, useOpenFile } from "../../components/FilePath";
import { RISK_SIGNAL_NOTE } from "../../components/FileIntelligence";
import { useRisk, useTable } from "../../hooks/queries";
import { fmtNumber, fmtPercent, riskSeverity, severityText } from "../../lib/format";
import type { FileRow, Risk } from "../../types/api";

type LevelFilter = "all" | "Critical" | "High" | "Medium" | "Low";

function ModelPanel({ risk }: { risk: Risk }) {
  if (!risk.available) {
    return (
      <Callout tone="warning" title="Historical risk signal not available">
        {risk.reason} File metrics are still shown below.
      </Callout>
    );
  }
  const distribution = risk.class_distribution ?? {};
  const withHistory = distribution["1"] ?? 0;
  const without = distribution["0"] ?? 0;
  return (
    <Panel title="How the risk signal is produced" description={risk.label_definition}>
      <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[460px] text-sm" aria-label="Model evaluation">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="py-1.5 pr-3 font-medium">Model</th>
                {["Accuracy", "Precision", "Recall", "F1", "ROC-AUC"].map((label) => (
                  <th key={label} className="py-1.5 pr-3 text-right font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular">
              {risk.models.map((model) => (
                <tr key={model.model} className={cx("border-t border-line", model.selected && "font-medium")}>
                  <td className="py-1.5 pr-3">
                    {model.model}
                    {model.selected && <span className="ml-2 text-xs text-accent">selected</span>}
                  </td>
                  {[model.accuracy, model.precision, model.recall, model.f1, model.roc_auc].map((value, index) => (
                    <td key={index} className="py-1.5 pr-3 text-right">
                      {value === null ? "—" : value.toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">
            Evaluated on a held-out split of this repository's files. The model with the best F1 score is used. Small
            repositories give unstable scores.
          </p>
        </div>
        {(withHistory > 0 || without > 0) && (
          <dl className="grid grid-cols-2 gap-4 self-start lg:grid-cols-1">
            <div>
              <dt className="text-xs text-muted">Files with bug-fix history</dt>
              <dd className="tabular text-lg font-semibold">{withHistory}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Files without</dt>
              <dd className="tabular text-lg font-semibold">{without}</dd>
            </div>
          </dl>
        )}
      </div>
    </Panel>
  );
}

export default function RiskPage() {
  const { repoId } = useParams<"repoId">();
  const risk = useRisk(repoId);
  const { open } = useOpenFile();
  const [level, setLevel] = useState<LevelFilter>("all");
  const [language, setLanguage] = useState("all");
  const rows = risk.data?.files ?? [];

  const languages = useMemo(() => [...new Set(rows.map((row) => row.language ?? "Other"))].sort(), [rows]);
  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    rows.forEach((row) => {
      if (row.risk_level) result[row.risk_level] = (result[row.risk_level] ?? 0) + 1;
    });
    return result;
  }, [rows]);

  const filter = useMemo(
    () => (row: FileRow) =>
      (level === "all" || row.risk_level === level) && (language === "all" || (row.language ?? "Other") === language),
    [level, language],
  );
  const table = useTable(rows, {
    search: (row, text) => row.file.toLowerCase().includes(text),
    initialSort: { key: "risk_probability", dir: "desc" },
    filter,
  });

  if (risk.isLoading) return <PageLoading />;
  if (risk.isError || !risk.data) return <EmptyState title="Risk data not available">{risk.error?.message}</EmptyState>;

  return (
    <div className="space-y-6">
      <ModelPanel risk={risk.data} />

      <Panel
        title="Risky files"
        description={RISK_SIGNAL_NOTE}
        actions={
          <>
            <SearchInput value={table.query} onChange={table.setQuery} label="Search files" placeholder="Search files" className="w-56" />
            <Select label="Language" value={language} onChange={(event) => { setLanguage(event.target.value); table.resetPage(); }}>
              <option value="all">All languages</option>
              {languages.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </>
        }
      >
        {risk.data.available && (
          <div className="mb-3">
            <Segmented<LevelFilter>
              label="Risk level"
              value={level}
              onChange={(value) => {
                setLevel(value);
                table.resetPage();
              }}
              options={[
                { value: "all", label: "All", count: rows.length },
                ...(["Critical", "High", "Medium", "Low"] as const).map((item) => ({ value: item, label: item, count: counts[item] ?? 0 })),
              ]}
            />
          </div>
        )}
        {table.total === 0 ? (
          <EmptyState title="No files match">Try a different search or filter.</EmptyState>
        ) : (
          <>
            <TableShell label="Risky files">
              <thead className={theadClass}>
                <tr>
                  <SortHeader label="File" column="file" sort={table.sort} onSort={table.toggleSort} />
                  <SortHeader label="Risk" column="risk_probability" sort={table.sort} onSort={table.toggleSort} align="right" title="Historical risk signal" />
                  <th scope="col" className="px-3 py-2 font-medium text-muted">Level</th>
                  <SortHeader label="Complexity" column="complexity" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Churn" column="code_churn" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Maintainability" column="maintainability" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Bug-fix commits" column="bug_fix_commits" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Debt" column="debt_score" sort={table.sort} onSort={table.toggleSort} align="right" />
                </tr>
              </thead>
              <tbody className="tabular">
                {table.rows.map((row) => (
                  <tr
                    key={row.file}
                    className={cx(rowClass, "cursor-pointer")}
                    onClick={() => open(row.file)}
                    onKeyDown={(event) => event.key === "Enter" && open(row.file)}
                    tabIndex={0}
                    aria-label={`Open ${row.file}`}
                  >
                    <td className={cx(cellClass, "max-w-[360px]")}>
                      <FilePath path={row.file} />
                    </td>
                    <td className={cx(cellClass, "text-right font-medium", severityText[riskSeverity(row.risk_probability === null ? null : row.risk_probability * 100)])}>
                      {fmtPercent(row.risk_probability)}
                    </td>
                    <td className={cellClass}>
                      <LevelBadge level={row.risk_level} fallback="—" />
                    </td>
                    <td className={cx(cellClass, "text-right")}>{fmtNumber(row.complexity)}</td>
                    <td className={cx(cellClass, "text-right")}>{fmtNumber(row.code_churn)}</td>
                    <td className={cx(cellClass, "text-right")}>{fmtNumber(row.maintainability, 1)}</td>
                    <td className={cx(cellClass, "text-right")}>{fmtNumber(row.bug_fix_commits)}</td>
                    <td className={cx(cellClass, "text-right")}>{fmtNumber(row.debt_score, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
            <Pagination page={table.page} pageCount={table.pageCount} total={table.total} pageSize={table.pageSize} onPage={table.setPage} />
          </>
        )}
      </Panel>
    </div>
  );
}
