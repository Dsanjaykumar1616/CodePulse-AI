# CodePulse AI

## Intelligent Codebase Health & Technical Debt Analyzer

CodePulse AI is an ML-based platform that analyzes GitHub repositories,
extracts source-code and Git-history metrics, predicts defect-prone files,
measures technical debt, detects duplicate code, generates architecture
diagrams, and provides code health insights through a web dashboard.

## Web application

The product is a web app. Users sign up, paste a GitHub URL, watch the
analysis run, and explore the results in the browser. The terminal is only
needed to start the servers during development.

```
React (frontend/)  ->  FastAPI (backend/)  ->  analysis service  ->  existing engine modules
                                  |
                              PostgreSQL
```

* `frontend/` - React + TypeScript + Vite + Tailwind, React Router, TanStack
  Query, Recharts and React Flow (interactive architecture graph).
* `backend/` - FastAPI, SQLAlchemy, Alembic, JWT auth. `app/services/engine_runner.py`
  runs the existing engine stage by stage (same order as
  `workspace.ContributorPipeline`) and `result_builder.py` turns its output
  into the JSON the UI reads. No analysis logic is duplicated.
* The engine (`analyzer/`, `metrics/`, `git_analysis/`, `ml/`, `analysis/`,
  `github/`) is unchanged. `main.py` and `workspace.py` still work as
  developer/debug CLIs.

### Requirements

* Python 3.10 or newer
* Node.js 18 or newer
* PostgreSQL 14 or newer
* On macOS, XGBoost needs OpenMP: `brew install libomp`
* Git, and optionally Graphviz (`dot`) for the PNG/SVG diagrams in the
  exported HTML report. The interactive graph does not need Graphviz.

### 1. PostgreSQL

macOS (Homebrew):

```bash
brew install postgresql@16
brew services start postgresql@16
createuser codepulse --pwprompt        # enter: codepulse
createdb codepulse --owner codepulse
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt        # also installs the engine's requirements
cp .env.example .env                   # then set JWT_SECRET (see below)
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET
alembic upgrade head                   # create the database tables
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Environment variables (`backend/.env`):

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL, default `postgresql+psycopg://codepulse:codepulse@localhost:5432/codepulse` |
| `JWT_SECRET` | Required. Long random string used to sign login tokens |
| `JWT_EXPIRE_MINUTES` | Login lifetime, default 10080 (7 days) |
| `CORS_ORIGINS` | Allowed frontend origins, default `http://localhost:5173` |
| `GITHUB_TOKEN` | Optional. Raises the GitHub API limit for issue analysis (60 -> 5000 requests/hour). No scopes needed |
| `MAX_FILE_INTELLIGENCE` | Optional. Files per analysis with precomputed file intelligence, default 3000 |
| `LOG_LEVEL` | Default `INFO` |

Without PostgreSQL you can try the app with SQLite by setting
`DATABASE_URL=sqlite:///./codepulse.db` before `alembic upgrade head`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

### Tests

```bash
# Existing engine regression suite (from the repository root)
python -m pytest tests -q              # or: python -m unittest discover tests

# Backend API, auth, jobs and integration tests
cd backend && python -m pytest

# Frontend
cd frontend && npm test && npm run build
```

The backend tests use a temporary SQLite database. One integration test runs
the real engine on a small local Git repository.

### How analysis runs

`POST /api/repositories` validates the GitHub URL and queues an analysis job.
A single background worker runs jobs one at a time, because the engine writes
its artifacts to fixed paths under `data/datasets/` and clears them at the
start of every run. The progress page polls `GET /api/analysis/{job_id}`.
Finished results are stored in PostgreSQL (one JSONB document per section), so
past analyses load instantly and survive restarts.

Main endpoints (all under `/api`, JWT bearer auth except signup/login):

* `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
* `GET|POST /repositories`, `GET|DELETE /repositories/{id}`, `POST /repositories/{id}/analyze`
* `GET /analysis/{job_id}`
* `GET /repositories/{id}/overview|health|risk|debt|duplicates|review|issues|opportunities`
* `GET /repositories/{id}/architecture?limit=&directory=&focus=&depth=`
* `GET /repositories/{id}/files` and `GET /repositories/{id}/files/intelligence?path=`
* `GET /repositories/{id}/report` (HTML export)
* `GET /repositories/{id}/guide` (contributor onboarding: directory groups, start-here files, roadmap)
* `GET /repositories/{id}/issues/{number}/files` (files CodePulse infers are related to an issue)
* `GET /repositories/{id}/issues/{number}/work` (a step-by-step plan for one issue: likely files, what uses them, related tests, estimated difficulty)

### Contributor guidance

`backend/app/services/guide.py` turns stored engine results into contributor
guidance without re-analysing code: directory groups and how they import each
other, possible entry points and core dependencies, the reasons behind each
opportunity, the engine conditions that set its difficulty, a readiness
checklist (no combined score), change impact (direct and second-level
dependents), and related tests. Everything is labelled by how it was found:
"detected" (from engine output, such as a test file importing the target),
"heuristic" (from documented naming rules) or "inferred" (issue text matching).

On the Issues page, beginner labels (for example "good first issue", "help wanted",
"documentation") are detected from GitHub. Each issue's difficulty is *estimated* from
the files it was matched to: the hardest file's engine difficulty, raised one level for
High/Critical risk, a central file, or three or more files. Issues with no matched file
show "Difficulty not estimated" and get a GitHub code-search link instead.
Directory descriptions come only from directory names and import structure.

The ML output is a historical risk signal learned from past bug-fix commits.
The UI never presents it as a confirmed probability of future defects.

## Engine

## Current Scope

Tier 1 - Core Implementation

## Development Phases

1. Project Setup & Requirements
2. Repository Analyzer
3. Code Metrics Extraction
4. Git History Analysis
5. Feature Engineering
6. ML-Based Defect Prediction
7. Technical Debt Analysis
8. Duplicate Code Detection
9. Architecture Diagram Generation
10. Rule-Based Code Review
11. Backend & Database
12. Dashboard & Integration

## Technical Debt Analysis

Phase 7 calculates an explainable 0-100 technical-debt score for each
analyzed file and for the repository as a whole. It combines repository-
relative complexity/file-size, available ML historical-risk probability,
maintainability debt, and Git churn. The intended weights are 35%, 25%, 10%,
and 10%; unavailable optional signals are excluded and the remaining weights
are renormalized.

Files are classified as LOW, MEDIUM, HIGH, or CRITICAL using documented score
bands. Results include evidence-based reasons, top debt-prone files, and
contributor-oriented context. Duplicate-code data is explicitly unavailable
until Phase 8 and is never fabricated. Results are saved to
`data/datasets/codepulse_technical_debt.csv`.

## Duplicate Code Detection

Phase 8 compares supported source files using normalized code tokens, ignoring
formatting and comments while safely normalizing identifiers. Comparisons are
filtered by source type and minimum token size. Similarity of 75% or more is
reported, with 80% classified as MEDIUM and 90% as HIGH. Pair evidence is
saved to `data/datasets/codepulse_duplicates.csv` and feeds the duplication
component of technical-debt scoring without fabricating results.

## Architecture Analysis

Phase 9 generates architecture diagrams from the existing static dependency
graph. It reports real source-file nodes, import/include edges, central files,
and unresolved references without inventing relationships. DOT output is
always generated at `data/datasets/codepulse_architecture.dot`; PNG and SVG
are rendered when the Graphviz `dot` executable is available. Large graphs are
limited to the most connected nodes for display while the underlying graph
remains available to contributor impact analysis.

## Rule-Based Code Review

Phase 10 produces deterministic findings for high complexity, large files,
deep nesting, low maintainability, low documentation ratio, high churn,
frequent bug-fix activity, and actual duplicate-code pairs. Findings use
repository-relative thresholds where appropriate, have LOW through CRITICAL
severity, include the triggering metric and recommendation, and are saved to
`data/datasets/codepulse_review.csv`. Selected-file findings are shown in the
contributor workflow.

## HTML Analysis Report

CodePulse AI can export an offline HTML analysis report containing repository
health, ML risk, technical debt, duplication, architecture, code review, and
contributor intelligence. The report is generated from existing analysis
results at `data/datasets/codepulse_report.html`.