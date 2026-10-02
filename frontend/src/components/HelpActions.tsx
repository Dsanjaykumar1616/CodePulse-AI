import { Link } from "react-router-dom";
import { AlertOctagon, BookOpen, GitPullRequestArrow, Network, Sprout, Mountain } from "lucide-react";
import { cx } from "./ui";

interface Counts {
  BEGINNER?: number;
  INTERMEDIATE?: number;
  ADVANCED?: number;
  openIssues?: number | null;
  issuesAvailable?: boolean;
}

/** "How can CodePulse help you?" — every action routes to a real view. */
export function HelpActions({ repoId, counts, compact }: { repoId: string | null; counts?: Counts; compact?: boolean }) {
  const base = repoId ? `/app/r/${repoId}` : null;
  const actions = [
    {
      to: base,
      icon: BookOpen,
      title: "Understand this repository",
      hint: "Major parts, key files and where to start reading",
    },
    {
      to: base && `${base}/opportunities?difficulty=BEGINNER`,
      icon: Sprout,
      title: "Find beginner contributions",
      hint: counts?.BEGINNER !== undefined ? `${counts.BEGINNER} estimated` : "Smaller, lower-risk changes",
    },
    {
      to: base && `${base}/opportunities?difficulty=INTERMEDIATE`,
      icon: GitPullRequestArrow,
      title: "Find intermediate contributions",
      hint: counts?.INTERMEDIATE !== undefined ? `${counts.INTERMEDIATE} estimated` : "Moderate complexity or churn",
    },
    {
      to: base && `${base}/opportunities?difficulty=ADVANCED`,
      icon: Mountain,
      title: "Find advanced contributions",
      hint: counts?.ADVANCED !== undefined ? `${counts.ADVANCED} estimated` : "Central or complex files",
    },
    {
      to: base && `${base}/issues`,
      icon: AlertOctagon,
      title: "Explore issues",
      hint:
        counts?.issuesAvailable === false
          ? "Issue data unavailable"
          : counts?.openIssues !== undefined && counts?.openIssues !== null
            ? `${counts.openIssues} open issues`
            : "Open issues and the files they mention",
    },
    {
      to: base && `${base}/architecture`,
      icon: Network,
      title: "Explore architecture",
      hint: "How the code is organised and connected",
    },
  ];
  return (
    <ul className={cx("grid gap-2", compact ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-3")}>
      {actions.map((action) => {
        const body = (
          <>
            <action.icon className={cx("h-4 w-4 shrink-0", action.to ? "text-accent" : "text-faint")} aria-hidden />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-ink">{action.title}</span>
              <span className="block truncate text-xs text-muted">{action.hint}</span>
            </span>
          </>
        );
        return (
          <li key={action.title}>
            {action.to ? (
              <Link
                to={action.to}
                className="flex h-full items-start gap-3 rounded border border-line bg-surface px-3.5 py-3 transition-colors hover:border-accent/50 hover:bg-raised/40"
              >
                {body}
              </Link>
            ) : (
              <span
                className="flex h-full cursor-not-allowed items-start gap-3 rounded border border-dashed border-line px-3.5 py-3 opacity-70"
                title="Analyze a repository first"
                aria-disabled="true"
              >
                {body}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
