import shutil
import subprocess
from pathlib import Path

from codepulse_runtime import (
    ARCHITECTURE_DOT_PATH,
    ARCHITECTURE_PNG_PATH,
    ARCHITECTURE_SVG_PATH,
    project_path,
)


class ArchitectureDiagramGenerator:
    """Generate architecture artifacts from an existing static dependency graph."""

    def __init__(self, dependency_graph, limit=50):
        self.graph = dependency_graph
        self.limit = limit

    def _centrality(self):
        nodes = set(self.graph.dependencies) | set(self.graph.used_by)
        return sorted(
            (
                {
                    "file": node,
                    "incoming_dependencies": len(self.graph.used_by.get(node, set())),
                    "outgoing_dependencies": len(self.graph.dependencies.get(node, set())),
                    "total_connections": len(self.graph.used_by.get(node, set()))
                    + len(self.graph.dependencies.get(node, set())),
                }
                for node in nodes
            ),
            key=lambda item: (-item["total_connections"], item["file"]),
        )

    def _selected_nodes(self):
        centrality = self._centrality()
        if self.limit is None or len(centrality) <= self.limit:
            return centrality
        return centrality[:self.limit]

    @staticmethod
    def _quote(value):
        return '"' + str(value).replace("\\", "/").replace('"', '\\"') + '"'

    def _dot(self, centrality):
        selected = {item["file"] for item in centrality}
        lines = ["digraph codepulse_architecture {", "  rankdir=LR;"]
        for item in centrality:
            label = f"{item['file']}\\n(in: {item['incoming_dependencies']}, out: {item['outgoing_dependencies']})"
            lines.append(f"  {self._quote(item['file'])} [label={self._quote(label)}];")
        for source in sorted(selected):
            for target in sorted(self.graph.dependencies.get(source, set())):
                if target in selected:
                    lines.append(f"  {self._quote(source)} -> {self._quote(target)};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _sibling(path, suffix):
        """Derive a sibling artifact path (e.g. ..._overview.dot) next to `path`."""
        path = Path(path)
        return path.with_name(f"{path.stem}{suffix}{path.suffix}")

    @staticmethod
    def _render(dot_executable, dot_path, targets):
        """Render a DOT file to the requested formats; degrade gracefully."""
        if not dot_executable:
            return []
        rendered = []
        for format_name, output_path in targets:
            output_path = project_path(output_path)
            try:
                subprocess.run(
                    [dot_executable, f"-T{format_name}", str(dot_path),
                     "-o", str(output_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                rendered.append(str(output_path))
            except (OSError, subprocess.CalledProcessError):
                continue
        return rendered

    @staticmethod
    def _group_key(file_path):
        """Return the directory/package a file belongs to; root files share one group."""
        if "/" in file_path:
            return file_path.rsplit("/", 1)[0]
        return "(root)"

    @staticmethod
    def _short_label(file_path):
        """Concise node label: the filename only, never an absolute path."""
        return file_path.rsplit("/", 1)[-1]

    @staticmethod
    def _node_style(total_connections, max_total):
        """Visual emphasis derived from the existing centrality (no new score)."""
        ratio = (total_connections / max_total) if max_total else 0
        if ratio >= 0.66:
            return 'fillcolor="#176b87", fontcolor="white", fontsize=18, penwidth=2.2'
        if ratio >= 0.33:
            return 'fillcolor="#9fc5d1", fontsize=14, penwidth=1.6'
        return 'fillcolor="#eef3f6", fontsize=11, penwidth=1.0'

    def _overview_dot(self, centrality):
        """Clustered, centrality-weighted overview of the same selected nodes."""
        selected = {item["file"] for item in centrality}
        totals = {item["file"]: item["total_connections"] for item in centrality}
        max_total = max(totals.values(), default=0)
        groups = {}
        for item in centrality:
            groups.setdefault(self._group_key(item["file"]), []).append(item)
        lines = [
            "digraph codepulse_architecture_overview {",
            "  rankdir=LR;",
            "  compound=true;",
            "  labelloc=t;",
            '  node [shape=box, style="rounded,filled", fontname="Helvetica"];',
            '  edge [color="#7a8a99"];',
        ]
        for cluster_index, group_name in enumerate(sorted(groups)):
            lines.append(f"  subgraph cluster_{cluster_index} {{")
            lines.append(f"    label={self._quote(group_name)};")
            lines.append('    style="rounded";')
            lines.append('    color="#b0bec5";')
            lines.append("    fontsize=13;")
            for item in sorted(groups[group_name], key=lambda node: node["file"]):
                style = self._node_style(totals[item["file"]], max_total)
                label = self._short_label(item["file"])
                lines.append(
                    f"    {self._quote(item['file'])} "
                    f"[label={self._quote(label)}, {style}];"
                )
            lines.append("  }")
        for source in sorted(selected):
            for target in sorted(self.graph.dependencies.get(source, set())):
                if target in selected:
                    lines.append(f"  {self._quote(source)} -> {self._quote(target)};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def focused_dot(self, file_path):
        """Small readable graph: one file with its direct deps and dependents.

        Available for a focused selected-file view; it only reads the existing
        graph and does not alter DependencyImpactAnalyzer behaviour.
        """
        depends_on = self.graph.dependencies.get(file_path, set())
        used_by = self.graph.used_by.get(file_path, set())
        nodes = {file_path} | set(depends_on) | set(used_by)
        lines = [
            "digraph codepulse_focus {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fontname="Helvetica"];',
            '  edge [color="#7a8a99"];',
        ]
        for node in sorted(nodes):
            if node == file_path:
                style = 'fillcolor="#176b87", fontcolor="white", fontsize=16, penwidth=2.2'
            else:
                style = 'fillcolor="#eef3f6", fontsize=11'
            lines.append(
                f"  {self._quote(node)} "
                f"[label={self._quote(self._short_label(node))}, {style}];"
            )
        for target in sorted(depends_on):
            lines.append(f"  {self._quote(file_path)} -> {self._quote(target)};")
        for source in sorted(used_by):
            lines.append(f"  {self._quote(source)} -> {self._quote(file_path)};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def generate(self, dot_path=ARCHITECTURE_DOT_PATH,
                 png_path=ARCHITECTURE_PNG_PATH, svg_path=ARCHITECTURE_SVG_PATH):
        if self.graph is None or not hasattr(self.graph, "dependencies"):
            raise ValueError("A dependency graph is required for architecture analysis.")
        centrality = self._selected_nodes()

        dot_path = project_path(dot_path)
        png_path = project_path(png_path)
        svg_path = project_path(svg_path)
        dot_path.parent.mkdir(parents=True, exist_ok=True)

        # Full dependency graph: unchanged primary backward-compatible artifact.
        dot_path.write_text(self._dot(centrality), encoding="utf-8")

        # Clustered, centrality-weighted overview: new readable artifact.
        # Overview artifacts always sit beside the DOT they are built from.
        overview_dot_path = self._sibling(dot_path, "_overview")
        overview_png_path = dot_path.with_name(f"{dot_path.stem}_overview.png")
        overview_svg_path = dot_path.with_name(f"{dot_path.stem}_overview.svg")
        overview_dot_path.write_text(self._overview_dot(centrality), encoding="utf-8")

        dot_executable = shutil.which("dot")
        rendered = self._render(
            dot_executable, dot_path, (("png", png_path), ("svg", svg_path))
        )
        overview_rendered = self._render(
            dot_executable, overview_dot_path,
            (("png", overview_png_path), ("svg", overview_svg_path)),
        )

        unresolved = sum(
            len(imports)
            for imports in getattr(self.graph, "unresolved_imports", {}).values()
        )
        edges = sum(len(targets) for targets in self.graph.dependencies.values())
        return {
            "dot_path": str(dot_path),
            "rendered_paths": rendered,
            "files_in_dependency_graph": len(self.graph.dependencies),
            "displayed_files": len(centrality),
            "dependency_relationships": edges,
            "unresolved_dependencies": unresolved,
            "centrality": centrality,
            "graphviz_available": bool(dot_executable),
            "overview_dot_path": str(overview_dot_path),
            "overview_rendered_paths": overview_rendered,
            "full_dot_path": str(dot_path),
            "full_rendered_paths": rendered,
        }

    @staticmethod
    def print_report(report):
        print("\n==========================================")
        print("          ARCHITECTURE ANALYSIS")
        print("==========================================")
        print(f"Files in dependency graph: {report['files_in_dependency_graph']}")
        print(f"Displayed files: {report['displayed_files']}")
        print(f"Dependency relationships: {report['dependency_relationships']}")
        print(f"Unresolved dependencies: {report['unresolved_dependencies']}")
        print("\nMost connected files:")
        for rank, item in enumerate(report["centrality"][:5], start=1):
            print(f"{rank}. {item['file']} - {item['total_connections']} total "
                  f"(in: {item['incoming_dependencies']}, out: {item['outgoing_dependencies']})")
        print(f"\nDOT artifact: {report['dot_path']}")
        if report["rendered_paths"]:
            print("Rendered artifacts:")
            for path in report["rendered_paths"]:
                print(path)
        else:
            print("Graphviz rendering unavailable; DOT output was generated.")
        overview_dot = report.get("overview_dot_path")
        if overview_dot:
            print(f"\nOverview DOT artifact: {overview_dot}")
            for path in report.get("overview_rendered_paths", []):
                print(path)
        print("==========================================")