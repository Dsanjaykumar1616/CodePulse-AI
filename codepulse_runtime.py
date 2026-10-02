"""Shared runtime paths, repository identity, and analysis artifact guards."""

import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_DIR = PROJECT_ROOT / "data" / "datasets"
MODEL_DIR = PROJECT_ROOT / "models"
FEATURES_PATH = DATASET_DIR / "codepulse_features.csv"
PREDICTIONS_PATH = DATASET_DIR / "codepulse_predictions.csv"
TECHNICAL_DEBT_PATH = DATASET_DIR / "codepulse_technical_debt.csv"
DUPLICATES_PATH = DATASET_DIR / "codepulse_duplicates.csv"
ARCHITECTURE_DOT_PATH = DATASET_DIR / "codepulse_architecture.dot"
ARCHITECTURE_PNG_PATH = DATASET_DIR / "codepulse_architecture.png"
ARCHITECTURE_SVG_PATH = DATASET_DIR / "codepulse_architecture.svg"
REVIEW_PATH = DATASET_DIR / "codepulse_review.csv"
REPORT_PATH = DATASET_DIR / "codepulse_report.html"
RUN_METADATA_PATH = DATASET_DIR / "codepulse_run.json"
MODEL_PATH = MODEL_DIR / "codepulse_defect_model.pkl"
MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.pkl"

LOGGER = logging.getLogger(__name__)


def project_path(path):
    """Resolve a relative CodePulse path from the project root."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def repository_identity(repository_url):
    """Return a stable identity for a GitHub URL or local repository path."""
    value = str(repository_url or "").strip().rstrip("/\\")
    if value.startswith("git@github.com:"):
        canonical = "https://github.com/" + value.split(":", 1)[1]
    elif re.match(r"^[\w.-]+/[\w.-]+(?:\.git)?$", value):
        canonical = "https://github.com/" + value
    else:
        parsed = urlparse(value)
        canonical = value
        if parsed.netloc.lower() in {"github.com", "www.github.com"}:
            path = parsed.path.strip("/").removesuffix(".git")
            canonical = f"https://github.com/{path}"
    canonical = canonical.lower().rstrip("/")
    name = canonical.rstrip("/").split("/")[-1] or "repository"
    name = name.removesuffix(".git")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return {
        "canonical_url": canonical,
        "repository_name": name,
        "key": f"{name}-{digest}",
    }


def write_run_metadata(repository_url, dataset_path=FEATURES_PATH,
                       predictions_path=PREDICTIONS_PATH):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    metadata = {
        "repository": repository_identity(repository_url),
        "dataset_path": str(Path(dataset_path).resolve()),
        "predictions_path": str(Path(predictions_path).resolve()),
    }
    RUN_METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def invalidate_analysis_artifacts(reason):
    """Remove artifacts that could otherwise be mistaken for this run."""
    for path in (
        FEATURES_PATH,
        PREDICTIONS_PATH,
        TECHNICAL_DEBT_PATH,
        DUPLICATES_PATH,
        ARCHITECTURE_DOT_PATH,
        ARCHITECTURE_PNG_PATH,
        ARCHITECTURE_SVG_PATH,
        REVIEW_PATH,
        REPORT_PATH,
        MODEL_PATH,
        MODEL_METADATA_PATH,
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            LOGGER.warning("Could not remove stale artifact %s: %s", path, error)
    try:
        RUN_METADATA_PATH.unlink(missing_ok=True)
    except OSError as error:
        LOGGER.warning("Could not remove run metadata: %s", error)
    LOGGER.warning("Analysis artifacts invalidated: %s", reason)


def dataset_is_valid_for_run(dataset, repository_url):
    """Check that a dataset is non-empty, structurally valid, and current."""
    required = {"file", "language", "bug_label"}
    if dataset is None or dataset.empty or not required.issubset(dataset.columns):
        return False
    try:
        metadata = json.loads(RUN_METADATA_PATH.read_text(encoding="utf-8"))
        return metadata.get("repository", {}).get("canonical_url") == repository_identity(
            repository_url
        )["canonical_url"]
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def predictions_are_valid_for_run(predictions, dataset, repository_url):
    """Check that predictions contain exactly the files in this run."""
    if predictions is None or predictions.empty or dataset is None or dataset.empty:
        return False
    if not {"file", "bug_probability", "risk_level"}.issubset(predictions.columns):
        return False
    if set(predictions["file"]) != set(dataset["file"]):
        return False
    try:
        metadata = json.loads(RUN_METADATA_PATH.read_text(encoding="utf-8"))
        return metadata.get("repository", {}).get("canonical_url") == repository_identity(
            repository_url
        )["canonical_url"]
    except (OSError, json.JSONDecodeError, TypeError):
        return False