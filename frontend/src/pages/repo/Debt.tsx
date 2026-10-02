import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import {
  Callout,
  EmptyState,
  LevelBadge,
  PageLoading,
  Pagination,
  Panel,
  SearchInput,
  Segmented,
  cx,
} from "../../components/ui";
import { cellClass, rowClass, ScoreRing, SortHeader, TableShell, theadClass } from "../../components/data";
import { FilePath, useOpenFile } from "../../components/FilePath";
import { useDebt, useTable } from "../../hooks/queries";
import { debtSeverity, fmtNumber, severityOf, severityText } from "../../lib/format";
import type { DebtLevel, DebtRow } from "../../types/api";

const LEVELS: DebtLevel[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const tooltipStyle = {
  background: "rgb(var(--surface))",
  border: "1px solid rgb(var(--line))",
  borderRadius: 6,
  fontSize: 12,
  color: "rgb(var(--ink))",
};

function Component({ value }: { value: number | null }) {
  if (value === null) return <span className="text-faint" title="Not available for this file">—</span>;
  return <span className={value >= 75 ? "font-medium text-ink" : "text-muted"}>{fmtNumber(value, 0)}</span>;
}

export default function DebtPage() {
  const { repoId } = useParams<"repoId">();
  const debt = useDebt(repoId);
  const { open } = useOpenFile();
  const [level, setLevel] = useState<"all" | DebtLevel>("all");
  const rows: DebtRow[] = debt.data && debt.data.available ? debt.data.files : [];
  const filter = useMemo(() => (row: DebtRow) => level === "all" || row.technical_debt_level === level, [level]);
  const table = useTable(rows, {
    search: (row, text) => row.file.toLowerCase().includes(text),
    initialSort: { key: "technical_debt_score", dir: "desc" },
    filter,
  });

  if (debt.isLoading) return <PageLoading />;
  if (debt.isError || !debt.data) return <EmptyState title="Technical debt not available">{debt.error?.message}</EmptyState>;
  const data = debt.data;
  if (!data.available) return <EmptyState title="Technical debt not available">{data.reason}</EmptyState>;

  const distribution = LEVELS.map((item) => ({ level: item, count: data.distribution[item] ?? 0 }));
  const top = rows.slice(0, 10).map((row) => ({ file: row.file, label: row.file.split("/").pop() ?? row.file, score: row.technical_debt_score }));
  const evidenceCounts = new Map<string, number>();
  rows.forEach((row) => row.debt_reasons.forEach((reason) => evidenceCounts.set(reason, (evidenceCounts.get(reason) ?? 0) + 1)));
  const evidence = [...evidenceCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[auto_1fr_1fr]">
        <section className="panel flex items-center gap-5 p-5">
          <ScoreRing
            value={data.repository_debt_score}
            severity={debtSeverity(data.repository_debt_score)}
            label="Repository technical debt score"
            caption="debt"
          />
          <div>
            <p className="text-xs text-muted">Repository debt</p>
            <div className="mt-1">
              <LevelBadge level={data.debt_level} />
            </div>
            <p className="mt-2 max-w-[12rem] text-xs text-muted">
              {fmtNumber(data.high_critical_percentage, 0)}% of files are high or critical. Higher scores mean more debt.
            </p>
          </div>
        </section>

        <Panel title="Distribution" description="Files per debt level">
          <div className="h-40" role="img" aria-label="Files per technical debt level">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={distribution} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <XAxis dataKey="level" tick={{ fill: "rgb(var(--muted))", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "rgb(var(--faint))", fontSize: 11 }} axisLine={false} tickLine={false} />
                <ChartTooltip cursor={{ fill: "rgb(var(--raised))" }} contentStyle={tooltipStyle} formatter={(value: number) => [`${value} files`, "Files"]} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {distribution.map((item) => (
                    <Cell key={item.level} fill={`rgb(var(--sev-${severityOf(item.level)}))`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Most common evidence" description="Reasons recorded across files">
          {evidence.length === 0 ? (
            <p className="text-sm text-muted">No component reached the evidence threshold.</p>
          ) : (
            <ul className="space-y-2">
              {evidence.map(([reason, count]) => (
                <li key={reason} className="flex items-baseline justify-between gap-3 text-sm">
                  <span>{reason}</span>
                  <span className="tabular shrink-0 text-xs text-muted">{count} files</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {!data.duplication_available && (
        <Callout>No file had duplication data, so duplication did not contribute to these scores and its weight was spread across the other components.</Callout>
      )}

      <Panel title="Top debt-prone files" description="Click a bar to inspect the file">
        <div style={{ height: Math.max(160, top.length * 30) }} role="img" aria-label="Top ten files by technical debt score">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top} layout="vertical" margin={{ top: 0, right: 24, left: 8, bottom: 0 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fill: "rgb(var(--faint))", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="label"
                width={170}
                tick={{ fill: "rgb(var(--ink))", fontSize: 12, fontFamily: "JetBrains Mono" }}
                axisLine={false}
                tickLine={false}
              />
              <ChartTooltip
                cursor={{ fill: "rgb(var(--raised))" }}
                contentStyle={tooltipStyle}
                formatter={(value: number) => [fmtNumber(value, 1), "Debt score"]}
                labelFormatter={(_: string, payload: { payload?: { file: string } }[]) => payload?.[0]?.payload?.file ?? ""}
              />
              <Bar
                dataKey="score"
                radius={[0, 3, 3, 0]}
                barSize={16}
                className="cursor-pointer"
                onClick={(entry: { file: string }) => open(entry.file, "debt")}
              >
                {top.map((item) => (
                  <Cell key={item.file} fill={`rgb(var(--sev-${debtSeverity(item.score)}))`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel
        title="Files"
        description="Component scores are 0–100 and relative to this repository. Weights: complexity 35%, historical risk 25%, duplication 20%, maintainability 10%, churn 10%."
        actions={<SearchInput value={table.query} onChange={table.setQuery} label="Search files" placeholder="Search files" className="w-56" />}
      >
        <div className="mb-3">
          <Segmented<"all" | DebtLevel>
            label="Debt level"
            value={level}
            onChange={(value) => {
              setLevel(value);
              table.resetPage();
            }}
            options={[
              { value: "all", label: "All", count: rows.length },
              ...LEVELS.slice().reverse().map((item) => ({ value: item, label: item.charAt(0) + item.slice(1).toLowerCase(), count: data.distribution[item] ?? 0 })),
            ]}
          />
        </div>
        {table.total === 0 ? (
          <EmptyState title="No files match">Try a different search or filter.</EmptyState>
        ) : (
          <>
            <TableShell label="Technical debt by file">
              <thead className={theadClass}>
                <tr>
                  <SortHeader label="File" column="file" sort={table.sort} onSort={table.toggleSort} />
                  <SortHeader label="Debt" column="technical_debt_score" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <th scope="col" className="px-3 py-2 font-medium text-muted">Category</th>
                  <SortHeader label="Complexity" column="complexity_component" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Risk" column="ml_component" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Duplication" column="duplication_component" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Maintainability" column="maintainability_component" sort={table.sort} onSort={table.toggleSort} align="right" />
                  <SortHeader label="Churn" column="churn_component" sort={table.sort} onSort={table.toggleSort} align="right" />
                </tr>
              </thead>
              <tbody className="tabular">
                {table.rows.map((row) => (
                  <tr
                    key={row.file}
                    className={cx(rowClass, "cursor-pointer")}
                    onClick={() => open(row.file, "debt")}
                    onKeyDown={(event) => event.key === "Enter" && open(row.file, "debt")}
                    tabIndex={0}
                    aria-label={`Open ${row.file}`}
                  >
                    <td className={cx(cellClass, "max-w-[340px]")}>
                      <FilePath path={row.file} />
                    </td>
                    <td className={cx(cellClass, "text-right font-medium", severityText[debtSeverity(row.technical_debt_score)])}>
                      {fmtNumber(row.technical_debt_score, 1)}
                    </td>
                    <td className={cellClass}>
                      <LevelBadge level={row.technical_debt_level} />
                    </td>
                    <td className={cx(cellClass, "text-right")}><Component value={row.complexity_component} /></td>
                    <td className={cx(cellClass, "text-right")}><Component value={row.ml_component} /></td>
                    <td className={cx(cellClass, "text-right")}><Component value={row.duplication_component} /></td>
                    <td className={cx(cellClass, "text-right")}><Component value={row.maintainability_component} /></td>
                    <td className={cx(cellClass, "text-right")}><Component value={row.churn_component} /></td>
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
