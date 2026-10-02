import ast
import posixpath
import re
from pathlib import Path


class StaticDependencyAnalyzer:
    """Build a local-file dependency graph from static imports/includes only."""

    EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".html", ".css")
    JAVASCRIPT_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx")

    def __init__(self, repository_path, source_files):
        self.repository_path = Path(repository_path).resolve()
        self.source_files = {
            self._normalize_source_file(file_path)
            for file_path in source_files
        }
        self.dependencies = {file_path: set() for file_path in self.source_files}
        self.used_by = {file_path: set() for file_path in self.source_files}
        self.unresolved_imports = {}

        # All resolution below uses this one repository-relative index.
        self.source_paths = {
            file_path: self.repository_path / file_path
            for file_path in self.source_files
        }
        self.file_by_name = {}
        for file_path in self.source_files:
            name = file_path.rsplit("/", 1)[-1]
            self.file_by_name.setdefault(name, []).append(file_path)

    def _normalize_source_file(self, file_path):
        path = Path(file_path)
        try:
            if path.is_absolute():
                path = path.resolve().relative_to(self.repository_path)
        except (OSError, ValueError):
            pass
        return str(path).replace("\\", "/").lstrip("./")

    @staticmethod
    def _normalized_path(path):
        normalized = posixpath.normpath(str(path).replace("\\", "/"))
        if normalized == "." or normalized.startswith("../"):
            return None
        return normalized.lstrip("/")

    def _candidate_names(self, base_path, extensions):
        base = self._normalized_path(base_path)
        if not base:
            return []
        candidates = [base]
        suffix = Path(base).suffix.lower()
        if suffix not in extensions:
            candidates.extend(base + extension for extension in extensions)
        candidates.extend(f"{base}/index{extension}" for extension in extensions)
        if ".py" in extensions:
            candidates.append(f"{base}/__init__.py")
        return candidates

    def _first_existing(self, candidates):
        for candidate in candidates:
            if candidate in self.source_paths:
                return candidate
        return None

    def _resolve_python_import(self, import_path):
        return self._first_existing(self._candidate_names(import_path, (".py",)))

    def _resolve_python_relative(self, source_file, import_path):
        clean_import = import_path.replace("\\", "/")
        dots = len(clean_import) - len(clean_import.lstrip("."))
        remainder = clean_import[dots:].lstrip("/")
        source_parent = posixpath.dirname(source_file)
        base_parts = source_parent.split("/") if source_parent else []
        if dots > len(base_parts) + 1:
            return None
        anchor = "/".join(base_parts[:len(base_parts) - dots + 1])
        base = f"{anchor}/{remainder}" if anchor and remainder else anchor or remainder
        return self._first_existing(self._candidate_names(base, (".py",)))

    def _resolve_javascript_import(self, source_file, import_path):
        clean_import = import_path.strip().replace("\\", "/")
        if not clean_import.startswith("."):
            return None
        source_dir = posixpath.dirname(source_file)
        base = posixpath.join(source_dir, clean_import)
        return self._first_existing(
            self._candidate_names(base, self.JAVASCRIPT_EXTENSIONS)
        )

    def _resolve_legacy_import(self, source_file, import_path):
        clean_import = import_path.strip().replace("\\", "/")
        if clean_import.startswith(("http://", "https://", "//")):
            return None
        import_filename = clean_import.rsplit("/", 1)[-1]
        matches = self.file_by_name.get(import_filename, [])
        if len(matches) == 1:
            return matches[0]
        source_dir = posixpath.dirname(source_file)
        for base in (
            posixpath.join(source_dir, clean_import),
            clean_import.lstrip("/"),
        ):
            resolved = self._first_existing(
                self._candidate_names(base, self.EXTENSIONS)
            )
            if resolved:
                return resolved
        return None

    @staticmethod
    def _javascript_imports(content):
        patterns = [
            r"(?:import|export)\s+(?:[^'\"]*?\s+from\s+)?['\"]([^'\"]+)['\"]",
            r"require\(\s*['\"]([^'\"]+)['\"]\s*\)",
        ]
        return {
            item
            for pattern in patterns
            for item in re.findall(pattern, content)
        }

    @staticmethod
    def _html_imports(content):
        return set(re.findall(
            r"<(?:script|link)[^>]+(?:src|href)=['\"]([^'\"]+)['\"]",
            content,
            flags=re.IGNORECASE
        ))

    @staticmethod
    def _css_imports(content):
        return set(re.findall(
            r"@import\s+(?:url\(['\"]?|['\"])([^'\"\)]+)['\"]?\)?;?",
            content,
            flags=re.IGNORECASE
        ))

    @staticmethod
    def _java_imports(content):
        imports = set()
        for match in re.findall(r"import\s+(?:static\s+)?([a-zA-Z0-9_.]+);", content):
            imports.add("/".join(match.split(".")))
            imports.add(match.rsplit(".", 1)[-1])
        return imports

    @staticmethod
    def _python_imports(content, source_file):
        imports = set()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.replace(".", "/") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module.replace(".", "/") if node.module else ""
                if node.level:
                    prefix = "." * node.level
                    if module:
                        imports.add(prefix + module)
                    for alias in node.names:
                        imports.add(prefix + (module + "/" if module else "") + alias.name)
                elif module:
                    imports.add(module)
                    for alias in node.names:
                        imports.add(f"{module}/{alias.name}")
        return imports

    def _extract_imports(self, source_file, content):
        extension = Path(source_file).suffix.lower()
        if extension == ".py":
            return self._python_imports(content, source_file)
        if extension in self.JAVASCRIPT_EXTENSIONS:
            return self._javascript_imports(content)
        if extension == ".html":
            return self._html_imports(content)
        if extension == ".css":
            return self._css_imports(content)
        if extension == ".java":
            return self._java_imports(content)
        return set()

    def _resolve_import(self, source_file, import_path):
        extension = Path(source_file).suffix.lower()
        if extension == ".py":
            if import_path.startswith("."):
                return self._resolve_python_relative(source_file, import_path)
            return self._resolve_python_import(import_path)
        if extension in self.JAVASCRIPT_EXTENSIONS:
            return self._resolve_javascript_import(source_file, import_path)
        return self._resolve_legacy_import(source_file, import_path)

    def build(self):
        for source_file, file_path in self.source_paths.items():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for import_path in self._extract_imports(source_file, content):
                target_file = self._resolve_import(source_file, import_path)
                if target_file and target_file != source_file:
                    self.dependencies[source_file].add(target_file)
                    self.used_by[target_file].add(source_file)
                elif target_file is None:
                    self.unresolved_imports.setdefault(source_file, set()).add(import_path)

        return self
