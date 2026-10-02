import { describe, expect, it } from "vitest";
import { isGitHubUrl } from "../components/AnalyzeForm";
import { passwordStrength } from "../pages/Auth";
import { layeredLayout } from "../lib/graphLayout";
import { debtSeverity, riskSeverity, scoreSeverity, severityOf, splitPath } from "../lib/format";
import { beginnerFit, isStale, sortIssues, suggestedIssues } from "../lib/issues";
import type { GraphNode, Issue } from "../types/api";

describe("isGitHubUrl", () => {
  it("accepts the forms the backend accepts", () => {
    expect(isGitHubUrl("https://github.com/psf/requests")).toBe(true);
    expect(isGitHubUrl("https://github.com/psf/requests.git")).toBe(true);
    expect(isGitHubUrl("github.com/psf/requests")).toBe(true);
    expect(isGitHubUrl("git@github.com:psf/requests.git")).toBe(true);
    expect(isGitHubUrl("psf/requests")).toBe(true);
    expect(isGitHubUrl("https://github.com/psf/requests/tree/main/src")).toBe(true);
  });

  it("rejects other hosts, local paths and junk", () => {
    expect(isGitHubUrl("https://gitlab.com/psf/requests")).toBe(false);
    expect(isGitHubUrl("/etc/passwd")).toBe(false);
    expect(isGitHubUrl("../secret/repo")).toBe(false);
    expect(isGitHubUrl("https://github.com/psf")).toBe(false);
    expect(isGitHubUrl("")).toBe(false);
  });
});

describe("passwordStrength", () => {
  it("scores longer, mixed passwords higher", () => {
    expect(passwordStrength("abc").score).toBeLessThan(passwordStrength("abcdefgh1").score);
    expect(passwordStrength("Abcdefgh1234!").label).toBe("Strong");
  });
});

describe("severity bands mirror the engine", () => {
  it("maps debt scores like TechnicalDebtAnalyzer.classify", () => {
    expect(debtSeverity(95)).toBe("critical");
    expect(debtSeverity(80)).toBe("high");
    expect(debtSeverity(60)).toBe("medium");
    expect(debtSeverity(10)).toBe("low");
    expect(debtSeverity(null)).toBe("none");
  });
  it("maps risk percentages like DefectPredictionModel.classify_risk", () => {
    expect(riskSeverity(80)).toBe("critical");
    expect(riskSeverity(55)).toBe("high");
    expect(riskSeverity(30)).toBe("medium");
    expect(riskSeverity(5)).toBe("low");
  });
  it("maps health scores like RepositoryHealthScore._health_level", () => {
    expect(scoreSeverity(80)).toBe("low");
    expect(scoreSeverity(65)).toBe("medium");
    expect(scoreSeverity(45)).toBe("high");
    expect(scoreSeverity(20)).toBe("critical");
  });
  it("reads engine level labels", () => {
    expect(severityOf("Critical")).toBe("critical");
    expect(severityOf("HIGH")).toBe("high");
    expect(severityOf("BEGINNER")).toBe("low");
    expect(severityOf("Not available")).toBe("none");
  });
});

describe("splitPath", () => {
  it("separates directory and file name", () => {
    expect(splitPath("src/core/payment.py")).toEqual({ dir: "src/core/", base: "payment.py" });
    expect(splitPath("setup.py")).toEqual({ dir: "", base: "setup.py" });
  });
});

const node = (id: string): GraphNode => ({
  id,
  label: id,
  directory: "(root)",
  language: "Python",
  incoming: 0,
  outgoing: 0,
  total: 0,
  centrality: 0,
  risk_probability: null,
  risk_level: null,
  debt_score: null,
  debt_level: null,
});

describe("layeredLayout", () => {
  it("places importers left of the files they import", () => {
    const positions = layeredLayout(
      [node("app.py"), node("service.py"), node("db.py")],
      [
        { source: "app.py", target: "service.py" },
        { source: "service.py", target: "db.py" },
      ],
    );
    expect(positions.get("app.py")!.x).toBeLessThan(positions.get("service.py")!.x);
    expect(positions.get("service.py")!.x).toBeLessThan(positions.get("db.py")!.x);
  });

  it("survives import cycles and positions every node", () => {
    const positions = layeredLayout(
      [node("a"), node("b"), node("c"), node("lonely")],
      [
        { source: "a", target: "b" },
        { source: "b", target: "c" },
        { source: "c", target: "a" },
      ],
    );
    expect(positions.size).toBe(4);
    for (const position of positions.values()) {
      expect(Number.isFinite(position.x)).toBe(true);
      expect(Number.isFinite(position.y)).toBe(true);
    }
  });
});

describe("issue suggestions", () => {
  const now = new Date("2026-10-01T00:00:00Z").getTime();
  const base = {
    url: null, author: null, comments: 0, description: "", related_files: [], labels: [] as string[],
    created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-20T00:00:00Z",
  };
  const issue = (over: Partial<Issue>): Issue => ({ number: 1, title: "t", state: "OPEN", ...base, ...over }) as Issue;
  const estimated = (level: "BEGINNER" | "INTERMEDIATE" | "ADVANCED") => ({
    status: "ESTIMATED" as const, level, basis: [], files_considered: [], reason: null,
  });

  it("scores beginner labels and easy estimates higher", () => {
    const good = issue({ number: 1, signals: [{ kind: "beginner", label: "good first issue" }], difficulty: estimated("BEGINNER") });
    const hard = issue({ number: 2, difficulty: estimated("ADVANCED") });
    expect(beginnerFit(good, now).score).toBe(6);
    expect(beginnerFit(good, now).reasons[0].includes("good first issue")).toBe(true);
    expect(beginnerFit(hard, now).score).toBe(0);
  });

  it("never suggests closed issues and penalises stale ones", () => {
    const closed = issue({ state: "CLOSED", signals: [{ kind: "beginner", label: "easy" }] });
    const stale = issue({ number: 3, updated_at: "2024-01-01T00:00:00Z", signals: [{ kind: "help_wanted", label: "help wanted" }] });
    expect(suggestedIssues([closed, stale], 3, now)).toEqual([]);
    expect(isStale(stale, now)).toBe(true);
  });

  it("sorts by beginner fit", () => {
    const a = issue({ number: 1, difficulty: estimated("ADVANCED") });
    const b = issue({ number: 2, signals: [{ kind: "documentation", label: "docs" }] });
    expect(sortIssues([a, b], "beginner", now).map((item) => item.number)).toEqual([2, 1]);
  });
});
