"""Test the ContributorWorkspace on a real public repository."""
import sys
import traceback

from workspace import ContributorWorkspace


REPO_URL = "https://github.com/pallets/flask"


def main():
    workspace = ContributorWorkspace()

    print("=" * 60)
    print(f"Testing ContributorWorkspace on: {REPO_URL}")
    print("=" * 60)

    success = workspace.run_analysis(REPO_URL)
    if not success:
        print("\nAnalysis failed. Aborting tests.")
        sys.exit(1)

    print("\nAnalysis completed. Testing menu options...\n")

    tests = [
        ("Repository Health", workspace.option_repository_health),
        ("Contribution Opportunities", workspace.option_contribution_opportunities),
        ("Beginner Opportunities", lambda: workspace.option_filter_opportunities("BEGINNER")),
        ("Intermediate Opportunities", lambda: workspace.option_filter_opportunities("INTERMEDIATE")),
        ("Advanced Opportunities", lambda: workspace.option_filter_opportunities("ADVANCED")),
        ("Top Risk Files", workspace.option_view_top_risk_files),
        ("View GitHub Issues", workspace.option_view_github_issues),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print(f"{'='*60}")
            test_func()
            passed += 1
            print(f"\n[PASS] {name}")
        except Exception as error:
            failed += 1
            print(f"\n[FAIL] {name}")
            print(f"Error: {error}")
            traceback.print_exc()

    # Test file analysis with a fallback file
    print(f"\n{'='*60}")
    print("TEST: Analyze a File")
    print(f"{'='*60}")

    test_file = None
    if workspace.dataset is not None and not workspace.dataset.empty:
        test_file = workspace.dataset["file"].iloc[0]

    if test_file:
        print(f"Testing with file: {test_file}")
        original_input = __builtins__.input
        __builtins__.input = lambda prompt="": test_file
        try:
            workspace.option_analyze_file()
            passed += 1
            print(f"\n[PASS] Analyze a File")
        except Exception as error:
            failed += 1
            print(f"\n[FAIL] Analyze a File")
            print(f"Error: {error}")
            traceback.print_exc()
        finally:
            __builtins__.input = original_input
    else:
        failed += 1
        print("\n[FAIL] Analyze a File - no files in dataset")

    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    if failed == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{failed} test(s) failed.")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
