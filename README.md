# CodePulse AI

## Intelligent Codebase Health & Technical Debt Analyzer

CodePulse AI is an ML-based platform that analyzes GitHub repositories,
extracts source-code and Git-history metrics, predicts defect-prone files,
measures technical debt, detects duplicate code, generates architecture
diagrams, and provides code health insights through a dashboard.

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