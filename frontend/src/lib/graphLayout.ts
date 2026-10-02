import type { GraphEdge, GraphNode } from "../types/api";

export interface Positioned {
  id: string;
  x: number;
  y: number;
}

const COLUMN_GAP = 270;
const ROW_GAP = 74;

/**
 * Layered layout for a dependency graph (no external layout library).
 *
 * An edge source -> target means "source imports target". Files that import
 * others sit to the left of the files they import. Ranks come from the
 * longest import chain below each file (cycles are broken by ignoring back
 * edges), and nodes within a column are ordered by the average position of
 * their neighbours to reduce crossings. Unconnected files go in a grid below.
 */
export function layeredLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Positioned> {
  const ids = new Set(nodes.map((node) => node.id));
  const out = new Map<string, string[]>();
  const into = new Map<string, string[]>();
  for (const id of ids) {
    out.set(id, []);
    into.set(id, []);
  }
  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target) || edge.source === edge.target) continue;
    out.get(edge.source)!.push(edge.target);
    into.get(edge.target)!.push(edge.source);
  }

  // Rank = longest path to a leaf along import edges (iterative DFS).
  const rank = new Map<string, number>();
  const state = new Map<string, 0 | 1 | 2>(); // 0 new, 1 visiting, 2 done
  const sortedIds = [...ids].sort();
  for (const start of sortedIds) {
    if (state.get(start) === 2) continue;
    const stack: [string, number][] = [[start, 0]];
    state.set(start, 1);
    while (stack.length) {
      const frame = stack[stack.length - 1];
      const [id, index] = frame;
      const children = out.get(id)!;
      if (index < children.length) {
        frame[1] = index + 1;
        const child = children[index];
        if (!state.get(child)) {
          state.set(child, 1);
          stack.push([child, 0]);
        }
        continue;
      }
      let best = -1;
      for (const child of children) {
        if (state.get(child) === 2) best = Math.max(best, rank.get(child) ?? 0);
      }
      rank.set(id, best + 1);
      state.set(id, 2);
      stack.pop();
    }
  }

  const isolated = sortedIds.filter((id) => out.get(id)!.length === 0 && into.get(id)!.length === 0);
  const isolatedSet = new Set(isolated);
  const connected = sortedIds.filter((id) => !isolatedSet.has(id));
  const maxRank = Math.max(0, ...connected.map((id) => rank.get(id) ?? 0));

  const columns: string[][] = Array.from({ length: maxRank + 1 }, () => []);
  const directoryOf = new Map(nodes.map((node) => [node.id, node.directory]));
  for (const id of connected) columns[maxRank - (rank.get(id) ?? 0)].push(id);
  for (const column of columns) {
    column.sort((a, b) => (directoryOf.get(a) ?? "").localeCompare(directoryOf.get(b) ?? "") || a.localeCompare(b));
  }

  // Barycenter ordering sweeps.
  const order = new Map<string, number>();
  const assign = () => columns.forEach((column) => column.forEach((id, index) => order.set(id, index)));
  assign();
  const neighbours = (id: string) => [...out.get(id)!, ...into.get(id)!];
  for (let sweep = 0; sweep < 4; sweep++) {
    const sequence = sweep % 2 === 0 ? columns.slice(1) : columns.slice(0, -1).reverse();
    for (const column of sequence) {
      const score = new Map<string, number>();
      for (const id of column) {
        const positions = neighbours(id).map((n) => order.get(n)).filter((value): value is number => value !== undefined);
        score.set(id, positions.length ? positions.reduce((a, b) => a + b, 0) / positions.length : order.get(id) ?? 0);
      }
      column.sort((a, b) => (score.get(a) ?? 0) - (score.get(b) ?? 0));
      column.forEach((id, index) => order.set(id, index));
    }
  }

  const tallest = Math.max(1, ...columns.map((column) => column.length));
  const positions = new Map<string, Positioned>();
  columns.forEach((column, columnIndex) => {
    const offset = ((tallest - column.length) * ROW_GAP) / 2;
    column.forEach((id, rowIndex) => {
      positions.set(id, { id, x: columnIndex * COLUMN_GAP, y: offset + rowIndex * ROW_GAP });
    });
  });

  // Unconnected files: a compact grid under the graph.
  const gridTop = connected.length ? tallest * ROW_GAP + 80 : 0;
  const perRow = Math.max(4, columns.length);
  isolated.forEach((id, index) => {
    positions.set(id, {
      id,
      x: (index % perRow) * COLUMN_GAP,
      y: gridTop + Math.floor(index / perRow) * ROW_GAP,
    });
  });
  return positions;
}
