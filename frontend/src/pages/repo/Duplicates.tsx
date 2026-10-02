import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge, Callout, EmptyState, LevelBadge, PageLoading, Pagination, Panel, SearchInput, Segmented } from "../../components/ui";
import { FileLink } from "../../components/FilePath";
import { useDuplicates, useTable } from "../../hooks/queries";
import { fmtNumber, severityOf } from "../../lib/format";
import type { DuplicateGroup } from "../../types/api";

function GroupRow({ group }: { group: DuplicateGroup }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border-b border-line last:border-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-raised/40"
      >
        {open ? <ChevronDown className="h-4 w-4 shrink-0 text-faint" /> : <ChevronRight className="h-4 w-4 shrink-0 text-faint" />}
        <span className="tabular w-16 shrink-0 text-sm font-semibold">{fmtNumber(group.max_similarity, 1)}%</span>
        <LevelBadge level={group.severity} />
        <span className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-muted">
          {group.files.map((file) => file.split("/").pop()).join(", ")}
        </span>
        <span className="tabular shrink-0 text-xs text-faint">
          {group.files.length} files · {group.pair_count} {group.pair_count === 1 ? "pair" : "pairs"}
        </span>
      </button>
      {open && (
        <div className="space-y-3 bg-raised/30 px-4 pb-4 pt-1">
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm" aria-label={`Pairs in duplicate group ${group.id}`}>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th className="py-2 pr-3 font-medium">File A</th>
                  <th className="py-2 pr-3 font-medium">File B</th>
                  <th className="py-2 pr-3 text-right font-medium">Similarity</th>
                  <th className="py-2 text-right font-medium">Matching tokens</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {group.pairs.map((pair) => (
                  <tr key={`${pair.file_a}|${pair.file_b}`} className="border-t border-line">
                    <td className="max-w-[280px] py-2 pr-3">
                      <FileLink path={pair.file_a} />
                    </td>
                    <td className="max-w-[280px] py-2 pr-3">
                      <FileLink path={pair.file_b} />
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <Badge severity={severityOf(pair.similarity_level)}>{fmtNumber(pair.similarity_score, 1)}%</Badge>
                    </td>
                    <td className="py-2 text-right text-muted">{fmtNumber(pair.matching_token_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">Evidence: {group.pairs[0]?.evidence}</p>
        </div>
      )}
    </li>
  );
}

export default function DuplicatesPage() {
  const { repoId } = useParams<"repoId">();
  const duplicates = useDuplicates(repoId);
  const [severity, setSeverity] = useState<"all" | "HIGH" | "MEDIUM" | "LOW">("all");
  const groups = duplicates.data && duplicates.data.available ? duplicates.data.groups : [];
  const filter = useMemo(() => (group: DuplicateGroup) => severity === "all" || group.severity === severity, [severity]);
  const table = useTable(groups, {
    search: (group, text) => group.files.some((file) => file.toLowerCase().includes(text)),
    filter,
    pageSize: 20,
  });

  if (duplicates.isLoading) return <PageLoading />;
  if (duplicates.isError || !duplicates.data) return <EmptyState title="Duplicate data not available">{duplicates.error?.message}</EmptyState>;
  const data = duplicates.data;

  if (!data.available) {
    return (
      <div className="space-y-4">
        <EmptyState title="Duplicate detection not available">{data.reason}</EmptyState>
        <Callout>{data.limitations}</Callout>
      </div>
    );
  }

  const countOf = (level: string) => groups.filter((group) => group.severity === level).length;

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-3 gap-3">
        {[
          ["Duplicate groups", data.duplicate_groups],
          ["Similar file pairs", data.pair_count],
          ["High-similarity pairs (90%+)", data.high_similarity_pairs],
        ].map(([label, value]) => (
          <div key={label as string} className="panel px-4 py-3">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="tabular mt-1 text-2xl font-semibold">{fmtNumber(value as number)}</dd>
          </div>
        ))}
      </dl>

      <Callout title="What this shows">{data.limitations}</Callout>

      <Panel
        title="Duplicate groups"
        description="Files are grouped when they are connected by at least one similar pair (75%+ similarity)."
        actions={<SearchInput value={table.query} onChange={table.setQuery} label="Search files" placeholder="Search files" className="w-56" />}
        bodyClassName="p-0"
      >
        {groups.length === 0 ? (
          <EmptyState title="No significant duplicate groups detected">No pair of files reached the 75% similarity threshold.</EmptyState>
        ) : (
          <>
            <div className="border-b border-line px-4 py-3">
              <Segmented
                label="Severity"
                value={severity}
                onChange={(value) => {
                  setSeverity(value);
                  table.resetPage();
                }}
                options={[
                  { value: "all", label: "All", count: groups.length },
                  { value: "HIGH", label: "High (90%+)", count: countOf("HIGH") },
                  { value: "MEDIUM", label: "Medium (80%+)", count: countOf("MEDIUM") },
                  { value: "LOW", label: "Low (75%+)", count: countOf("LOW") },
                ]}
              />
            </div>
            {table.total === 0 ? (
              <EmptyState title="No groups match">Try a different search or filter.</EmptyState>
            ) : (
              <ul>
                {table.rows.map((group) => (
                  <GroupRow key={group.id} group={group} />
                ))}
              </ul>
            )}
            <div className="px-4 pb-3">
              <Pagination page={table.page} pageCount={table.pageCount} total={table.total} pageSize={table.pageSize} onPage={table.setPage} />
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
