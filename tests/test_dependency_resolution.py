import shutil
import tempfile
import unittest
from pathlib import Path

from analysis.architecture_diagram import ArchitectureDiagramGenerator
from analysis.dependency_analyzer import StaticDependencyAnalyzer
from analysis.dependency_impact import DependencyImpactAnalyzer


class TestDependencyResolution(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="codepulse_dependency_"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def graph(self):
        files = [
            str(path.relative_to(self.root)).replace("\\", "/")
            for path in self.root.rglob("*")
            if path.is_file()
        ]
        return StaticDependencyAnalyzer(self.root, files).build()

    def test_python_absolute_local_import(self):
        self.write("main.py", "import helpers\n")
        self.write("helpers.py", "VALUE = 1\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["main.py"], {"helpers.py"})

    def test_python_relative_import(self):
        self.write("pkg/main.py", "from .utils import VALUE\n")
        self.write("pkg/utils.py", "VALUE = 1\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["pkg/main.py"], {"pkg/utils.py"})

    def test_python_package_import(self):
        self.write("app.py", "import package\nfrom package import service\n")
        self.write("package/__init__.py", "from .service import run\n")
        self.write("package/service.py", "def run(): pass\n")
        graph = self.graph()
        self.assertIn("package/__init__.py", graph.dependencies["app.py"])
        self.assertIn("package/service.py", graph.dependencies["app.py"])

    def test_python_parent_relative_import(self):
        self.write("pkg/sub/main.py", "from ..shared import VALUE\n")
        self.write("pkg/shared.py", "VALUE = 1\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["pkg/sub/main.py"], {"pkg/shared.py"})

    def test_javascript_relative_import_and_extensions(self):
        self.write("src/app.js", "import Button from './components/Button'\n")
        self.write("src/components/Button.jsx", "export default function Button() {}\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["src/app.js"], {"src/components/Button.jsx"})

    def test_typescript_tsx_relative_import(self):
        self.write("src/app.ts", "import View from './View'\n")
        self.write("src/View.tsx", "export const View = () => null\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["src/app.ts"], {"src/View.tsx"})

    def test_index_resolution(self):
        self.write("src/app.jsx", "import Button from './components/Button'\n")
        self.write("src/components/Button/index.ts", "export const Button = 1\n")
        graph = self.graph()
        self.assertEqual(
            graph.dependencies["src/app.jsx"],
            {"src/components/Button/index.ts"},
        )

    def test_external_package_is_not_local_edge(self):
        self.write("app.py", "import requests\nimport package_not_in_repo\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["app.py"], set())
        self.assertIn("requests", graph.unresolved_imports["app.py"])
        self.assertIn("package_not_in_repo", graph.unresolved_imports["app.py"])

    def test_unresolved_import_reporting_and_no_false_edge(self):
        self.write("src/app.js", "import missing from './missing'\n")
        graph = self.graph()
        self.assertEqual(graph.dependencies["src/app.js"], set())
        self.assertEqual(graph.unresolved_imports["src/app.js"], {"./missing"})

    def test_architecture_and_impact_compatibility(self):
        self.write("main.py", "import helpers\n")
        self.write("helpers.py", "VALUE = 1\n")
        graph = self.graph()
        report = ArchitectureDiagramGenerator(graph).generate(
            dot_path=self.root / "architecture.dot"
        )
        self.assertEqual(report["dependency_relationships"], 1)
        self.assertIn('"main.py" -> "helpers.py"', Path(report["dot_path"]).read_text())
        impact = DependencyImpactAnalyzer().analyze("helpers.py", graph)
        self.assertEqual(impact["dependent_count"], 1)
        self.assertEqual(impact["used_by"], ["main.py"])


if __name__ == "__main__":
    unittest.main()
