export function fmtNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** 0–1 probability shown as a whole percentage. */
export function fmtPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return "never";
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (Number.isNaN(seconds)) return "—";
  if (seconds < 60) return "just now";
  const units: [number, string][] = [
    [60, "minute"],
    [3600, "hour"],
    [86400, "day"],
    [2592000, "month"],
    [31536000, "year"],
  ];
  let unit = units[0];
  for (const candidate of units) if (seconds >= candidate[0]) unit = candidate;
  const amount = Math.floor(seconds / unit[0]);
  return `${amount} ${unit[1]}${amount === 1 ? "" : "s"} ago`;
}

export function fmtDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes ? `${minutes}m ${seconds.toString().padStart(2, "0")}s` : `${seconds}s`;
}

export function splitPath(path: string): { dir: string; base: string } {
  const index = path.lastIndexOf("/");
  return index === -1 ? { dir: "", base: path } : { dir: path.slice(0, index + 1), base: path.slice(index + 1) };
}

export function capitalize(value: string | null | undefined): string {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

export type Severity = "low" | "medium" | "high" | "critical" | "none";

/** Maps the engine's level labels (Low/HIGH/Critical…) onto the severity scale. */
export function severityOf(level: string | null | undefined): Severity {
  switch ((level ?? "").toLowerCase()) {
    case "low":
    case "beginner":
    case "excellent":
    case "good":
      return "low";
    case "medium":
    case "moderate":
    case "intermediate":
      return "medium";
    case "high":
    case "advanced":
    case "poor":
      return "high";
    case "critical":
      return "critical";
    default:
      return "none";
  }
}

/** Health-style scores, higher is better (bands mirror RepositoryHealthScore._health_level). */
export function scoreSeverity(score: number | null | undefined): Severity {
  if (score === null || score === undefined) return "none";
  if (score >= 75) return "low";
  if (score >= 60) return "medium";
  if (score >= 40) return "high";
  return "critical";
}

/** Debt-style scores, higher is worse (bands mirror TechnicalDebtAnalyzer.classify). */
export function debtSeverity(score: number | null | undefined): Severity {
  if (score === null || score === undefined) return "none";
  if (score >= 90) return "critical";
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}

export const severityText: Record<Severity, string> = {
  low: "text-low",
  medium: "text-medium",
  high: "text-high",
  critical: "text-critical",
  none: "text-muted",
};

export const severityBg: Record<Severity, string> = {
  low: "bg-low",
  medium: "bg-medium",
  high: "bg-high",
  critical: "bg-critical",
  none: "bg-faint",
};

/** Historical risk signal as a 0–100 percentage (bands mirror DefectPredictionModel.classify_risk). */
export function riskSeverity(percent: number | null | undefined): Severity {
  if (percent === null || percent === undefined) return "none";
  if (percent >= 75) return "critical";
  if (percent >= 50) return "high";
  if (percent >= 25) return "medium";
  return "low";
}
