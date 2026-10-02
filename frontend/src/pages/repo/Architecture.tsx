import { memo, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlowProvider,
  useReactFlow,
} from "reactflow";
import "reactflow/dist/style.css";
import { Compass, Crosshair, FileSearch, FolderOpen, Info, Network, Radar, X } from "lucide-react";
import {
  Badge,
  Button,
  Callout,
  EmptyState,
  Explainer,
  LevelBadge,
  PageLoading,
  Panel,
  Select,
  Spinner,
  Tabs,
  cx,
} from "../../components/ui";
import { FileLink, FilePath, useOpenFile } from "../../components/FilePath";
import { useArchitecture, useFileIntelligence, useFileList, useGuide } from "../../hooks/queries";
import { layeredLayout } from "../../lib/graphLayout";
import { capitalize, fmtNumber, fmtPercent, severityOf } from "../../lib/format";
import type { AnnotatedNode, ArchitectureAvailable, DirectoryGroup, GraphNode, Guide } from "../../types/api";

type Mode = "overview" | "components" | "dependencies" | "impact" | "contribution";
const MODES: { value: Mode; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "components", label: "Components" },
  { value: "dependencies", label: "Dependencies" },
  { value: "impact", label: "Impact" },
  { value: "contribution", label: "Contribution view" },
];

const severityColor = (level: string | null | undefined) => {
  const severity = severityOf(level ?? null);
  return severity === "none" ? "rgb(var(--line))" : `rgb(var(--sev-${severity}))`;
};

const tooltipEdge = (count: number) => `${count} import${count === 1 ? "" : "s"}`;

// ---------------------------------------------------------------------------
// Nodes
// ---------------------------------------------------------------------------

interface FileNodeData {
  node: AnnotatedNode;
  state: "normal" | "selected" | "neighbour" | "dimmed";
  isFocus: boolean;
  highlight: boolean;
  mode: Mode;
}

const FileNode = memo(function FileNode({ data }: { data: FileNodeData }) {
  const { node, state, isFocus, highlight, mode } = data;
  const width = 168 + Math.round(node.centrality * 64);
  const central = node.connectivity === "Highly connected";
  const showOpportunity = mode === "contribution" && node.opportunity;
  return (
    <div
      className={cx(
        "rounded border bg-surface px-2.5 py-1.5 text-left transition-opacity",
        state === "dimmed" && "opacity-25",
        mode === "contribution" && !highlight && state === "normal" && "opacity-40",
        (state === "selected" || isFocus) && "ring-2 ring-accent ring-offset-1 ring-offset-canvas",
      )}
      style={{
        width,
        borderColor: central ? "rgb(var(--muted))" : "rgb(var(--line))",
        borderWidth: central ? 2 : 1,
        borderLeftWidth: 4,
        borderLeftColor: severityColor(node.risk_level ?? node.debt_level),
      }}
      title={node.id}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
      <div className="flex items-center gap-1.5">
        <span className={cx("min-w-0 flex-1 truncate font-mono text-[12px] text-ink", central && "font-medium")}>{node.label}</span>
        {showOpportunity && (
          <span
            className="shrink-0 rounded-[3px] px-1 text-[9px] font-semibold"
            style={{ background: `${severityColor(node.opportunity!.difficulty)}`, color: "white" }}
          >
            {node.opportunity!.difficulty.slice(0, 3)}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 text-[10px] text-faint">
        <span className="truncate">{node.directory}</span>
        <span className="tabular shrink-0">
          {node.incoming} in · {node.outgoing} out
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-faint" />
    </div>
  );
});

interface GroupNodeData {
  group: DirectoryGroup;
  selected: boolean;
  maxFiles: number;
}

const GroupNode = memo(function GroupNode({ data }: { data: GroupNodeData }) {
  const { group, selected, maxFiles } = data;
  const width = 190 + Math.round((group.file_count / Math.max(1, maxFiles)) * 70);
  return (
    <div
      className={cx(
        "rounded-md border-2 bg-surface px-3 py-2 text-left",
        selected ? "border-accent" : "border-line",
      )}
      style={{ width }}
      title={group.id}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-faint" />
      <div className="flex items-center gap-1.5">
        <FolderOpen className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
        <span className="truncate font-mono text-[12px] font-medium text-ink">{group.label}/</span>
      </div>
      <p className="mt-0.5 truncate text-[10.5px] text-muted">{group.name_hint ?? "Directory"}</p>
      <p className="tabular text-[10px] text-faint">
        {group.file_count} files · {group.opportunities} opportunities
        {group.high_risk_files ? ` · ${group.high_risk_files} high risk` : ""}
      </p>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-faint" />
    </div>
  );
});

const nodeTypes = { file: FileNode, group: GroupNode };

function FitOnChange({ signature }: { signature: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const timer = setTimeout(() => fitView({ padding: 0.15, duration: 250 }), 40);
    return () => clearTimeout(timer);
  }, [signature, fitView]);
  return null;
}

// ---------------------------------------------------------------------------
// Graphs
// ---------------------------------------------------------------------------

function FileGraph({
  data,
  selected,
  onSelect,
  mode,
}: {
  data: ArchitectureAvailable;
  selected: string | null;
  onSelect: (id: string | null) => void;
  mode: Mode;
}) {
  const positions = useMemo(() => layeredLayout(data.nodes, data.edges), [data.nodes, data.edges]);
  const neighbours = useMemo(() => {
    if (!selected) return null;
    const set = new Set<string>([selected]);
    for (const edge of data.edges) {
      if (edge.source === selected) set.add(edge.target);
      if (edge.target === selected) set.add(edge.source);
    }
    return set;
  }, [selected, data.edges]);

  const nodes = useMemo(
    () =>
      data.nodes.map((node) => {
        const position = positions.get(node.id) ?? { x: 0, y: 0 };
        const state: FileNodeData["state"] = !neighbours
          ? "normal"
          : node.id === selected
            ? "selected"
            : neighbours.has(node.id)
              ? "neighbour"
              : "dimmed";
        return {
          id: node.id,
          type: "file",
          position: { x: position.x, y: position.y },
          data: {
            node,
            state,
            isFocus: node.id === data.focus,
            highlight: Boolean(node.opportunity && node.opportunity.rank <= 25),
            mode,
          } satisfies FileNodeData,
        };
      }),
    [data.nodes, data.focus, positions, neighbours, selected, mode],
  );

  const edges = useMemo(
    () =>
      data.edges.map((edge) => {
        const outgoing = edge.source === selected;
        const incoming = edge.target === selected;
        const active = outgoing || incoming;
        const color = outgoing ? "rgb(var(--accent))" : incoming ? "rgb(var(--sev-medium))" : undefined;
        return {
          id: `${edge.source}->${edge.target}`,
          source: edge.source,
          target: edge.target,
          animated: active,
          style: { stroke: color, strokeWidth: active ? 2 : 1, opacity: selected && !active ? 0.12 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: color ?? "rgb(var(--faint))" },
        };
      }),
    [data.edges, selected],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_: unknown, node: { id: string }) => onSelect(node.id === selected ? null : node.id)}
      onPaneClick={() => onSelect(null)}
      minZoom={0.1}
      maxZoom={2}
      fitView
      onlyRenderVisibleElements
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={20} size={1} color="rgb(var(--line))" />
      <Controls showInteractive={false} position="bottom-left" />
      <MiniMap
        pannable
        zoomable
        position="bottom-right"
        nodeColor={(node: { data: FileNodeData }) => severityColor(node.data.node.risk_level ?? node.data.node.debt_level)}
        maskColor="rgb(var(--canvas) / 0.7)"
        className="!hidden md:!block"
      />
      <FitOnChange signature={`${mode}|${data.focus ?? ""}|${data.directory ?? ""}|${data.nodes.length}`} />
    </ReactFlow>
  );
}

function GroupGraph({
  guide,
  selected,
  onSelect,
  onOpen,
}: {
  guide: Guide;
  selected: string | null;
  onSelect: (id: string | null) => void;
  onOpen: (id: string) => void;
}) {
  const groups = guide.groups.groups;
  const maxFiles = Math.max(1, ...groups.map((group) => group.file_count));
  const pseudo = useMemo<GraphNode[]>(
    () =>
      groups.map((group) => ({
        id: group.id,
        label: group.label,
        directory: group.id,
        language: null,
        incoming: group.incoming,
        outgoing: group.outgoing,
        total: group.incoming + group.outgoing,
        centrality: 0,
        risk_probability: null,
        risk_level: null,
        debt_score: null,
        debt_level: null,
      })),
    [groups],
  );
  const positions = useMemo(() => layeredLayout(pseudo, guide.groups.edges), [pseudo, guide.groups.edges]);
  const maxCount = Math.max(1, ...guide.groups.edges.map((edge) => edge.count));
  const nodes = groups.map((group) => ({
    id: group.id,
    type: "group",
    position: positions.get(group.id) ?? { x: 0, y: 0 },
    data: { group, selected: group.id === selected, maxFiles } satisfies GroupNodeData,
  }));
  const edges = guide.groups.edges.map((edge) => {
    const active = selected !== null && (edge.source === selected || edge.target === selected);
    return {
      id: `${edge.source}->${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: tooltipEdge(edge.count),
      labelStyle: { fill: "rgb(var(--muted))", fontSize: 10 },
      labelBgStyle: { fill: "rgb(var(--surface))" },
      style: {
        strokeWidth: 1 + (3 * edge.count) / maxCount,
        stroke: active ? "rgb(var(--accent))" : undefined,
        opacity: selected && !active ? 0.2 : 1,
      },
      markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: active ? "rgb(var(--accent))" : "rgb(var(--faint))" },
    };
  });
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_: unknown, node: { id: string }) => onSelect(node.id === selected ? null : node.id)}
      onNodeDoubleClick={(_: unknown, node: { id: string }) => onOpen(node.id)}
      onPaneClick={() => onSelect(null)}
      minZoom={0.2}
      maxZoom={1.8}
      fitView
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={20} size={1} color="rgb(var(--line))" />
      <Controls showInteractive={false} position="bottom-left" />
      <FitOnChange signature={`groups|${groups.length}`} />
    </ReactFlow>
  );
}

// ---------------------------------------------------------------------------
// Side panels
// ---------------------------------------------------------------------------

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="tabular text-right">{children}</dd>
    </div>
  );
}

function whyFileMatters(node: AnnotatedNode): string {
  const parts: string[] = [];
  if (node.incoming >= 3) {
    parts.push(`It is used by ${node.incoming} local files, so changes here may affect several parts of the repository.`);
  } else if (node.incoming > 0) {
    parts.push(`It is used by ${node.incoming} local file${node.incoming === 1 ? "" : "s"}.`);
  }
  if (node.outgoing >= 3) {
    parts.push(`It imports ${node.outgoing} local files, so reading it shows how those parts fit together.`);
  }
  if (node.roles.includes("Possible entry point")) {
    parts.push("Nothing in the repository imports it, which is typical of an entry point or script.");
  }
  if (node.total === 0) {
    parts.push("Static analysis found no imports to or from other repository files.");
  }
  if (node.risk_level === "High" || node.risk_level === "Critical") {
    parts.push(`Its history has a ${node.risk_level.toLowerCase()} historical risk signal.`);
  }
  return parts.join(" ") || "It has few dependency relationships, so changes here are likely to stay local.";
}

function NodePanel({
  node,
  data,
  repoId,
  onFocus,
  onImpact,
  onClose,
}: {
  node: AnnotatedNode;
  data: ArchitectureAvailable;
  repoId: string;
  onFocus: (id: string) => void;
  onImpact: (id: string) => void;
  onClose: () => void;
}) {
  const { open } = useOpenFile();
  const intel = useFileIntelligence(repoId, node.id);
  const incoming = data.edges.filter((edge) => edge.target === node.id).map((edge) => edge.source);
  const outgoing = data.edges.filter((edge) => edge.source === node.id).map((edge) => edge.target);
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-sm font-medium">{node.label}</p>
          <FilePath path={node.id} className="text-xs" />
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge>{node.connectivity}</Badge>
            {node.roles.map((role) => (
              <Badge key={role}>{role}</Badge>
            ))}
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Clear selection">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div>
        <h4 className="text-xs font-medium text-muted">Why this file matters</h4>
        <p className="mt-1 text-sm">{whyFileMatters(node)}</p>
      </div>

      <dl className="divide-y divide-line">
        <Row label="Used by">{node.incoming} files</Row>
        <Row label="Depends on">{node.outgoing} files</Row>
        <Row label="Connections">
          {node.total} <span className="text-xs text-faint">({fmtPercent(node.centrality)} of the most connected)</span>
        </Row>
        <Row label="Risk">{node.risk_level ? `${node.risk_level} · ${fmtPercent(node.risk_probability)}` : "Unavailable"}</Row>
        <Row label="Technical debt">{node.debt_level ? `${capitalize(node.debt_level)} · ${fmtNumber(node.debt_score, 0)}` : "—"}</Row>
        <Row label="Complexity">{intel.data?.summary ? fmtNumber(intel.data.summary.complexity) : intel.isLoading ? "…" : "—"}</Row>
      </dl>

      {node.opportunity && (
        <div className="rounded border border-line bg-surface p-3">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-xs font-medium text-muted">Contribution opportunity</h4>
            <LevelBadge level={node.opportunity.difficulty} />
          </div>
          <p className="tabular mt-1 text-xs text-muted">
            Ranked #{node.opportunity.rank} · score {fmtNumber(node.opportunity.score, 1)}
          </p>
          {intel.data?.why && <p className="mt-1.5 text-sm">{intel.data.why.why_it_matters}</p>}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="primary" icon={<FileSearch className="h-3.5 w-3.5" />} onClick={() => open(node.id, "before")}>
          Explore this file
        </Button>
        <Button size="sm" icon={<Radar className="h-3.5 w-3.5" />} onClick={() => onImpact(node.id)}>
          Show impact
        </Button>
        <Button size="sm" variant="ghost" icon={<Crosshair className="h-3.5 w-3.5" />} onClick={() => onFocus(node.id)}>
          Focus
        </Button>
      </div>

      {[
        ["Uses (in this view)", outgoing],
        ["Used by (in this view)", incoming],
      ].map(([title, list]) => (
        <div key={title as string}>
          <h4 className="mb-1 text-xs text-muted">
            {title as string} <span className="text-faint">({(list as string[]).length})</span>
          </h4>
          {(list as string[]).length ? (
            <ul className="space-y-1">
              {(list as string[]).slice(0, 12).map((id) => (
                <li key={id}>
                  <FileLink path={id} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-faint">None shown</p>
          )}
        </div>
      ))}
    </div>
  );
}

function GroupPanel({ group, onExpand, onClose }: { group: DirectoryGroup; onExpand: (id: string) => void; onClose: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-sm font-medium">{group.label}/</p>
          <p className="text-sm text-muted">
            {group.name_hint ? (
              <>
                {group.name_hint} <span className="text-xs text-faint">(suggested by the name)</span>
              </>
            ) : (
              "Directory"
            )}
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Clear selection">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-sm">{group.structure}.</p>
      <dl className="divide-y divide-line">
        <Row label="Files">{group.file_count}</Row>
        <Row label="Lines of code">{fmtNumber(group.loc)}</Row>
        <Row label="Imports into it">{group.incoming}</Row>
        <Row label="Imports out of it">{group.outgoing}</Row>
        <Row label="Internal imports">{group.internal_dependencies}</Row>
        <Row label="Opportunities">{group.opportunities}</Row>
        <Row label="High-risk files">{group.high_risk_files}</Row>
      </dl>
      <div>
        <h4 className="mb-1 text-xs text-muted">Important files</h4>
        <ul className="space-y-1">
          {group.key_files.map((file) => (
            <li key={file.file} className="flex items-center gap-2">
              <FileLink path={file.file} className="min-w-0 flex-1" />
              <span className="tabular text-2xs text-faint">{file.total}</span>
            </li>
          ))}
        </ul>
      </div>
      <Button size="sm" variant="primary" onClick={() => onExpand(group.id)}>
        Expand module
      </Button>
    </div>
  );
}

function FileSearchBox({ repoId, onPick }: { repoId: string; onPick: (path: string) => void }) {
  const files = useFileList(repoId);
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const matches = useMemo(() => {
    const query = text.trim().toLowerCase();
    if (!query) return [];
    return (files.data?.files ?? []).filter((file) => file.file.toLowerCase().includes(query)).slice(0, 12);
  }, [text, files.data]);
  return (
    <div className="relative w-full sm:w-72">
      <input
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && matches[0]) {
            onPick(matches[0].file);
            setText("");
            setOpen(false);
          }
        }}
        placeholder="Search for a file"
        aria-label="Search for a file to show its impact"
        role="combobox"
        aria-expanded={open && matches.length > 0}
        className="h-9 w-full rounded border border-line bg-surface px-3 text-sm placeholder:text-faint focus:outline-none focus-visible:border-accent"
      />
      {open && matches.length > 0 && (
        <ul role="listbox" className="panel absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto p-1">
          {matches.map((file) => (
            <li key={file.file} role="option" aria-selected={false}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onPick(file.file);
                  setText("");
                  setOpen(false);
                }}
                className="w-full rounded px-2 py-1.5 text-left hover:bg-raised"
              >
                <FilePath path={file.file} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Legend({ mode }: { mode: Mode }) {
  return (
    <div className="rounded border border-line bg-surface px-3 py-2 text-[11px] text-muted">
      {mode === "overview" ? (
        <ul className="space-y-0.5">
          <li>Box: a directory · wider means more files</li>
          <li>Arrow: files in one directory import files in the other</li>
          <li>Thicker arrow: more imports</li>
        </ul>
      ) : (
        <ul className="space-y-0.5">
          <li>Arrow: imports (left side imports right side)</li>
          <li>Wider box: more connections · thick border: highly connected</li>
          <li>Left color: risk level (green low → red critical)</li>
          {mode === "contribution" && <li>Highlighted: top 25 contribution opportunities</li>}
          <li className="flex items-center gap-2">
            <span className="flex items-center gap-1">
              <span className="h-0.5 w-4 bg-accent" /> uses
            </span>
            <span className="flex items-center gap-1">
              <span className="h-0.5 w-4 bg-medium" /> used by
            </span>
          </li>
        </ul>
      )}
    </div>
  );
}

function HowToRead() {
  return (
    <Explainer title="How to read this architecture">
      <ol className="list-decimal space-y-1 pl-4">
        <li>Start with Overview: each box is a directory, and arrows show which directories import from which.</li>
        <li>Look for highly connected files: they appear wider and with a thick border, and are listed under Start here.</li>
        <li>Select a core file to highlight what it depends on (blue arrows).</li>
        <li>Check what depends on that file (amber arrows) to see who would be affected by a change.</li>
        <li>Use Impact to follow the dependency path one, two or three steps away.</li>
        <li>Open “Explore this file” to see its risk, technical debt, Git history and contribution plan.</li>
      </ol>
      <p className="mt-2 text-xs text-faint">
        Relationships come from static imports only. Dynamic imports, dependency injection, plugins and runtime wiring are
        not determined by static analysis.
      </p>
    </Explainer>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function ArchitectureInner() {
  const { repoId } = useParams<"repoId">();
  const [params, setParams] = useSearchParams();
  const modeParam = params.get("mode") as Mode | null;
  const focus = params.get("focus");
  const groupParam = params.get("group");
  const limit = Number(params.get("limit") ?? 120) || 120;
  const depth = Number(params.get("depth") ?? 1) || 1;
  const mode: Mode = modeParam && MODES.some((item) => item.value === modeParam) ? modeParam : focus ? "impact" : "overview";
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  const guide = useGuide(repoId);
  const fileQuery = useArchitecture(repoId, {
    limit,
    directory: mode === "components" ? groupParam : null,
    focus: mode === "impact" ? focus : null,
    depth,
  });

  useEffect(() => setSelected(null), [mode, focus, groupParam]);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => (value === null ? next.delete(key) : next.set(key, value)));
    setParams(next, { replace: true });
  };
  const setMode = (value: Mode) => update({ mode: value });
  const showImpact = (id: string) => update({ mode: "impact", focus: id });
  const expandGroup = (id: string) => update({ mode: "components", group: id });

  if (guide.isLoading || (fileQuery.isLoading && mode !== "overview")) return <PageLoading />;
  const guideData = guide.data;
  const archData = fileQuery.data;
  if (archData && !archData.available) {
    return <EmptyState title="Architecture not available">{archData.reason}</EmptyState>;
  }

  const groups = guideData?.groups.groups ?? [];
  const selectedGroupData = groups.find((group) => group.id === selectedGroup) ?? null;
  const fileData = archData && archData.available ? archData : null;
  const selectedNode = fileData?.nodes.find((node) => node.id === selected) ?? null;

  let canvas: ReactNode;
  let panel: ReactNode;

  if (mode === "overview") {
    canvas = guideData && groups.length > 0 ? (
      <GroupGraph guide={guideData} selected={selectedGroup} onSelect={setSelectedGroup} onOpen={expandGroup} />
    ) : (
      <EmptyState title="No directories to show">No analyzed source files were found.</EmptyState>
    );
    panel = selectedGroupData ? (
      <GroupPanel group={selectedGroupData} onExpand={expandGroup} onClose={() => setSelectedGroup(null)} />
    ) : (
      <div className="space-y-3">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Compass className="h-4 w-4 text-accent" aria-hidden /> Start here
        </p>
        {guideData && guideData.start_here.length > 0 ? (
          <ol className="space-y-2.5">
            {guideData.start_here.map((item) => (
              <li key={item.file}>
                <div className="flex items-center gap-2">
                  <FileLink path={item.file} className="min-w-0 flex-1" />
                </div>
                <p className="text-xs text-muted">
                  <span className="text-ink">{item.label}.</span> {item.reason}
                </p>
                <button type="button" onClick={() => showImpact(item.file)} className="text-xs text-accent hover:underline">
                  Show impact
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted">No file stood out structurally.</p>
        )}
        <p className="text-xs text-faint">Select a directory for details; double-click to expand it.</p>
      </div>
    );
  } else if (mode === "components" && !groupParam) {
    canvas = (
      <div className="p-4">
        <p className="mb-3 text-sm text-muted">Choose a directory to see its files and how they connect.</p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {groups.map((group) => (
            <li key={group.id}>
              <button
                type="button"
                onClick={() => expandGroup(group.id)}
                className="w-full rounded border border-line bg-surface px-3 py-2 text-left hover:border-accent/50"
              >
                <span className="font-mono text-[12.5px]">{group.label}/</span>
                <span className="block text-xs text-muted">
                  {group.file_count} files{group.name_hint ? ` · ${group.name_hint}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
    panel = <p className="text-sm text-muted">Pick a directory on the left.</p>;
  } else if (mode === "impact" && !focus) {
    canvas = (
      <EmptyState icon={<Crosshair className="h-6 w-6" />} title="Choose a file">
        Search for a file above, or select a node in another view and choose “Show impact”, to see what it depends on and
        what depends on it.
      </EmptyState>
    );
    panel = <p className="text-sm text-muted">Upstream files are on the right (what it imports); downstream files are on the left (what imports it).</p>;
  } else if (fileData) {
    canvas = fileData.nodes.length ? (
      <FileGraph data={fileData} selected={selected} onSelect={setSelected} mode={mode} />
    ) : (
      <EmptyState icon={<Network className="h-6 w-6" />} title="No files to show">No files match this view.</EmptyState>
    );
    panel = selectedNode ? (
      <NodePanel
        node={selectedNode}
        data={fileData}
        repoId={repoId!}
        onFocus={(id) => update({ mode: "impact", focus: id, depth: "1" })}
        onImpact={showImpact}
        onClose={() => setSelected(null)}
      />
    ) : mode === "contribution" ? (
      <div className="space-y-2">
        <p className="text-sm font-medium">Top opportunities in this view</p>
        <ol className="space-y-1.5">
          {[...fileData.nodes]
            .filter((node) => node.opportunity)
            .sort((a, b) => a.opportunity!.rank - b.opportunity!.rank)
            .slice(0, 10)
            .map((node) => (
              <li key={node.id} className="flex items-center gap-2">
                <span className="tabular w-6 text-right text-xs text-faint">#{node.opportunity!.rank}</span>
                <button type="button" onClick={() => setSelected(node.id)} className="min-w-0 flex-1 text-left hover:underline">
                  <FilePath path={node.id} />
                </button>
                <LevelBadge level={node.opportunity!.difficulty} />
              </li>
            ))}
        </ol>
      </div>
    ) : (
      <div className="space-y-2">
        <p className="text-sm font-medium">Most connected files</p>
        <ol className="space-y-1.5">
          {fileData.most_connected.slice(0, 10).map((node, index) => (
            <li key={node.id} className="flex items-center gap-2">
              <span className="tabular w-5 text-right text-xs text-faint">{index + 1}</span>
              <button type="button" onClick={() => setSelected(node.id)} className="min-w-0 flex-1 text-left hover:underline">
                <FilePath path={node.id} />
              </button>
              <span className="text-2xs text-muted">{node.connectivity}</span>
            </li>
          ))}
        </ol>
        <p className="flex gap-1.5 pt-1 text-xs text-faint">
          <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /> Select a node to see why it matters.
        </p>
      </div>
    );
  } else {
    canvas = <Spinner label="Loading graph" />;
    panel = null;
  }

  const summary = fileData ?? null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Architecture map</h2>
          <p className="mt-0.5 text-sm text-muted">
            How the project is organised and connected, from static imports.
            {summary && (
              <span className="tabular">
                {" "}
                {fmtNumber(summary.files)} files, {fmtNumber(summary.dependency_relationships)} dependencies.
              </span>
            )}
          </p>
        </div>
        <FileSearchBox repoId={repoId!} onPick={showImpact} />
      </div>

      <HowToRead />

      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line">
        <Tabs<Mode> label="Architecture modes" value={mode} onChange={setMode} tabs={MODES} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {mode === "components" && groupParam && (
          <Select label="Directory" value={groupParam} onChange={(event) => update({ group: event.target.value })}>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.label}/ ({group.file_count})
              </option>
            ))}
          </Select>
        )}
        {(mode === "dependencies" || mode === "contribution" || mode === "components") && (
          <Select label="Maximum files" value={String(limit)} onChange={(event) => update({ limit: event.target.value })}>
            {[50, 120, 250, 500].map((value) => (
              <option key={value} value={value}>
                Top {value} files
              </option>
            ))}
          </Select>
        )}
        {mode === "impact" && focus && (
          <>
            <span className="text-sm text-muted">Impact of</span>
            <FilePath path={focus} className="max-w-xs" />
            <Select label="Depth" value={String(depth)} onChange={(event) => update({ depth: event.target.value })}>
              <option value="1">Direct relationships</option>
              <option value="2">2 steps away</option>
              <option value="3">3 steps away</option>
            </Select>
          </>
        )}
        {fileQuery.isFetching && <Spinner label="Updating" />}
      </div>

      {fileData?.truncated && mode !== "overview" && (
        <Callout>
          Showing the {fileData.nodes.length} most connected of {fmtNumber(fileData.candidate_count)} files. Use Components or
          Impact to explore the rest.
        </Callout>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-2">
          <div className="panel relative h-[62vh] min-h-[440px] overflow-hidden" aria-label="Architecture graph">
            {canvas}
          </div>
          {(mode === "overview" ? groups.length > 0 : Boolean(fileData?.nodes.length)) && <Legend mode={mode} />}
        </div>
        <Panel>{panel}</Panel>
      </div>

      {fileData && fileData.unresolved.length > 0 && (
        <details className="panel">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
            Dependencies static analysis could not resolve{" "}
            <span className="text-muted">({fmtNumber(fileData.unresolved_dependencies)})</span>
          </summary>
          <div className="border-t border-line px-4 py-3">
            <p className="mb-3 text-xs text-muted">
              Imports that do not point to a file in this repository, usually third-party packages or the standard library.
              They are not drawn in the graph.
            </p>
            <ul className="space-y-2">
              {fileData.unresolved.slice(0, 40).map((item) => (
                <li key={item.file} className="grid gap-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
                  <FileLink path={item.file} />
                  <span className="truncate font-mono text-xs text-muted" title={item.imports.join(", ")}>
                    {item.imports.join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </details>
      )}
      {mode !== "overview" && (
        <p className="text-xs text-faint">
          Need the big picture?{" "}
          <Link to={`/app/r/${repoId}/architecture`} className="text-accent hover:underline">
            Back to the overview
          </Link>
          .
        </p>
      )}
    </div>
  );
}

export default function ArchitecturePage() {
  return (
    <ReactFlowProvider>
      <ArchitectureInner />
    </ReactFlowProvider>
  );
}
