import pandas as pd


class ContributionOpportunityGenerator:
    """Create evidence-based suggested contribution areas, categorized by difficulty."""

    PRIORITY_WEIGHTS = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1
    }

    DIFFICULTY_LEVELS = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]
    SCORE_WEIGHTS = {
        "priority": 2.0,
        "risk": 3.0,
        "debt": 3.5,
        "centrality": 5.0,
        "open_issue": 1.5,
        "review_finding": 0.25,
        "complexity": 1.0,
        "churn": 1.0,
    }

    @staticmethod
    def _threshold(series, quantile=0.75):
        values = pd.to_numeric(series, errors="coerce").fillna(0)
        return float(values.quantile(quantile))

    @staticmethod
    def _priority(probability, complexity_high, churn_high, bug_fixes_high):
        if probability >= 0.85 and (complexity_high or churn_high):
            return "CRITICAL"
        if probability >= 0.70 or (complexity_high and churn_high) or bug_fixes_high:
            return "HIGH"
        if probability >= 0.40 or complexity_high or churn_high:
            return "MEDIUM"
        return "LOW"

    def classify_difficulty(self, file_data, complexity_75, complexity_50,
                            churn_75, churn_50, loc_75, loc_50):
        """Classify opportunity difficulty based on measurable repository metrics."""
        complexity = float(file_data.get("complexity", 0))
        churn = float(file_data.get("code_churn", 0))
        loc = float(file_data.get("loc", 0))
        bug_fixes = int(file_data.get("bug_fix_commits", 0))
        probability = float(file_data.get("bug_probability", 0))
        nesting = int(file_data.get("nesting_depth", 0))
        impact_level = str(file_data.get("impact_level", "")).upper()
        related_count = int(file_data.get("related_count", 0) or 0)

        # Advanced: Large, complex, frequently churned, or high historical defect risk
        if ((complexity >= complexity_75 and complexity >= 30) or
                (complexity >= complexity_50 and churn >= churn_75) or
                (probability >= 0.75 and (complexity >= complexity_50 or churn >= churn_50)) or
                (loc >= loc_75 and complexity >= complexity_75) or
                bug_fixes >= 20 or
                impact_level in {"CRITICAL", "HIGH"} or
                related_count >= 6):
            return "ADVANCED"

        # Intermediate: Moderate complexity, moderate churn, or moderate size
        if (complexity >= complexity_50 or
                churn >= churn_50 or
                loc >= loc_50 or
                nesting >= 3 or
                bug_fixes >= 3 or
                probability >= 0.40):
            return "INTERMEDIATE"

        # Beginner: Low complexity, low churn, smaller files, documentation, small cleanup
        return "BEGINNER"

    def generate(self, dataset, predictions=None, limit=None, technical_debt=None,
                 dependency_graph=None, issue_matches=None, review_findings=None):
        if dataset.empty:
            return []

        data = dataset.copy()
        data["bug_probability"] = 0.0
        data["risk_level"] = "Not available"

        if predictions is not None and not predictions.empty:
            data = data.merge(
                predictions[["file", "bug_probability", "risk_level"]],
                on="file",
                how="left",
                suffixes=("", "_prediction")
            )
            data["bug_probability"] = data["bug_probability_prediction"].fillna(0)
            data["risk_level"] = data["risk_level_prediction"].fillna("Not available")

        debt_by_file = {}
        if technical_debt is not None and not technical_debt.empty:
            debt_by_file = technical_debt.set_index("file").to_dict("index")

        centrality = {}
        if dependency_graph is not None and hasattr(dependency_graph, "dependencies"):
            centrality = {
                file_path: len(dependency_graph.dependencies.get(file_path, set()))
                + len(dependency_graph.used_by.get(file_path, set()))
                for file_path in dependency_graph.dependencies
            }
        max_centrality = max(centrality.values(), default=0) or 1

        review_by_file = {}
        if review_findings is not None and not review_findings.empty:
            review_by_file = review_findings.groupby("file").size().to_dict()

        complexity_75 = self._threshold(data["complexity"], 0.75)
        complexity_50 = self._threshold(data["complexity"], 0.50)
        churn_75 = self._threshold(data["code_churn"], 0.75)
        churn_50 = self._threshold(data["code_churn"], 0.50)
        loc_75 = self._threshold(data["loc"], 0.75)
        loc_50 = self._threshold(data["loc"], 0.50)
        comment_25 = self._threshold(data["comment_ratio"], 0.25)

        opportunities = []

        for _, file_data in data.iterrows():
            complexity = float(file_data["complexity"])
            churn = float(file_data["code_churn"])
            loc = int(file_data["loc"])
            comment_ratio = float(file_data["comment_ratio"])
            bug_fixes = int(file_data["bug_fix_commits"])
            probability = float(file_data["bug_probability"])
            debt = debt_by_file.get(file_data["file"], {})
            debt_level = debt.get("technical_debt_level")
            debt_score = float(debt.get("technical_debt_score", 0) or 0)
            centrality_value = centrality.get(file_data["file"], 0)
            impact_level = ""
            if dependency_graph is not None and file_data["file"] in centrality:
                incoming = len(dependency_graph.used_by.get(file_data["file"], set()))
                total = centrality_value
                impact_level = (
                    "CRITICAL" if incoming >= 8 or total >= 12 else
                    "HIGH" if incoming >= 4 or total >= 6 else
                    "MEDIUM" if incoming >= 2 or total >= 3 else "LOW"
                )
            file_data["impact_level"] = impact_level
            file_data["related_count"] = centrality_value

            complexity_high = complexity > 0 and complexity >= complexity_75
            churn_high = churn > 0 and churn >= churn_75
            bug_fixes_high = bug_fixes >= 10
            documentation_low = loc >= 20 and comment_ratio <= comment_25

            difficulty = self.classify_difficulty(
                file_data, complexity_75, complexity_50,
                churn_75, churn_50, loc_75, loc_50
            )

            priority = self._priority(
                probability, complexity_high, churn_high, bug_fixes_high
            )

            matched_issues = (issue_matches or {}).get(file_data["file"], [])
            open_issues = [
                issue for issue in matched_issues
                if str(issue.get("state", "UNKNOWN")).upper() == "OPEN"
                and str(issue.get("relevance", "")).upper() in {"HIGH", "MEDIUM"}
            ]
            closed_issues = [
                issue for issue in matched_issues
                if str(issue.get("state", "UNKNOWN")).upper() == "CLOSED"
            ]

            reasons = []
            if difficulty == "ADVANCED":
                if complexity_high:
                    reasons.append(
                        f"Complexity {int(complexity)} is in the repository's highest range"
                    )
                if churn_high:
                    reasons.append(
                        f"Code churn {int(churn)} is in the repository's highest range"
                    )
                if bug_fixes > 0:
                    reasons.append(f"Historical bug-fix commits: {bug_fixes}")
                if probability >= 0.50:
                    reasons.append(f"ML historical-risk probability: {probability:.0%}")
                if debt_level in {"HIGH", "CRITICAL"}:
                    reasons.append(f"Technical debt score: {debt_score:.0f}/100 ({debt_level})")
                title = f"Refactor {file_data['file']}"
                action = "Review complex functions and split them into smaller, modular units."

            elif difficulty == "INTERMEDIATE":
                if complexity >= complexity_50 and complexity > 0:
                    reasons.append(f"Moderate cyclomatic complexity ({int(complexity)})")
                if churn >= churn_50 and churn > 0:
                    reasons.append(f"Frequently modified file (code churn: {int(churn)})")
                if bug_fixes > 0:
                    reasons.append(f"Past bug-fix commits ({bug_fixes})")
                if probability >= 0.40:
                    reasons.append(f"Elevated defect probability ({probability:.0%})")
                if debt_level in {"HIGH", "CRITICAL"}:
                    reasons.append(f"Technical debt score: {debt_score:.0f}/100 ({debt_level})")
                if not reasons:
                    reasons.append(f"File size: {loc} lines of code")
                title = f"Simplify logic in {file_data['file']}"
                action = "Refactor nested branches, reduce duplication, or add focused unit tests."

            else:  # BEGINNER
                if documentation_low:
                    reasons.append("Low comment ratio for file logic")
                    title = f"Improve documentation in {file_data['file']}"
                    action = "Add docstrings, comments, or usage documentation."
                elif loc <= 50 and complexity <= 5:
                    reasons.append(f"Compact file ({loc} LOC) with simple control flow")
                    title = f"Simplify small function in {file_data['file']}"
                    action = "Review formatting, docstrings, or add basic unit tests."
                else:
                    reasons.append("Manageable complexity suitable for small contributions")
                    title = f"Review and clean up {file_data['file']}"
                    action = "Clean up unused code, improve readability, or add tests."

                if debt_level in {"HIGH", "CRITICAL"}:
                    reasons.append(f"Technical debt score: {debt_score:.0f}/100 ({debt_level})")

            if centrality_value >= 2:
                reasons.append(f"Central dependency with {centrality_value} direct connections")
            if open_issues:
                reasons.append(f"Related OPEN GitHub issue ({len(open_issues)} found)")
            if closed_issues and not open_issues:
                reasons.append("Related CLOSED issue available as historical context")
            if review_by_file.get(file_data["file"], 0):
                reasons.append(
                    f"Evidence-based code review findings: {review_by_file[file_data['file']]}"
                )

            difficulty_adjustment = {
                "BEGINNER": 0.5,
                "INTERMEDIATE": 0.0,
                "ADVANCED": -0.5,
            }[difficulty]
            opportunity_score = (
                self.PRIORITY_WEIGHTS.get(priority, 1) * self.SCORE_WEIGHTS["priority"]
                + probability * self.SCORE_WEIGHTS["risk"]
                + (debt_score / 100) * self.SCORE_WEIGHTS["debt"]
                + (centrality_value / max_centrality) * self.SCORE_WEIGHTS["centrality"]
                + min(len(open_issues), 3) * self.SCORE_WEIGHTS["open_issue"]
                + min(review_by_file.get(file_data["file"], 0), 3) * self.SCORE_WEIGHTS["review_finding"]
                + (self.SCORE_WEIGHTS["complexity"] if complexity_high else 0.0)
                + (self.SCORE_WEIGHTS["churn"] if churn_high else 0.0)
                + difficulty_adjustment
            )

            opportunities.append({
                "title": title,
                "file": file_data["file"],
                "priority": priority,
                "difficulty": difficulty,
                "suggested_for": f"Suggested for {difficulty.capitalize()}",
                "reasons": reasons,
                "suggested_action": action,
                "score": round(opportunity_score, 2),
                "impact_score": round(opportunity_score, 2),
                "opportunity_score": round(opportunity_score, 2),
                "impact": impact_level or "Not available",
                "centrality": centrality_value if dependency_graph is not None else None,
                "related_files": (
                    sorted(
                        set(dependency_graph.dependencies.get(file_data["file"], set()))
                        | set(dependency_graph.used_by.get(file_data["file"], set()))
                    )[:8]
                    if dependency_graph is not None else []
                ),
                "open_issue_count": len(open_issues),
                "closed_issue_count": len(closed_issues),
                "related_issue_status": (
                    "OPEN" if open_issues else
                    "CLOSED" if closed_issues else
                    "NONE/UNAVAILABLE"
                ),
            })

        # Sort by the combined opportunity score; priority breaks ties.
        sorted_opportunities = sorted(
            opportunities,
            key=lambda item: (
                item["score"],
                self.PRIORITY_WEIGHTS.get(item["priority"], 1),
            ),
            reverse=True
        )

        if limit:
            return sorted_opportunities[:limit]
        return sorted_opportunities

    @classmethod
    def filter_by_level(cls, opportunities, level):
        """Filter opportunities by contributor level (BEGINNER, INTERMEDIATE, ADVANCED, ALL)."""
        normalized = str(level).strip().upper()
        if normalized in {"ALL", "4", "4. ALL"}:
            return opportunities
        if normalized in {"BEGINNER", "1", "1. BEGINNER"}:
            return [op for op in opportunities if op["difficulty"] == "BEGINNER"]
        if normalized in {"INTERMEDIATE", "2", "2. INTERMEDIATE"}:
            return [op for op in opportunities if op["difficulty"] == "INTERMEDIATE"]
        if normalized in {"ADVANCED", "3", "3. ADVANCED"}:
            return [op for op in opportunities if op["difficulty"] == "ADVANCED"]
        return opportunities

    @classmethod
    def print_grouped_report(cls, opportunities, level_filter="ALL", limit_per_group=5):
        """Print opportunities formatted cleanly by contributor level."""
        print("\n==========================================")
        print("     SUGGESTED CONTRIBUTION OPPORTUNITIES")
        print("==========================================")
        print("Note: Opportunities are suggested based on measurable file metrics.")
        print("Choose the level that matches your desired contribution scope.\n")

        if not opportunities:
            print("No contribution opportunities met the current evidence rules.")
            print("==========================================")
            return

        normalized = str(level_filter).strip().upper()
        if normalized in {"BEGINNER", "1", "1. BEGINNER"}:
            levels = ["BEGINNER"]
        elif normalized in {"INTERMEDIATE", "2", "2. INTERMEDIATE"}:
            levels = ["INTERMEDIATE"]
        elif normalized in {"ADVANCED", "3", "3. ADVANCED"}:
            levels = ["ADVANCED"]
        else:
            levels = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]

        found_any = False
        for lvl in levels:
            group = [op for op in opportunities if op["difficulty"] == lvl]
            if not group:
                continue

            found_any = True
            print(f"--- {lvl} OPPORTUNITIES ({op['suggested_for'] if (op := group[0]) else ''}) ---")
            for index, opportunity in enumerate(group[:limit_per_group], start=1):
                print(f"\n{index}. {opportunity['title']}")
                print(f"   File: {opportunity['file']}")
                print(f"   Priority: {opportunity['priority']}")
                print(f"   Opportunity Score: {opportunity.get('opportunity_score', opportunity.get('score', 0)):.2f}")
                print(f"   Difficulty: {opportunity['difficulty']} ({opportunity['suggested_for']})")
                print(f"   Impact: {opportunity.get('impact', 'Not available')}")
                print(f"   Issue status: {opportunity.get('related_issue_status', 'NONE/UNAVAILABLE')}")
                print("   Evidence:")
                for reason in opportunity["reasons"]:
                    print(f"   - {reason}")
                print(f"   Suggested action: {opportunity['suggested_action']}")
            print()

        if not found_any:
            print(f"No opportunities found matching level: {level_filter}")

        print("==========================================")

    @classmethod
    def print_report(cls, opportunities):
        """Default print report for backward compatibility."""
        cls.print_grouped_report(opportunities, level_filter="ALL", limit_per_group=5)

    def interactive_filter(self, opportunities):
        """Terminal interactive interface to filter opportunities by contributor level."""
        if not opportunities:
            print("\nNo contribution opportunities available.")
            return

        print("\n==========================================")
        print("      FIND CONTRIBUTION OPPORTUNITIES")
        print("==========================================")
        print("\nChoose contributor level:")
        print("1. Beginner")
        print("2. Intermediate")
        print("3. Advanced")
        print("4. All")

        choice = input("\nEnter choice (1-4, or press Enter for All): ").strip()
        level_map = {
            "1": "BEGINNER",
            "beginner": "BEGINNER",
            "2": "INTERMEDIATE",
            "intermediate": "INTERMEDIATE",
            "3": "ADVANCED",
            "advanced": "ADVANCED",
            "4": "ALL",
            "all": "ALL",
            "": "ALL",
        }
        selected_level = level_map.get(choice.lower(), "ALL")
        self.print_grouped_report(opportunities, level_filter=selected_level, limit_per_group=10)
