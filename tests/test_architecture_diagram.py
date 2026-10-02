import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis.architecture_diagram import ArchitectureDiagramGenerator
from analysis.dependency_analyzer import StaticDependencyAnalyzer
from analysis.dependency_impact import DependencyImpactAnalyzer


class TestArchitectureDiagramGenerator(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="codepulse_architecture_"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _graph(self):
        files = [str(path.relative_to(self.root)).replace("\\", "/")
                 for path in self.root.rglob("*.py")]
        return StaticDependencyAnalyzer(self.root, files).build()

    def test_simple_and_multiple_dependencies(self):
        self._write("base.py", "VALUE = 1\n")
        self._write("helper.py", "from base import VALUE\nreturn_value = VALUE\n")
        self._write("app.py", "from helper import return_value\nfrom base import VALUE\n")
        graph = self._graph()
        self.assertIn("base.py", graph.dependencies["app.py"])
        self.assertIn("helper.py", graph.dependencies["app.py"])
        report = ArchitectureDiagramGenerator(graph).generate(
            dot_path=self.root / "architecture.dot",
            png_path=self.root / "architecture.png",
            svg_path=self.root / "architecture.svg",
        )
        self.assertEqual(report["dependency_relationships"], 3)
        self.assertTrue(Path(report["dot_path"]).exists())
        self.assertIn('"app.py" -> "base.py"', Path(report["dot_path"]).read_text())

    def test_central_file_detection(self):
        self._write("core.py", "VALUE = 1\n")
        for name in ("one.py", "two.py", "three.py"):
            self._write(name, "from core import VALUE\nvalue = VALUE\n")
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "central.dot"
        )
        self.assertEqual(report["centrality"][0]["file"], "core.py")
        self.assertEqual(report["centrality"][0]["incoming_dependencies"], 3)
        self.assertEqual(report["centrality"][0]["total_connections"], 3)

    def test_unresolved_dependency_is_reported_without_edge(self):
        self._write("app.py", "import external_package\nvalue = 1\n")
        graph = self._graph()
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "unresolved.dot"
        )
        self.assertEqual(report["dependency_relationships"], 0)
        self.assertGreaterEqual(report["unresolved_dependencies"], 1)
        self.assertEqual(len(graph.dependencies["app.py"]), 0)

    def test_empty_and_single_file_graphs(self):
        empty_graph = StaticDependencyAnalyzer(self.root, []).build()
        empty_report = ArchitectureDiagramGenerator(empty_graph).generate(
            dot_path=self.root / "empty.dot"
        )
        self.assertEqual(empty_report["files_in_dependency_graph"], 0)
        self.assertTrue(Path(empty_report["dot_path"]).exists())

        self._write("single.py", "value = 1\n")
        single_report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "single.dot"
        )
        self.assertEqual(single_report["displayed_files"], 1)
        self.assertEqual(single_report["dependency_relationships"], 0)

    def test_large_graph_limit(self):
        for index in range(5):
            self._write(f"file_{index}.py", "value = 1\n")
        report = ArchitectureDiagramGenerator(self._graph(), limit=2).generate(
            dot_path=self.root / "limited.dot"
        )
        self.assertEqual(report["files_in_dependency_graph"], 5)
        self.assertEqual(report["displayed_files"], 2)

    def test_graphviz_missing_falls_back_to_dot(self):
        self._write("single.py", "value = 1\n")
        with patch("analysis.architecture_diagram.shutil.which", return_value=None):
            report = ArchitectureDiagramGenerator(self._graph()).generate(
                dot_path=self.root / "fallback.dot"
            )
        self.assertFalse(report["graphviz_available"])
        self.assertEqual(report["rendered_paths"], [])
        self.assertTrue(Path(report["dot_path"]).exists())

    def test_existing_dependency_impact_remains_compatible(self):
        self._write("base.py", "VALUE = 1\n")
        self._write("app.py", "from base import VALUE\n")
        graph = self._graph()
        impact = DependencyImpactAnalyzer().analyze("base.py", graph)
        self.assertEqual(impact["dependent_count"], 1)
        self.assertEqual(impact["impact_level"], "LOW")

    # --- Overview (clustered, centrality-weighted) view -------------------

    def test_report_preserves_existing_keys_and_adds_overview_keys(self):
        self._write("base.py", "VALUE = 1\n")
        self._write("app.py", "from base import VALUE\n")
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "keys.dot",
            png_path=self.root / "keys.png",
            svg_path=self.root / "keys.svg",
        )
        for key in (
            "dot_path", "rendered_paths", "files_in_dependency_graph",
            "displayed_files", "dependency_relationships",
            "unresolved_dependencies", "centrality", "graphviz_available",
        ):
            self.assertIn(key, report)
        for key in (
            "overview_dot_path", "overview_rendered_paths",
            "full_dot_path", "full_rendered_paths",
        ):
            self.assertIn(key, report)

    def test_overview_uses_short_labels_and_no_absolute_paths(self):
        self._write("src/pkg/api.py", "from src.pkg.models import M\n")
        self._write("src/pkg/models.py", "M = 1\n")
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "arch.dot",
            png_path=self.root / "arch.png",
            svg_path=self.root / "arch.svg",
        )
        text = Path(report["overview_dot_path"]).read_text()
        self.assertTrue(Path(report["overview_dot_path"]).exists())
        self.assertIn('label="api.py"', text)
        self.assertIn('label="models.py"', text)
        self.assertNotIn(str(self.root), text)

    def test_overview_groups_directories_and_root(self):
        self._write("pkg/a.py", "from pkg.b import x\n")
        self._write("pkg/b.py", "x = 1\n")
        self._write("root_module.py", "value = 1\n")
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "grouped.dot"
        )
        text = Path(report["overview_dot_path"]).read_text()
        self.assertIn("subgraph cluster_", text)
        self.assertIn('label="pkg"', text)
        self.assertIn('label="(root)"', text)

    def test_overview_emphasizes_central_file(self):
        self._write("core.py", "VALUE = 1\n")
        for name in ("one.py", "two.py", "three.py"):
            self._write(name, "from core import VALUE\nvalue = VALUE\n")
        report = ArchitectureDiagramGenerator(self._graph()).generate(
            dot_path=self.root / "emph.dot"
        )
        text = Path(report["overview_dot_path"]).read_text()
        core_line = next(
            line for line in text.splitlines()
            if '"core.py"' in line and "label=" in line
        )
        leaf_line = next(
            line for line in text.splitlines()
            if '"one.py"' in line and "label=" in line
        )
        self.assertIn("#176b87", core_line)
        self.assertNotIn("#176b87", leaf_line)

    def test_overview_graphviz_missing_is_graceful(self):
        self._write("single.py", "value = 1\n")
        with patch("analysis.architecture_diagram.shutil.which", return_value=None):
            report = ArchitectureDiagramGenerator(self._graph()).generate(
                dot_path=self.root / "noviz.dot"
            )
        self.assertFalse(report["graphviz_available"])
        self.assertEqual(report["overview_rendered_paths"], [])
        self.assertTrue(Path(report["overview_dot_path"]).exists())

    def test_overview_handles_empty_graph(self):
        empty_graph = StaticDependencyAnalyzer(self.root, []).build()
        report = ArchitectureDiagramGenerator(empty_graph).generate(
            dot_path=self.root / "empty.dot"
        )
        self.assertTrue(Path(report["overview_dot_path"]).exists())
        self.assertEqual(report["files_in_dependency_graph"], 0)

    def test_focused_graph_contains_file_and_neighbors(self):
        self._write("models.py", "VALUE = 1\n")
        self._write("api.py", "from models import VALUE\n")
        self._write("sessions.py", "from models import VALUE\n")
        dot = ArchitectureDiagramGenerator(self._graph()).focused_dot("models.py")
        self.assertIn('label="models.py"', dot)
        self.assertIn('"api.py" -> "models.py"', dot)
        self.assertIn('"sessions.py" -> "models.py"', dot)


if __name__ == "__main__":
    unittest.main()
