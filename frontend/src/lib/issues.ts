import type { Difficulty, Issue } from "../types/api";

const DAY = 86_400_000;

export function daysSince(value: string | null | undefined, now = Date.now()): number | null {
  if (!value) return null;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return null;
  return Math.max(0, Math.floor((now - time) / DAY));
}

/** An open issue nobody has touched for a year may no longer be wanted. */
export const STALE_DAYS = 365;
export const ACTIVE_DAYS = 30;

export function isStale(issue: Issue, now = Date.now()): boolean {
  const days = daysSince(issue.updated_at ?? issue.created_at, now);
  return issue.state === "OPEN" && days !== null && days > STALE_DAYS;
}

export function hasSignal(issue: Issue, kind: "beginner" | "help_wanted" | "documentation"): boolean {
  return (issue.signals ?? []).some((signal) => signal.kind === kind);
}

/**
 * How suitable an open issue looks for a beginner. A simple, visible rule:
 *   +3 beginner label (e.g. "good first issue"), +1 "help wanted", +1 documentation label,
 *   +2 estimated Beginner, +1 estimated Intermediate, -1 estimated Advanced,
 *   +1 updated in the last 30 days, -2 not updated for over a year.
 * Closed issues are never suggested.
 */
export function beginnerFit(issue: Issue, now = Date.now()): { score: number; reasons: string[] } {
  if (issue.state !== "OPEN") return { score: Number.NEGATIVE_INFINITY, reasons: [] };
  let score = 0;
  const reasons: string[] = [];
  const signals = issue.signals ?? [];
  const beginner = signals.find((signal) => signal.kind === "beginner");
  if (beginner) {
    score += 3;
    reasons.push(`Labelled “${beginner.label}” on GitHub`);
  }
  const help = signals.find((signal) => signal.kind === "help_wanted");
  if (help) {
    score += 1;
    reasons.push(`Labelled “${help.label}”`);
  }
  const docs = signals.find((signal) => signal.kind === "documentation");
  if (docs) {
    score += 1;
    reasons.push("Documentation work");
  }
  const level: Difficulty | null | undefined = issue.difficulty?.level;
  if (level === "BEGINNER") {
    score += 2;
    reasons.push("Estimated Beginner difficulty");
  } else if (level === "INTERMEDIATE") {
    score += 1;
  } else if (level === "ADVANCED") {
    score -= 1;
  }
  const updated = daysSince(issue.updated_at ?? issue.created_at, now);
  if (updated !== null && updated <= ACTIVE_DAYS) {
    score += 1;
    reasons.push("Active in the last month");
  } else if (updated !== null && updated > STALE_DAYS) {
    score -= 2;
  }
  return { score, reasons };
}

/** Open issues worth suggesting first: at least one positive reason, best score first. */
export function suggestedIssues(issues: Issue[], limit = 3, now = Date.now()): { issue: Issue; reasons: string[] }[] {
  return issues
    .map((issue) => ({ issue, ...beginnerFit(issue, now) }))
    .filter((item) => item.score > 0 && item.reasons.length > 0)
    .sort((a, b) => b.score - a.score || (daysSince(a.issue.updated_at, now) ?? 1e9) - (daysSince(b.issue.updated_at, now) ?? 1e9))
    .slice(0, limit)
    .map(({ issue, reasons }) => ({ issue, reasons }));
}

export type IssueSort = "beginner" | "updated" | "newest";

export function sortIssues(issues: Issue[], sort: IssueSort, now = Date.now()): Issue[] {
  const time = (value: string | null) => (value ? new Date(value).getTime() || 0 : 0);
  const copy = [...issues];
  if (sort === "updated") return copy.sort((a, b) => time(b.updated_at) - time(a.updated_at));
  if (sort === "newest") return copy.sort((a, b) => time(b.created_at) - time(a.created_at));
  return copy.sort((a, b) => {
    const diff = beginnerFit(b, now).score - beginnerFit(a, now).score;
    return Number.isNaN(diff) || diff === 0 ? time(b.updated_at) - time(a.updated_at) : diff;
  });
}
