class ContributorView:
    """Print one compact contributor-oriented summary from existing results."""

    @staticmethod
    def print_report(explanation, related_files, impact, history, plan):
        print("\n==========================================")
        print("        CODEPULSE CONTRIBUTOR VIEW")
        print("==========================================")
        print(f"File: {explanation['file']}")
        print(f"Risk: {explanation['risk_level'].upper()}")
        print(f"ML Probability: {explanation['bug_probability']:.0%}")
        print("\nWhy:")
        for reason in explanation["reasons"] or ["No high-risk rules matched"]:
            print(f"- {reason}")
        print("\nRelated Files:")
        if related_files:
            for related in related_files:
                print(f"- {related['file']} ({related['reason']})")
        else:
            print("- Related files could not be determined reliably.")
        print(f"\nDependency Impact: {impact['impact_level']}")
        print("Git History:")
        print(f"{history['commit_count']} commits, {history['contributors']} contributors, "
              f"{history['bug_fix_commits']} bug-fix commits")
        print(f"\nSuggested Contribution: {plan['contribution_type']}")
        print(f"Difficulty: {plan['difficulty']}")
        print("Contribution Plan:")
        for number, step in enumerate(plan["steps"], start=1):
            print(f"{number}. {step}")
        print("==========================================")
