import { Link } from "react-router-dom";
import {
  Activity,
  Boxes,
  GitBranch,
  GitPullRequestArrow,
  HeartPulse,
  Network,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { Logo } from "../components/Logo";
import { Button, cx } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const FEATURES = [
  {
    icon: HeartPulse,
    title: "Codebase health",
    body: "A 0–100 health score built from code quality, Git stability, maintainability and historical risk, with the files behind each component.",
  },
  {
    icon: Activity,
    title: "ML risk analysis",
    body: "Logistic Regression, Random Forest and XGBoost are trained on the repository's own bug-fix history to produce a historical risk signal per file.",
  },
  {
    icon: Boxes,
    title: "Technical debt",
    body: "An explainable debt score per file from complexity, historical risk, duplication, maintainability and churn, with the evidence for each.",
  },
  {
    icon: Network,
    title: "Architecture intelligence",
    body: "An interactive dependency graph from static imports. See central files, who depends on a file, and what a change could affect.",
  },
  {
    icon: ShieldCheck,
    title: "Code review",
    body: "Deterministic review rules flag high complexity, large files, deep nesting, low documentation, high churn and duplicated code.",
  },
  {
    icon: GitPullRequestArrow,
    title: "Contribution opportunities",
    body: "Files ranked as places to contribute, with a difficulty level, related GitHub issues and a step-by-step plan for your first change.",
  },
];

const STEPS = [
  { title: "Paste a GitHub URL", body: "Any public repository with Python, JavaScript, TypeScript, React, HTML, CSS or Java code." },
  { title: "CodePulse analyzes it", body: "Code metrics, Git history, ML risk, debt, duplicates, dependencies, review rules and issues." },
  { title: "Explore and contribute", body: "Open any file to see why it matters, what it touches and a plan for changing it." },
];

/** A schematic of the product layout. It deliberately shows no numbers. */
function DashboardPreview() {
  const bars = [72, 58, 44, 36, 28, 21];
  return (
    <figure className="panel overflow-hidden" aria-label="Schematic preview of the CodePulse repository dashboard">
      <div className="flex items-center gap-1.5 border-b border-line bg-raised/60 px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-line" />
        <span className="h-2.5 w-2.5 rounded-full bg-line" />
        <span className="h-2.5 w-2.5 rounded-full bg-line" />
        <span className="ml-3 h-4 w-48 rounded bg-line/70" />
      </div>
      <div className="flex">
        <div className="hidden w-36 shrink-0 space-y-2 border-r border-line p-3 sm:block">
          {["Overview", "Health", "Risky files", "Technical debt", "Architecture", "Opportunities"].map((item, index) => (
            <div
              key={item}
              className={cx("rounded px-2 py-1 text-[11px]", index === 0 ? "bg-raised text-ink" : "text-faint")}
            >
              {item}
            </div>
          ))}
        </div>
        <div className="min-w-0 flex-1 space-y-3 p-3">
          <div className="grid grid-cols-3 gap-2">
            {["Health score", "Technical debt", "Risk signal"].map((label, index) => (
              <div key={label} className="rounded border border-line p-2">
                <p className="text-[10px] text-faint">{label}</p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-raised">
                  <div
                    className={cx("h-full rounded-full", index === 0 ? "bg-low" : index === 1 ? "bg-medium" : "bg-high")}
                    style={{ width: `${[68, 45, 30][index]}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-5 gap-2">
            <div className="col-span-3 rounded border border-line p-2">
              <p className="text-[10px] text-faint">Files by historical risk</p>
              <div className="mt-2 space-y-1.5">
                {bars.map((width, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <span className="h-1.5 w-16 rounded bg-line/80" />
                    <span
                      className={cx("h-1.5 rounded", index < 2 ? "bg-critical/80" : index < 4 ? "bg-high/70" : "bg-medium/60")}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                ))}
              </div>
            </div>
            <div className="col-span-2 rounded border border-line p-2">
              <p className="text-[10px] text-faint">Dependencies</p>
              <svg viewBox="0 0 120 80" className="mt-1 w-full" aria-hidden>
                <g stroke="rgb(var(--faint))" strokeOpacity="0.6" strokeWidth="1">
                  <line x1="60" y1="40" x2="20" y2="16" />
                  <line x1="60" y1="40" x2="22" y2="64" />
                  <line x1="60" y1="40" x2="100" y2="14" />
                  <line x1="60" y1="40" x2="102" y2="44" />
                  <line x1="60" y1="40" x2="88" y2="70" />
                  <line x1="100" y1="14" x2="102" y2="44" />
                </g>
                <circle cx="60" cy="40" r="9" fill="rgb(var(--accent))" />
                {[
                  [20, 16],
                  [22, 64],
                  [100, 14],
                  [102, 44],
                  [88, 70],
                ].map(([x, y]) => (
                  <circle key={`${x}-${y}`} cx={x} cy={y} r="5" fill="rgb(var(--surface))" stroke="rgb(var(--faint))" />
                ))}
              </svg>
            </div>
          </div>
        </div>
      </div>
      <figcaption className="border-t border-line px-3 py-2 text-xs text-faint">
        Layout preview. Every value in the app comes from analyzing your repository.
      </figcaption>
    </figure>
  );
}

export default function Landing() {
  const { status } = useAuth();
  const { theme, toggle } = useTheme();
  const signedIn = status === "authenticated";
  const analyzeTarget = signedIn ? "/app" : "/signup";

  return (
    <div className="min-h-full bg-canvas">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        <nav className="flex items-center gap-2" aria-label="Account">
          <Button variant="ghost" size="sm" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          {signedIn ? (
            <Link to="/app">
              <Button size="sm">Open dashboard</Button>
            </Link>
          ) : (
            <>
              <Link to="/login">
                <Button size="sm" variant="ghost">
                  Sign in
                </Button>
              </Link>
              <Link to="/signup">
                <Button size="sm" variant="primary">
                  Create account
                </Button>
              </Link>
            </>
          )}
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-12 lg:grid-cols-[1fr_1.05fr] lg:pt-20">
          <div>
            <h1 className="text-[2.6rem] font-semibold leading-[1.08] tracking-[-0.025em] text-ink sm:text-[3.25rem]">
              Understand any codebase.
              <span className="block text-muted">Find where to contribute.</span>
            </h1>
            <p className="mt-6 max-w-[34rem] text-base leading-relaxed text-muted">
              CodePulse AI analyzes code quality, Git history, technical debt, dependencies, risks and GitHub issues to help
              developers understand unfamiliar repositories and identify meaningful contribution opportunities.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={analyzeTarget}>
                <Button variant="primary" className="h-10 px-5">
                  Analyze a Repository
                </Button>
              </Link>
              {!signedIn && (
                <Link to="/login">
                  <Button className="h-10 px-5">Sign In</Button>
                </Link>
              )}
            </div>
            <p className="mt-5 flex items-center gap-2 text-xs text-faint">
              <GitBranch className="h-3.5 w-3.5" aria-hidden />
              Works with public GitHub repositories.
            </p>
          </div>
          <DashboardPreview />
        </section>

        <section className="border-y border-line bg-surface" aria-labelledby="features-heading">
          <div className="mx-auto max-w-6xl px-5 py-16">
            <h2 id="features-heading" className="max-w-xl text-2xl font-semibold tracking-tight">
              What CodePulse analyzes
            </h2>
            <p className="mt-2 max-w-xl text-muted">
              Every view is backed by the same analysis engine, and each score shows the evidence behind it.
            </p>
            <div className="mt-10 grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature) => (
                <div key={feature.title}>
                  <feature.icon className="h-5 w-5 text-accent" aria-hidden />
                  <h3 className="mt-3 font-semibold">{feature.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted">{feature.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-16" aria-labelledby="how-heading">
          <h2 id="how-heading" className="text-2xl font-semibold tracking-tight">
            From URL to first contribution
          </h2>
          <ol className="mt-8 grid gap-6 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title} className="border-t-2 border-line pt-4">
                <span className="tabular text-sm text-faint">Step {index + 1}</span>
                <h3 className="mt-1 font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm text-muted">{step.body}</p>
              </li>
            ))}
          </ol>
          <div className="mt-12">
            <Link to={analyzeTarget}>
              <Button variant="primary" className="h-10 px-5">
                Analyze a Repository
              </Button>
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-xs text-faint">
          <Logo withText={false} />
          <p>
            Risk scores are historical signals from repository history, not guarantees about future defects.
          </p>
        </div>
      </footer>
    </div>
  );
}
