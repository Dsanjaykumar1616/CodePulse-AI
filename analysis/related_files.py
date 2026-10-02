class RelatedFilesFinder:
    """Find local source files related by a verified static relationship."""

    def find(self, file_path, dependency_graph, limit=8):
        related = {}

        for target in dependency_graph.dependencies.get(file_path, set()):
            related[target] = "Imported by the selected file"

        for source in dependency_graph.used_by.get(file_path, set()):
            related[source] = "Imports the selected file"

        return [
            {"file": related_file, "reason": reason}
            for related_file, reason in sorted(related.items())[:limit]
        ]

    @staticmethod
    def print_report(file_path, related_files):
        print("\n==========================================")
        print("              RELATED FILES")
        print("==========================================")
        print(f"Selected: {file_path}")
        if not related_files:
            print("\nRelated files could not be determined reliably.")
        else:
            print()
            for index, related in enumerate(related_files, start=1):
                print(f"{index}. {related['file']}")
                print(f"   Reason: {related['reason']}")
        print("==========================================")
