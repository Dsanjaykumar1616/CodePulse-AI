import ast
import re
from pathlib import Path
from html.parser import HTMLParser

from radon.complexity import cc_visit
from radon.metrics import mi_visit
import lizard


class HTMLAnalyzer(HTMLParser):

    def __init__(self):
        super().__init__()

        self.element_count = 0
        self.comment_count = 0
        self.current_depth = 0
        self.max_depth = 0

    def handle_starttag(self, tag, attrs):

        self.element_count += 1

        self.current_depth += 1

        self.max_depth = max(
            self.max_depth,
            self.current_depth
        )

    def handle_startendtag(self, tag, attrs):

        self.element_count += 1

    def handle_endtag(self, tag):

        if self.current_depth > 0:
            self.current_depth -= 1

    def handle_comment(self, data):

        self.comment_count += 1


class CodeMetricsExtractor:

    # Directories that should not be analyzed
    IGNORED_DIRECTORIES = {
        ".git",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        "coverage",
        ".cache"
    }

    SUPPORTED_EXTENSIONS = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "React",
        ".tsx": "React",
        ".html": "HTML",
        ".css": "CSS",
        ".java": "Java"
    }

    def __init__(self, repository_path):

        self.repository_path = Path(
            repository_path
        )

    # =====================================================
    # Find supported files
    # =====================================================

    def get_source_files(self):

        source_files = []

        for file_path in self.repository_path.rglob("*"):

            if not file_path.is_file():
                continue

            # Ignore unwanted directories
            if any(
                directory in file_path.parts
                for directory in self.IGNORED_DIRECTORIES
            ):
                continue

            extension = file_path.suffix.lower()

            if extension in self.SUPPORTED_EXTENSIONS:

                source_files.append(file_path)

        return source_files

    # =====================================================
    # Detect technology
    # =====================================================

    def detect_language(self, file_path):

        extension = file_path.suffix.lower()

        language = self.SUPPORTED_EXTENSIONS.get(
            extension,
            "Unknown"
        )

        # React detection
        if extension in {".jsx", ".tsx"}:

            return "React"

        return language

    # =====================================================
    # LOC
    # =====================================================

    def calculate_loc(self, source_code):

        lines = source_code.splitlines()

        return len(
            [
                line
                for line in lines
                if line.strip()
            ]
        )

    # =====================================================
    # Comment Ratio
    # =====================================================

    def calculate_comment_ratio(
        self,
        source_code,
        language
    ):

        lines = source_code.splitlines()

        total_lines = len(
            [
                line
                for line in lines
                if line.strip()
            ]
        )

        if total_lines == 0:
            return 0

        comment_lines = 0

        in_block_comment = False

        for line in lines:

            stripped = line.strip()
            if not stripped:
                continue

            # Python comments
            if language == "Python":

                if stripped.startswith("#"):
                    comment_lines += 1

            # JavaScript / TypeScript / React / Java / CSS / HTML
            else:
                if in_block_comment:
                    comment_lines += 1
                    if "*/" in stripped or "-->" in stripped:
                        in_block_comment = False
                    continue

                if "/*" in stripped:
                    comment_lines += 1
                    if "*/" not in stripped:
                        in_block_comment = True
                    continue

                if "<!--" in stripped:
                    comment_lines += 1
                    if "-->" not in stripped:
                        in_block_comment = True
                    continue

                if (
                    stripped.startswith("//")
                    or stripped.startswith("*")
                ):
                    comment_lines += 1

        return round(
            comment_lines / total_lines,
            3
        )

    # =====================================================
    # Python AST Analysis
    # =====================================================

    def analyze_python_ast(
        self,
        source_code
    ):

        tree = ast.parse(
            source_code
        )

        classes = 0
        functions = 0
        max_nesting = 0

        nesting_nodes = (
            ast.If,
            ast.For,
            ast.While,
            ast.With,
            ast.Try
        )

        def visit_node(
            node,
            depth=0
        ):

            nonlocal classes
            nonlocal functions
            nonlocal max_nesting

            if isinstance(
                node,
                ast.ClassDef
            ):
                classes += 1

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):
                functions += 1

            if isinstance(
                node,
                nesting_nodes
            ):

                current_depth = depth + 1

                max_nesting = max(
                    max_nesting,
                    current_depth
                )

                for child in ast.iter_child_nodes(node):

                    visit_node(
                        child,
                        current_depth
                    )

                return

            for child in ast.iter_child_nodes(node):

                visit_node(
                    child,
                    depth
                )

        visit_node(tree)

        return {
            "classes": classes,
            "functions": functions,
            "nesting_depth": max_nesting
        }

    # =====================================================
    # Python Metrics
    # =====================================================

    def analyze_python(
        self,
        file_path,
        source_code
    ):

        try:
            ast_metrics = self.analyze_python_ast(
                source_code
            )
        except Exception as error:
            print(
                f"  Python AST parsing failed: {error}"
            )
            ast_metrics = {
                "functions": 0,
                "classes": 0,
                "nesting_depth": 0
            }

        try:
            complexity_results = cc_visit(
                source_code
            )

            if complexity_results:
                complexity = sum(
                    result.complexity
                    for result in complexity_results
                )
            else:
                complexity = 0
        except Exception as error:
            print(
                f"  Radon complexity failed: {error}"
            )
            complexity = 0

        try:
            maintainability = mi_visit(
                source_code,
                multi=True
            )
            maintainability = round(
                maintainability,
                2
            )
        except Exception as error:
            print(
                f"  Radon maintainability failed: {error}"
            )
            maintainability = None

        return {
            "complexity": complexity,
            "maintainability": maintainability,
            "functions": ast_metrics[
                "functions"
            ],
            "classes": ast_metrics[
                "classes"
            ],
            "nesting_depth": ast_metrics[
                "nesting_depth"
            ]
        }

    # =====================================================
    # Lizard Metrics
    # =====================================================

    def analyze_with_lizard(
        self,
        file_path
    ):

        try:

            result = lizard.analyze_file(
                str(file_path)
            )

            functions = len(
                result.function_list
            )

            classes = 0

            complexity = sum(
                function.cyclomatic_complexity
                for function in result.function_list
            )

            average_complexity = (
                complexity / functions
                if functions > 0
                else 0
            )

            return {
                "complexity": complexity,
                "maintainability": None,
                "functions": functions,
                "classes": classes,
                "nesting_depth": 0,
                "average_complexity":
                    round(
                        average_complexity,
                        2
                    )
            }

        except Exception as error:

            print(
                f"  Lizard analysis failed: {error}"
            )

            return {
                "complexity": 0,
                "maintainability": None,
                "functions": 0,
                "classes": 0,
                "nesting_depth": 0,
                "average_complexity": 0
            }

    # =====================================================
    # HTML Metrics
    # =====================================================

    def analyze_html(
        self,
        source_code
    ):

        analyzer = HTMLAnalyzer()

        try:
            analyzer.feed(
                source_code
            )
        except Exception as error:
            print(
                f"  HTML parsing failed: {error}"
            )

        return {
            "complexity": 0,
            "maintainability": None,
            "functions": 0,
            "classes": 0,
            "nesting_depth":
                analyzer.max_depth,
            "elements":
                analyzer.element_count
        }

    # =====================================================
    # CSS Metrics
    # =====================================================

    def analyze_css(
        self,
        source_code
    ):

        # Remove comments
        clean_code = re.sub(
            r"/\*.*?\*/",
            "",
            source_code,
            flags=re.DOTALL
        )

        selectors = len(
            re.findall(
                r"[^{}]+\{",
                clean_code
            )
        )

        declarations = len(
            re.findall(
                r":[^;{}]+;",
                clean_code
            )
        )

        important_count = len(
            re.findall(
                r"!important",
                clean_code,
                flags=re.IGNORECASE
            )
        )

        max_nesting = 0
        current_depth = 0

        for character in clean_code:

            if character == "{":

                current_depth += 1

                max_nesting = max(
                    max_nesting,
                    current_depth
                )

            elif character == "}":

                current_depth = max(
                    0,
                    current_depth - 1
                )

        return {
            "complexity": 0,
            "maintainability": None,
            "functions": 0,
            "classes": 0,
            "nesting_depth": max_nesting,
            "selectors": selectors,
            "declarations": declarations,
            "important_count": important_count
        }

    # =====================================================
    # Analyze One File
    # =====================================================

    def analyze_file(
        self,
        file_path
    ):

        language = self.detect_language(
            file_path
        )

        print(
            f"\nAnalyzing: {file_path.name}"
        )

        print(
            f"Language: {language}"
        )

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:

                source_code = file.read()

        except (
            UnicodeDecodeError,
            OSError
        ) as error:

            print(
                f"  File skipped: {error}"
            )

            return None

        loc = self.calculate_loc(
            source_code
        )

        comment_ratio = (
            self.calculate_comment_ratio(
                source_code,
                language
            )
        )

        # -----------------------------
        # Python
        # -----------------------------

        if language == "Python":

            language_metrics = (
                self.analyze_python(
                    file_path,
                    source_code
                )
            )

        # -----------------------------
        # JavaScript / TypeScript
        # -----------------------------

        elif language in {
            "JavaScript",
            "TypeScript",
            "React",
            "Java"
        }:

            language_metrics = (
                self.analyze_with_lizard(
                    file_path
                )
            )

        # -----------------------------
        # HTML
        # -----------------------------

        elif language == "HTML":

            language_metrics = (
                self.analyze_html(
                    source_code
                )
            )

        # -----------------------------
        # CSS
        # -----------------------------

        elif language == "CSS":

            language_metrics = (
                self.analyze_css(
                    source_code
                )
            )

        else:

            return None

        return {
            "file": str(file_path),
            "language": language,
            "loc": loc,
            "complexity":
                language_metrics.get(
                    "complexity",
                    0
                ),
            "maintainability":
                language_metrics.get(
                    "maintainability"
                ),
            "functions":
                language_metrics.get(
                    "functions",
                    0
                ),
            "classes":
                language_metrics.get(
                    "classes",
                    0
                ),
            "nesting_depth":
                language_metrics.get(
                    "nesting_depth",
                    0
                ),
            "comment_ratio":
                comment_ratio,
            "elements":
                language_metrics.get(
                    "elements",
                    0
                ),
            "selectors":
                language_metrics.get(
                    "selectors",
                    0
                ),
            "declarations":
                language_metrics.get(
                    "declarations",
                    0
                ),
            "important_count":
                language_metrics.get(
                    "important_count",
                    0
                )
        }

    # =====================================================
    # Analyze Entire Repository
    # =====================================================

    def analyze_repository(self):

        results = []

        source_files = (
            self.get_source_files()
        )

        print(
            f"\nFound {len(source_files)} "
            f"supported source files."
        )

        for index, file_path in enumerate(
            source_files,
            start=1
        ):

            print(
                f"\n[{index}/{len(source_files)}]"
            )

            result = self.analyze_file(
                file_path
            )

            if result:

                results.append(
                    result
                )

        return results