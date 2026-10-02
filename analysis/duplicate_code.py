import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from codepulse_runtime import DUPLICATES_PATH, project_path
from metrics.code_metrics import CodeMetricsExtractor


class DuplicateCodeDetector:
    """Detect likely similar source files using explainable token similarity."""

    DEFAULT_MIN_TOKENS = 15
    DEFAULT_SIMILARITY_THRESHOLD = 0.75
    HIGH_SIMILARITY_THRESHOLD = 0.90
    MEDIUM_SIMILARITY_THRESHOLD = 0.80
    TOKEN_PATTERN = re.compile(
        r"(?:[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|==|!=|<=|>=|=>|&&|\|\||\+=|-=|\*=|/=|.)",
        re.DOTALL,
    )
    IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][\w$]*$")
    KEYWORDS = {
        "and", "as", "assert", "async", "await", "break", "case", "catch",
        "class", "const", "continue", "def", "default", "del", "do", "else",
        "except", "export", "extends", "finally", "for", "from", "function",
        "if", "import", "in", "interface", "is", "new", "not", "null", "or",
        "pass", "print", "public", "private", "raise", "return", "static",
        "switch", " this", "throw", "try", "typeof", "var", "void", "while",
        "with", "yield", "true", "false", "none", "this",
    }

    def __init__(self, repository_path, min_tokens=DEFAULT_MIN_TOKENS,
                 similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD):
        self.repository_path = Path(repository_path).resolve()
        self.min_tokens = min_tokens
        self.similarity_threshold = similarity_threshold
        self.source_extensions = set(CodeMetricsExtractor.SUPPORTED_EXTENSIONS)
        self.ignored_directories = set(CodeMetricsExtractor.IGNORED_DIRECTORIES)

    def get_source_files(self):
        files = []
        for path in self.repository_path.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in self.source_extensions:
                continue
            if any(part in self.ignored_directories for part in path.parts):
                continue
            files.append(path)
        return files

    @classmethod
    def tokenize(cls, source):
        """Remove comments/formatting and normalize safe identifier differences."""
        source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
        source = re.sub(r"<!--.*?-->", " ", source, flags=re.DOTALL)
        source = re.sub(r"(^|\s)#.*", r"\1 ", source)
        source = re.sub(r"(^|\s)//.*", r"\1 ", source)
        tokens = []
        for token in cls.TOKEN_PATTERN.findall(source):
            if token.isspace():
                continue
            if token[0] in {"'", '"', "`"}:
                tokens.append("STRING")
            elif cls.IDENTIFIER_PATTERN.match(token) and token.lower() not in cls.KEYWORDS:
                tokens.append("IDENT")
            else:
                tokens.append(token.lower())
        return tokens

    @staticmethod
    def _compatible(left, right):
        left_ext = left.suffix.lower()
        right_ext = right.suffix.lower()
        if left_ext == right_ext:
            return True
        web_groups = ({".js", ".jsx", ".ts", ".tsx"}, {".html", ".css"})
        return any(left_ext in group and right_ext in group for group in web_groups)

    @staticmethod
    def _level(similarity):
        if similarity >= DuplicateCodeDetector.HIGH_SIMILARITY_THRESHOLD:
            return "HIGH"
        if similarity >= DuplicateCodeDetector.MEDIUM_SIMILARITY_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _relative(path, root):
        return str(path.resolve().relative_to(root)).replace("\\", "/")

    def _pair_result(self, left, right, left_tokens, right_tokens, similarity):
        matcher = SequenceMatcher(None, left_tokens, right_tokens)
        matching_tokens = sum(block.size for block in matcher.get_matching_blocks())
        return {
            "file_a": self._relative(left, self.repository_path),
            "file_b": self._relative(right, self.repository_path),
            "similarity_score": round(similarity * 100, 2),
            "similarity_level": self._level(similarity),
            "matching_token_count": matching_tokens,
            "evidence": "Normalized token sequences share substantial structure",
        }

    def analyze(self):
        tokenized = {}
        for path in self.get_source_files():
            try:
                tokens = self.tokenize(path.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, UnicodeError):
                continue
            if len(tokens) >= self.min_tokens:
                tokenized[path] = tokens

        results = []
        paths = list(tokenized)
        for index, left in enumerate(paths):
            for right in paths[index + 1:]:
                if not self._compatible(left, right):
                    continue
                left_tokens = tokenized[left]
                right_tokens = tokenized[right]
                similarity = SequenceMatcher(None, left_tokens, right_tokens).ratio()
                if similarity >= self.similarity_threshold:
                    results.append(self._pair_result(
                        left, right, left_tokens, right_tokens, similarity
                    ))
        return pd.DataFrame(results, columns=[
            "file_a", "file_b", "similarity_score", "similarity_level",
            "matching_token_count", "evidence",
        ]).sort_values("similarity_score", ascending=False).reset_index(drop=True)

    @staticmethod
    def per_file_signal(pairs):
        """Return the maximum observed similarity for each participating file."""
        if pairs is None or pairs.empty:
            return pd.DataFrame(columns=["file", "duplication_score", "duplication_ratio"])
        values = {}
        for _, pair in pairs.iterrows():
            score = float(pair["similarity_score"]) / 100
            for file_path in (pair["file_a"], pair["file_b"]):
                values[file_path] = max(values.get(file_path, 0.0), score)
        return pd.DataFrame([
            {"file": file_path, "duplication_score": score, "duplication_ratio": score}
            for file_path, score in values.items()
        ])

    def summarize(self, pairs, top_n=10):
        pairs = pairs if pairs is not None else pd.DataFrame()
        high = int((pairs.get("similarity_level", pd.Series(dtype=str)) == "HIGH").sum())
        groups = []
        for _, pair in pairs.iterrows():
            members = {pair["file_a"], pair["file_b"]}
            matching = [group for group in groups if group & members]
            if matching:
                merged = members.union(*matching)
                groups = [group for group in groups if not group & members]
                groups.append(merged)
            else:
                groups.append(members)
        return {
            "duplicate_groups": len(groups),
            "high_similarity_groups": high,
            "top_pairs": pairs.head(top_n).to_dict("records"),
        }

    def save(self, pairs, output_path=DUPLICATES_PATH):
        output_path = project_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pairs.to_csv(output_path, index=False)
        return output_path

    @staticmethod
    def print_report(summary, limit=10):
        print("\n==========================================")
        print("        DUPLICATE CODE ANALYSIS")
        print("==========================================")
        print(f"Duplicate Groups: {summary['duplicate_groups']}")
        print(f"High Similarity Groups: {summary['high_similarity_groups']}")
        if not summary["top_pairs"]:
            print("No significant duplication detected.")
        else:
            print("\nTop Similar Code:")
            for rank, pair in enumerate(summary["top_pairs"][:limit], start=1):
                print(f"{rank}. {pair['file_a']} <-> {pair['file_b']} - "
                      f"{pair['similarity_score']:.1f}% ({pair['similarity_level']})")
                print(f"   {pair['evidence']}")
        print("==========================================")