class DependencyImpactAnalyzer:
    """Analyze the potential repository impact of modifying a target source file."""

    def analyze(self, file_path, dependency_graph, risk_level=None):
        if dependency_graph is None or not hasattr(dependency_graph, "dependencies"):
            return {
                "file": file_path,
                "depends_on": [],
                "used_by": [],
                "impact_level": "LOW",
                "reason": "Dependency impact could not be determined reliably.",
                "available": False,
                "risk_level": risk_level,
            }

        depends_on = sorted(dependency_graph.dependencies.get(file_path, set()))
        used_by = sorted(dependency_graph.used_by.get(file_path, set()))

        dependent_count = len(used_by)
        dependency_count = len(depends_on)
        total_connections = dependent_count + dependency_count

        # Explainable impact level classification based on repository connectivity
        if dependent_count >= 8 or total_connections >= 12:
            impact_level = "CRITICAL"
            reason = (
                "This file is a central core module with very high "
                "repository-wide connectivity."
            )
        elif dependent_count >= 4 or total_connections >= 6:
            impact_level = "HIGH"
            reason = "This file is connected to multiple application components."
        elif dependent_count >= 2 or total_connections >= 3:
            impact_level = "MEDIUM"
            reason = "Several related components depend on or interface with this file."
        elif total_connections == 1:
            impact_level = "LOW"
            reason = "Only one direct static dependency was detected."
        else:
            impact_level = "LOW"
            reason = "Few or no direct static dependencies were detected."

        checklist = [
            "Review dependent files",
            "Run relevant tests",
            "Keep the change isolated"
        ]

        return {
            "file": file_path,
            "depends_on": depends_on,
            "used_by": used_by,
            "dependent_count": dependent_count,
            "dependency_count": dependency_count,
            "total_connections": total_connections,
            "impact_level": impact_level,
            "reason": reason,
            "checklist": checklist,
            "available": True,
            "risk_level": risk_level,
        }

    @staticmethod
    def print_report(impact, risk_level=None):
        print("\n==========================================")
        print("       CONTRIBUTION IMPACT ANALYSIS")
        print("==========================================")
        print(f"\nTarget:\n{impact['file']}")

        # Use passed risk_level or risk_level stored in impact
        effective_risk = risk_level or impact.get("risk_level")
        if effective_risk:
            print(f"\nRisk:\n{str(effective_risk).upper()}")

        if not impact.get("available", True):
            print("\nDependency impact could not be determined reliably.")
            print("==========================================")
            return

        print("\nFiles it depends on:\n")
        if impact["depends_on"]:
            for item in impact["depends_on"]:
                print(item)
        else:
            print("None detected")

        print("\nFiles depending on it:\n")
        if impact["used_by"]:
            for item in impact["used_by"]:
                print(item)
        else:
            print("None detected")

        print(f"\nPotential Impact:\n{impact['impact_level']}")
        print(f"\nReason:\n\n{impact['reason']}")

        print("\nBefore modifying:")
        for item in impact.get("checklist", [
            "Review dependent files",
            "Run relevant tests",
            "Keep the change isolated"
        ]):
            print(f"✓ {item}")

        print("\nNote: This file has dependencies that may be affected. This is static analysis, not runtime prediction.")
        print("==========================================")
