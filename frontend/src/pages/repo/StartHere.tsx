import { Link, useParams } from "react-router-dom";
import { ArrowRight, Compass, FolderOpen, Info } from "lucide-react";
import { Badge, Button, EmptyState, InfoTip, LevelBadge, PageLoading, Panel } from "../../components/ui";
import { FileLink } from "../../components/FilePath";
import { HelpActions } from "../../components/HelpActions";
import { LanguageBar } from "./Overview";
import { useGuide, useRepository } from "../../hooks/queries";
import { ArchitectureInWords, FirstContribution, Glossary } from "../../components/Guidance";
import { fmtNumber, fmtPercent } from "../../lib/format";
import type { DirectoryGroup, Guide, RoadmapItem } from "../../types/api";

function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1 text-xs text-muted">
        {label}
        {hint && <InfoTip label={label}>{hint}</InfoTip>}
      </dt>
      <dd className="tabular mt-0.5 truncate text-lg font-semibold">{value}</dd>
    </div>
  );
}

function GroupCard({ group, repoId }: { group: DirectoryGroup; repoId: string }) {
  return (
    <li className="panel flex flex-col p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-mono text-[13px] font-medium text-ink">{group.label}/</h3>
        <span className="tabular text-xs text-muted">
          {group.file_count} {group.file_count === 1 ? "file" : "files"} · {fmtNumber(group.loc)} lines
        </span>
      </div>
      <p className="mt-1 text-sm text-muted">
        {group.name_hint ? (
          <>
            <span className="text-ink">{group.name_hint}</span>{" "}
            <span className="text-xs text-faint">(suggested by the directory name)</span>
          </>
        ) : (
          <span className="text-faint">Directory</span>
        )}
      </p>
      <p className="mt-0.5 text-xs text-muted">{group.structure}</p>

      {group.key_files.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs text-faint">Most connected files</p>
          <ul className="space-y-1">
            {group.key_files.slice(0, 3).map((file) => (
              <li key={file.file} className="flex items-center gap-2">
                <FileLink path={file.file} className="min-w-0 flex-1" />
                {file.roles[0] && <Badge>{file.roles[0]}</Badge>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-3 text-xs text-muted">
        {group.opportunities > 0 && <span>{group.opportunities} opportunities</span>}
        {group.high_risk_files > 0 && <span className="text-high">{group.high_risk_files} high-risk files</span>}
        {group.test_files > 0 && <span>{group.test_files} test files</span>}
        <Link
          to={`/app/r/${repoId}/architecture?mode=components&group=${encodeURIComponent(group.id)}`}
          className="ml-auto text-accent hover:underline"
        >
          View in architecture
        </Link>
      </div>
    </li>
  );
}

function Roadmap({ guide, repoId }: { guide: Guide; repoId: string }) {
  const levels = [
    { key: "BEGINNER", label: "Beginner", hint: "Smaller files with simpler logic" },
    { key: "INTERMEDIATE", label: "Intermediate", hint: "Moderate complexity, churn or size" },
    { key: "ADVANCED", label: "Advanced", hint: "Complex, central or high-impact files" },
  ] as const;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {levels.map((level, index) => {
        const items: RoadmapItem[] = guide.roadmap[level.key];
        const total = guide.roadmap[`${level.key}_total`];
        return (
          <div key={level.key} className="panel flex flex-col p-4">
            <div className="flex items-center justify-between gap-2">
              <LevelBadge level={level.key} />
              <span className="tabular text-xs text-muted">{total} total</span>
            </div>
            <p className="mt-1.5 text-xs text-muted">
              {index > 0 && <span className="text-faint">Then · </span>}
              {level.hint}
            </p>
            {items.length === 0 ? (
              <p className="mt-3 text-sm text-faint">No {level.label.toLowerCase()} opportunities were estimated.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {items.map((item) => (
                  <li key={item.file}>
                    <FileLink path={item.file} />
                    <p className="truncate text-xs text-muted">
                      {item.title}
                      {item.open_issue_count > 0 && <span className="text-low"> · open issue</span>}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <Link to={`/app/r/${repoId}/opportunities?difficulty=${level.key}`} className="mt-auto pt-3 text-xs text-accent hover:underline">
              All {level.label.toLowerCase()} opportunities
            </Link>
          </div>
        );
      })}
    </div>
  );
}

export default function StartHere() {
  const { repoId } = useParams<"repoId">();
  const guide = useGuide(repoId);
  const repository = useRepository(repoId);

  if (guide.isLoading) return <PageLoading />;
  if (guide.isError || !guide.data) return <EmptyState title="Onboarding not available">{guide.error?.message}</EmptyState>;
  const data = guide.data;
  const facts = data.facts;
  const first = data.roadmap.BEGINNER[0]
    ? { item: data.roadmap.BEGINNER[0], level: "BEGINNER" }
    : data.roadmap.INTERMEDIATE[0]
      ? { item: data.roadmap.INTERMEDIATE[0], level: "INTERMEDIATE" }
      : data.roadmap.ADVANCED[0]
        ? { item: data.roadmap.ADVANCED[0], level: "ADVANCED" }
        : null;

  return (
    <div className="space-y-8">
      {first && (
        <FirstContribution
          repoId={repoId!}
          repoUrl={repository.data?.url ?? data.repository.url}
          file={first.item.file}
          difficulty={first.level}
          reason={
            (first.level === "BEGINNER"
              ? "It is the top-ranked Beginner opportunity: a smaller file with simpler logic. "
              : `No Beginner opportunities were found, so this is the top ${first.level.toLowerCase()} one. `) +
            (first.item.title ? `Suggested change: ${first.item.title}.` : "")
          }
        />
      )}

      <ArchitectureInWords guide={data} />

      <Glossary />

      <section aria-labelledby="glance-heading" className="space-y-4">
        <div>
          <h2 id="glance-heading" className="text-base font-semibold">
            Repository at a glance
          </h2>
          <p className="mt-0.5 text-sm text-muted">
            What CodePulse found in {data.repository.full_name}, from static analysis and Git history.
          </p>
        </div>
        <div className="panel p-5">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Fact label="Source files" value={fmtNumber(facts.files)} hint="Files in the languages CodePulse analyzes (Python, JavaScript, TypeScript, React, HTML, CSS, Java)." />
            <Fact label="Lines of code" value={fmtNumber(facts.lines_of_code)} hint="Repository size: lines of code across the analyzed source files." />
            <Fact label="Contributors" value={fmtNumber(facts.contributors)} hint="Distinct commit author emails in the Git history." />
            <Fact label="Commits" value={fmtNumber(facts.commits)} />
            <Fact label="Test files" value={fmtNumber(facts.test_files)} hint="Files in test directories or named like tests (test_*.py, *.test.ts, *Test.java…)." />
            <Fact
              label="Open issues"
              value={facts.issues_available ? fmtNumber(facts.open_issues) : "Unavailable"}
              hint="Open GitHub issues returned by the GitHub API (up to the 100 most recently updated)."
            />
          </dl>
          <div className="mt-5 border-t border-line pt-4">
            <LanguageBar languages={facts.languages} />
          </div>
        </div>
      </section>

      <section aria-labelledby="help-heading" className="space-y-3">
        <h2 id="help-heading" className="text-base font-semibold">
          How can CodePulse help you?
        </h2>
        <HelpActions
          repoId={repoId!}
          counts={{
            BEGINNER: data.roadmap.BEGINNER_total,
            INTERMEDIATE: data.roadmap.INTERMEDIATE_total,
            ADVANCED: data.roadmap.ADVANCED_total,
            openIssues: facts.open_issues,
            issuesAvailable: facts.issues_available,
          }}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
        <Panel
          title={
            <span className="flex items-center gap-2">
              <Compass className="h-4 w-4 text-accent" aria-hidden /> Start here
            </span>
          }
          description="Recommended starting points based on the dependency structure. Roles are estimates."
        >
          {!data.architecture_available ? (
            <p className="text-sm text-muted">{data.architecture_reason ?? "Dependency analysis was not available, so starting points could not be estimated."}</p>
          ) : data.start_here.length === 0 ? (
            <p className="text-sm text-muted">No file stood out structurally. Browse the major parts below or the Explorer.</p>
          ) : (
            <ol className="space-y-3">
              {data.start_here.map((item, index) => (
                <li key={item.file} className="flex gap-3">
                  <span className="tabular mt-0.5 w-4 shrink-0 text-right text-sm text-faint">{index + 1}</span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <FileLink path={item.file} />
                      <Badge>{item.label}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-muted">{item.reason}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel title="Where to be careful" description="Files with a high historical risk signal and the most frequently changed files">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <h3 className="mb-1.5 text-xs text-muted">High-risk areas</h3>
              {data.high_risk_areas.length === 0 ? (
                <p className="text-sm text-faint">No files reached the high or critical historical risk levels, or the risk model did not run.</p>
              ) : (
                <ul className="space-y-1.5">
                  {data.high_risk_areas.map((item) => (
                    <li key={item.file} className="flex items-center gap-2">
                      <FileLink path={item.file} className="min-w-0 flex-1" />
                      <span className="tabular text-xs text-muted">{fmtPercent(item.risk_probability)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="mb-1.5 text-xs text-muted">Most frequently changed</h3>
              {facts.most_changed_files.length === 0 ? (
                <p className="text-sm text-faint">No commit activity was recorded for the analyzed files.</p>
              ) : (
                <ul className="space-y-1.5">
                  {facts.most_changed_files.map((item) => (
                    <li key={item.file} className="flex items-center gap-2">
                      <FileLink path={item.file} className="min-w-0 flex-1" />
                      <span className="tabular text-xs text-muted">{item.commits} commits</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Panel>
      </div>

      <section aria-labelledby="parts-heading" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="parts-heading" className="flex items-center gap-2 text-base font-semibold">
              <FolderOpen className="h-4 w-4 text-accent" aria-hidden /> Major parts of the project
            </h2>
            <p className="mt-0.5 text-sm text-muted">{data.groups.basis}</p>
          </div>
          <Link to={`/app/r/${repoId}/architecture`}>
            <Button size="sm">
              Open architecture map <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Button>
          </Link>
        </div>
        {data.groups.groups.length === 0 ? (
          <EmptyState title="No directories to show">No analyzed source files were found.</EmptyState>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.groups.groups.slice(0, 12).map((group) => (
              <GroupCard key={group.id} group={group} repoId={repoId!} />
            ))}
          </ul>
        )}
        {data.groups.groups.length > 12 && (
          <p className="text-xs text-muted">
            Showing 12 of {data.groups.groups.length} directories.{" "}
            <Link to={`/app/r/${repoId}/explore`} className="text-accent hover:underline">
              Browse all in the Explorer
            </Link>
          </p>
        )}
      </section>

      <section aria-labelledby="roadmap-heading" className="space-y-3">
        <div>
          <h2 id="roadmap-heading" className="text-base font-semibold">
            Contributor roadmap
          </h2>
          <p className="mt-0.5 text-sm text-muted">
            The top opportunities at each estimated difficulty. This is guidance, not a required order.
          </p>
        </div>
        <Roadmap guide={data} repoId={repoId!} />
      </section>

      <ul className="space-y-1 text-xs text-faint">
        {data.notes.map((note) => (
          <li key={note} className="flex gap-1.5">
            <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
            {note}
          </li>
        ))}
      </ul>
    </div>
  );
}
