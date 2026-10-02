"""Self-contained HTML export for an existing CodePulse analysis run."""

from html import escape
from pathlib import Path

from codepulse_runtime import REPORT_PATH, project_path


class HtmlReportGenerator:
    """Render already-computed CodePulse results without running analysis."""

    def __init__(self, output_path=REPORT_PATH):
        self.output_path = project_path(output_path)

    @staticmethod
    def _value(value, fallback="Not available"):
        if value is None or value == "":
            return fallback
        return escape(str(value))

    @staticmethod
    def _list(items, empty="Not available"):
        if not items:
            return f'<p class="muted">{escape(empty)}</p>'
        return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"

    @staticmethod
    def _table(headers, rows, empty="Not available"):
        if not rows:
            return f'<p class="muted">{escape(empty)}</p>'
        head = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    @staticmethod
    def _card(title, content):
        return f'<section class="card"><h2>{escape(title)}</h2>{content}</section>'

    def _overview(self, repository_info, dataset):
        languages = repository_info.get("languages", {}) if repository_info else {}
        language_text = ", ".join(
            f"{escape(str(name))} ({count})" for name, count in languages.items()
        ) or "Not available"
        content = (
            f"<div class=\"facts\"><div><b>Repository</b><span>{self._value(repository_info.get('repository_name') if repository_info else None)}</span></div>"
            f"<div><b>URL</b><span>{self._value(repository_info.get('repository_url') if repository_info else None)}</span></div>"
            f"<div><b>Files analyzed</b><span>{len(dataset) if dataset is not None else 'Not available'}</span></div>"
            f"<div><b>Languages</b><span>{language_text}</span></div>"
            f"<div><b>Commits</b><span>{self._value(repository_info.get('commits') if repository_info else None)}</span></div>"
            f"<div><b>Contributors</b><span>{self._value(repository_info.get('contributors') if repository_info else None)}</span></div></div>"
        )
        return self._card("Repository Overview", content)

    def _health(self, health_report):
        if not health_report:
            return self._card("Repository Health", '<p class="muted">Not available.</p>')
        content = (
            f"<div class=\"score\">{health_report.get('overall_score', 'Not available')}<small>/ 100</small></div>"
            f"<p>{self._value(health_report.get('health_level'))}</p>"
        )
        return self._card("Repository Health", content)

    def _ml(self, predictions, ml_results):
        if not ml_results:
            content = '<p class="muted">Not available. ML training was skipped or did not produce results.</p>'
        else:
            rows = []
            for name, result in ml_results.items():
                rows.append([escape(str(name)), escape(f"{result.get('f1', 0):.3f}"), escape(f"{result.get('roc_auc', 0):.3f}")])
            content = self._table(["Model", "F1", "ROC-AUC"], rows)
        risk_rows = []
        if predictions is not None and not predictions.empty:
            distribution = predictions["risk_level"].value_counts()
            risk_rows = [[escape(str(level)), str(count)] for level, count in distribution.items()]
            content += self._table(["Risk level", "Files"], risk_rows)
            top = predictions.head(10)
            content += self._table(
                ["File", "Probability", "Risk"],
                [[escape(str(row["file"])), f"{float(row['bug_probability']):.1%}", escape(str(row["risk_level"]))] for _, row in top.iterrows()],
            )
        return self._card("ML Defect Risk", content)

    def _debt(self, summary):
        if not summary:
            return self._card("Technical Debt", '<p class="muted">Not available.</p>')
        rows = [[escape(str(item.get("file"))), f"{item.get('technical_debt_score', 0):.1f}", escape(str(item.get("technical_debt_level"))), escape("; ".join(item.get("debt_reasons", [])))] for item in summary.get("top_files", [])]
        content = f"<div class=\"score\">{summary.get('repository_debt_score', 'Not available')}<small>/ 100</small></div><p>{self._value(summary.get('debt_level'))}</p>"
        content += self._table(["File", "Score", "Level", "Evidence"], rows)
        return self._card("Technical Debt", content)

    def _duplicates(self, summary):
        if not summary:
            return self._card("Duplicate Code", '<p class="muted">Not available.</p>')
        pairs = [[escape(str(item.get("file_a"))), escape(str(item.get("file_b"))), f"{item.get('similarity_score', 0):.1f}%", escape(str(item.get("similarity_level")))] for item in summary.get("top_pairs", [])]
        content = f"<p><b>Groups:</b> {summary.get('duplicate_groups', 0)} &nbsp; <b>High similarity:</b> {summary.get('high_similarity_groups', 0)}</p>"
        content += self._table(["File A", "File B", "Similarity", "Level"], pairs, "No significant duplication detected.")
        return self._card("Duplicate Code", content)

    def _architecture(self, report):
        if not report:
            return self._card("Architecture", '<p class="muted">Not available.</p>')
        content = (
            f"<p><b>Files:</b> {report.get('files_in_dependency_graph', 0)} &nbsp; "
            f"<b>Dependencies:</b> {report.get('dependency_relationships', 0)} &nbsp; "
            f"<b>Unresolved dependencies:</b> {report.get('unresolved_dependencies', 0)}</p>"
        )

        content += "<h3>Architecture Overview</h3>"
        overview = report.get("overview_rendered_paths", [])
        if overview:
            content += f'<img class="architecture" src="{escape(Path(overview[0]).name)}" alt="Architecture overview diagram">'
        else:
            content += '<p class="muted">Overview rendering unavailable; DOT representation was generated.</p>'

        content += "<h3>Most Connected Files</h3>"
        rows = [[escape(str(item["file"])), str(item["incoming_dependencies"]), str(item["outgoing_dependencies"]), str(item["total_connections"])] for item in report.get("centrality", [])[:10]]
        content += self._table(["Central file", "Incoming", "Outgoing", "Total"], rows)

        content += "<h3>Full Dependency Graph</h3>"
        rendered = report.get("rendered_paths", [])
        if rendered:
            content += f'<img class="architecture" src="{escape(Path(rendered[0]).name)}" alt="Full dependency graph">'
        else:
            content += '<p class="muted">Visual rendering unavailable; DOT representation was generated.</p>'
        return self._card("Architecture", content)

    def _review(self, summary):
        if not summary:
            return self._card("Rule-Based Code Review", '<p class="muted">Not available.</p>')
        rows = [[escape(str(item.get("severity"))), escape(str(item.get("rule_id"))), escape(str(item.get("file"))), escape(str(item.get("recommendation")))] for item in summary.get("top_findings", [])]
        content = f"<p><b>Total findings:</b> {summary.get('total_findings', 0)} &nbsp; <b>Critical:</b> {summary.get('critical_count', 0)} &nbsp; <b>High:</b> {summary.get('high_count', 0)}</p>"
        content += self._table(["Severity", "Rule", "File", "Recommendation"], rows, "No rule violations detected.")
        return self._card("Rule-Based Code Review", content)

    def _opportunities(self, opportunities):
        rows = [[escape(str(item.get("file"))), f"{item.get('opportunity_score', item.get('score', 0)):.2f}", escape(str(item.get("difficulty"))), escape(str(item.get("impact", "Not available"))), escape("; ".join(item.get("reasons", [])))] for item in (opportunities or [])[:10]]
        return self._card("Contributor Opportunities", self._table(["File", "Score", "Difficulty", "Impact", "Evidence"], rows))

    def _selected(self, selected):
        if not selected:
            return self._card("Selected File Intelligence", '<p class="muted">No selected-file analysis was available for this export.</p>')
        explanation = selected.get("explanation", {})
        content = f"<p><b>File:</b> {self._value(explanation.get('file'))}</p><p><b>Risk:</b> {self._value(explanation.get('risk_level'))} &nbsp; <b>Debt:</b> {self._value(selected.get('debt_level'))}</p>"
        content += self._list(explanation.get("reasons", []), "No risk reasons available.")
        content += f"<p><b>Dependency impact:</b> {self._value(selected.get('impact', {}).get('impact_level'))}</p>"
        content += f"<p><b>Git history:</b> {self._value(selected.get('history', {}).get('commit_count'))} commits</p>"
        content += self._list([step for step in selected.get("plan", {}).get("steps", [])], "No contribution plan available.")
        return self._card("Selected File Intelligence", content)

    def generate(self, repository_info=None, dataset=None, health_report=None,
                 predictions=None, ml_results=None, technical_debt_summary=None,
                 duplicate_summary=None, architecture_report=None,
                 review_summary=None, opportunities=None, selected=None):
        sections = [
            self._overview(repository_info or {}, dataset),
            self._health(health_report),
            self._ml(predictions, ml_results),
            self._debt(technical_debt_summary),
            self._duplicates(duplicate_summary),
            self._architecture(architecture_report),
            self._review(review_summary),
            self._opportunities(opportunities),
            self._selected(selected),
        ]
        repository_name = self._value((repository_info or {}).get("repository_name"))
        html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CodePulse AI Report - {repository_name}</title>
<style>
:root {{ color-scheme: light; --ink:#17202a; --muted:#667085; --line:#dfe5ec; --paper:#f5f7fa; --accent:#176b87; --danger:#a63d40; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--paper); color:var(--ink); font:14px/1.5 Segoe UI,Arial,sans-serif; }} main {{ max-width:1180px; margin:0 auto; padding:34px 20px 60px; }} header {{ background:#16324f; color:#fff; padding:28px; border-radius:10px; margin-bottom:18px; }} h1 {{ margin:0 0 6px; font-size:28px; }} h2 {{ margin:0 0 16px; font-size:19px; color:var(--accent); }} h3 {{ margin:18px 0 6px; font-size:14px; color:var(--ink); text-transform:uppercase; letter-spacing:.03em; }} .card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:20px; margin:16px 0; box-shadow:0 2px 8px #17202a0b; }} .facts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }} .facts div {{ border-left:3px solid var(--accent); padding-left:10px; }} .facts b,.facts span {{ display:block; }} .facts b {{ color:var(--muted); font-size:12px; text-transform:uppercase; }} .score {{ font-size:34px; font-weight:700; color:var(--accent); }} .score small {{ font-size:16px; color:var(--muted); }} .muted {{ color:var(--muted); }} table {{ width:100%; border-collapse:collapse; margin-top:14px; }} th,td {{ padding:9px 8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }} li {{ margin:5px 0; }} .architecture {{ display:block; max-width:100%; margin-top:16px; border:1px solid var(--line); }} footer {{ color:var(--muted); margin-top:20px; font-size:12px; }}
</style></head><body><main><header><h1>CodePulse AI Analysis Report</h1><div>{repository_name}</div><div>Generated from existing analysis results</div></header>{''.join(sections)}<footer>CodePulse AI static export. Unavailable values are reported explicitly.</footer></main></body></html>"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")
        return self.output_path
