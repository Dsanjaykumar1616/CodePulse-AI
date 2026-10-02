import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, FileCode2, Folder, FolderOpen } from "lucide-react";
import { Badge, EmptyState, LevelBadge, PageLoading, Panel, SearchInput, Segmented, cx } from "../../components/ui";
import { useOpenFile } from "../../components/FilePath";
import { useOpportunities, useRisk } from "../../hooks/queries";
import { debtSeverity, fmtNumber, fmtPercent, riskSeverity, severityText } from "../../lib/format";
import type { EnrichedOpportunity, FileRow } from "../../types/api";

type Lens = "risk" | "debt" | "opportunities" | "issues" | "connections";

interface TreeNode {
  name: string;
  path: string;
  children: Map<string, TreeNode>;
  files: FileRow[];
  total: number;
  highRisk: number;
  highDebt: number;
  openIssues: number;
}

function buildTree(rows: FileRow[], opps: Map<string, EnrichedOpportunity>): TreeNode {
  const root: TreeNode = { name: "", path: "", children: new Map(), files: [], total: 0, highRisk: 0, highDebt: 0, openIssues: 0 };
  for (const row of rows) {
    const parts = row.file.split("/");
    let node = root;
    const chain = [root];
    for (const part of parts.slice(0, -1)) {
      const path = node.path ? `${node.path}/${part}` : part;
      if (!node.children.has(part)) {
        node.children.set(part, { name: part, path, children: new Map(), files: [], total: 0, highRisk: 0, highDebt: 0, openIssues: 0 });
      }
      node = node.children.get(part)!;
      chain.push(node);
    }
    node.files.push(row);
    const risky = row.risk_level === "High" || row.risk_level === "Critical";
    const debt = row.debt_level === "HIGH" || row.debt_level === "CRITICAL";
    const issues = opps.get(row.file)?.open_issue_count ?? 0;
    for (const item of chain) {
      item.total += 1;
      if (risky) item.highRisk += 1;
      if (debt) item.highDebt += 1;
      if (issues) item.openIssues += 1;
    }
  }
  return root;
}

function FileLens({ row, opp, lens }: { row: FileRow; opp?: EnrichedOpportunity; lens: Lens }) {
  switch (lens) {
    case "risk":
      return row.risk_probability === null ? (
        <span className="text-faint">—</span>
      ) : (
        <span className={severityText[riskSeverity(row.risk_probability * 100)]}>{fmtPercent(row.risk_probability)}</span>
      );
    case "debt":
      return <span className={severityText[debtSeverity(row.debt_score)]}>{fmtNumber(row.debt_score, 0)}</span>;
    case "opportunities":
      return opp ? <LevelBadge level={opp.difficulty} /> : <span className="text-faint">—</span>;
    case "issues":
      return opp?.open_issue_count ? <Badge severity="low">{opp.open_issue_count} open</Badge> : <span className="text-faint">—</span>;
    case "connections":
      return <span className="text-muted">{opp?.connectivity ?? "—"}</span>;
  }
}

function DirectoryLens({ node, lens }: { node: TreeNode; lens: Lens }) {
  const value =
    lens === "risk" ? node.highRisk : lens === "debt" ? node.highDebt : lens === "issues" ? node.openIssues : null;
  if (value === null || value === 0) return null;
  const label = lens === "risk" ? "high risk" : lens === "debt" ? "high debt" : "with open issues";
  return (
    <span className={cx("text-2xs", lens === "issues" ? "text-low" : "text-high")}>
      {value} {label}
    </span>
  );
}

function Tree({
  node,
  depth,
  expanded,
  toggle,
  lens,
  opps,
  filter,
}: {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  toggle: (path: string) => void;
  lens: Lens;
  opps: Map<string, EnrichedOpportunity>;
  filter: string;
}) {
  const { open } = useOpenFile();
  const directories = [...node.children.values()].sort((a, b) => a.name.localeCompare(b.name));
  const files = [...node.files].sort((a, b) => a.file.localeCompare(b.file));
  return (
    <ul role={depth === 0 ? "tree" : "group"} aria-label={depth === 0 ? "Repository files" : undefined}>
      {directories.map((dir) => {
        const isOpen = expanded.has(dir.path) || Boolean(filter);
        return (
          <li key={dir.path} role="treeitem" aria-expanded={isOpen}>
            <button
              type="button"
              onClick={() => toggle(dir.path)}
              className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-sm hover:bg-raised/60"
              style={{ paddingLeft: 6 + depth * 16 }}
            >
              <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 text-faint transition-transform", isOpen && "rotate-90")} aria-hidden />
              {isOpen ? <FolderOpen className="h-4 w-4 shrink-0 text-accent" aria-hidden /> : <Folder className="h-4 w-4 shrink-0 text-accent" aria-hidden />}
              <span className="truncate font-mono text-[12.5px] text-ink">{dir.name}</span>
              <span className="tabular text-2xs text-faint">{dir.total}</span>
              <span className="ml-auto pl-2">
                <DirectoryLens node={dir} lens={lens} />
              </span>
            </button>
            {isOpen && <Tree node={dir} depth={depth + 1} expanded={expanded} toggle={toggle} lens={lens} opps={opps} filter={filter} />}
          </li>
        );
      })}
      {files.map((row) => (
        <li key={row.file} role="treeitem">
          <button
            type="button"
            onClick={() => open(row.file)}
            className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-sm hover:bg-raised/60"
            style={{ paddingLeft: 6 + depth * 16 + 18 }}
          >
            <FileCode2 className="h-4 w-4 shrink-0 text-faint" aria-hidden />
            <span className="truncate font-mono text-[12.5px] text-ink">{row.file.split("/").pop()}</span>
            <span className="tabular ml-auto shrink-0 pl-2 text-xs">
              <FileLens row={row} opp={opps.get(row.file)} lens={lens} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function ExplorerPage() {
  const { repoId } = useParams<"repoId">();
  const risk = useRisk(repoId);
  const opportunities = useOpportunities(repoId);
  const [lens, setLens] = useState<Lens>("opportunities");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const opps = useMemo(
    () => new Map((opportunities.data?.items ?? []).map((item) => [item.file, item])),
    [opportunities.data],
  );
  const rows = useMemo(() => {
    const all = risk.data?.files ?? [];
    const text = query.trim().toLowerCase();
    return text ? all.filter((row) => row.file.toLowerCase().includes(text)) : all;
  }, [risk.data, query]);
  const tree = useMemo(() => buildTree(rows, opps), [rows, opps]);

  if (risk.isLoading) return <PageLoading />;
  if (risk.isError || !risk.data) return <EmptyState title="Files not available">{risk.error?.message}</EmptyState>;

  const toggle = (path: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold">Repository explorer</h2>
        <p className="mt-0.5 text-sm text-muted">
          Browse the analyzed files by directory. Choose what to highlight, and click a file to open its intelligence.
        </p>
      </div>
      <Panel
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Segmented<Lens>
              label="Highlight"
              value={lens}
              onChange={setLens}
              options={[
                { value: "opportunities", label: "Opportunities" },
                { value: "risk", label: "Risk" },
                { value: "debt", label: "Debt" },
                { value: "issues", label: "Issues" },
                { value: "connections", label: "Connections" },
              ]}
            />
            <SearchInput value={query} onChange={setQuery} label="Filter files" placeholder="Filter files" className="w-56" />
          </div>
        }
        title={`${fmtNumber(rows.length)} files`}
        bodyClassName="p-2"
      >
        {rows.length === 0 ? (
          <EmptyState title="No files match">Try a different filter.</EmptyState>
        ) : (
          <div className="scroll-thin max-h-[70vh] overflow-y-auto">
            <Tree node={tree} depth={0} expanded={expanded} toggle={toggle} lens={lens} opps={opps} filter={query.trim()} />
          </div>
        )}
      </Panel>
      <p className="text-xs text-muted">
        Want to see how directories connect?{" "}
        <Link to={`/app/r/${repoId}/architecture`} className="text-accent hover:underline">
          Open the architecture map
        </Link>
        .
      </p>
    </div>
  );
}
