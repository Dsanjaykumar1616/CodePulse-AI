import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, FileSearch, ListChecks, Lightbulb } from "lucide-react";
import { Button, Explainer, LevelBadge } from "./ui";
import { FilePath, useOpenFile } from "./FilePath";
import type { DirectoryGroup, Guide } from "../types/api";

/** GitHub web URL for a file on the default branch. */
export function githubFileUrl(repoUrl: string | null | undefined, path: string) {
  if (!repoUrl) return null;
  return `${repoUrl.replace(/\/$/, "")}/blob/HEAD/${path.split("/").map(encodeURIComponent).join("/")}`;
}

function describeLanguages(languages: Record<string, number>): string {
  const entries = Object.entries(languages).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return "source files";
  const names = entries.slice(0, 3).map(([name]) => name);
  if (names.length === 1) return `${names[0]} files`;
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]} files`;
}

function groupName(group: DirectoryGroup) {
  return group.id === "(root)" ? "the top-level folder" : `${group.label}/`;
}

/**
 * The architecture explained in short sentences, built only from the
 * analysis (folder names, file counts, languages and import counts).
 */
export function ArchitectureInWords({ guide }: { guide: Guide }) {
  const groups = guide.groups.groups;
  const sentences: { key: string; text: ReactNode }[] = [];
  const main = [...groups].sort((a, b) => b.file_count - a.file_count).slice(0, 4);

  if (groups.length === 0) return null;

  sentences.push({
    key: "parts",
    text: (
      <>
        This project's analyzed code is split into <b>{groups.length}</b> {groups.length === 1 ? "folder" : "folders"}. The
        biggest {main.length === 1 ? "is" : "are"}:
        <ul className="mt-1.5 space-y-1">
          {main.map((group) => (
            <li key={group.id} className="flex flex-wrap items-baseline gap-x-1.5">
              <span className="font-mono text-[13px] text-ink">{groupName(group)}</span>
              <span className="text-muted">
                {group.file_count} {group.file_count === 1 ? "file" : "files"}, mostly {describeLanguages(group.languages)}
                {group.name_hint ? ` (the name suggests: ${group.name_hint.toLowerCase()})` : ""}
              </span>
            </li>
          ))}
        </ul>
      </>
    ),
  });

  const edges = guide.groups.edges.slice(0, 3);
  sentences.push({
    key: "connections",
    text: edges.length ? (
      <>
        How the parts connect:
        <ul className="mt-1.5 space-y-1">
          {edges.map((edge) => {
            const source = groups.find((group) => group.id === edge.source);
            const target = groups.find((group) => group.id === edge.target);
            return (
              <li key={`${edge.source}-${edge.target}`} className="text-muted">
                Code in <span className="font-mono text-[13px] text-ink">{source ? groupName(source) : edge.source}</span> uses
                code from <span className="font-mono text-[13px] text-ink">{target ? groupName(target) : edge.target}</span> ({edge.count}{" "}
                {edge.count === 1 ? "import" : "imports"})
              </li>
            );
          })}
        </ul>
      </>
    ) : (
      <>
        These folders don't import code from each other, so each part mostly works on its own. That usually means you can
        change one part without breaking another.
      </>
    ),
  });

  const core = guide.start_here.find((item) => item.label === "Core dependency" || item.label === "Highly connected module");
  const entry = guide.start_here.find((item) => item.label === "Possible entry point");
  if (core) {
    sentences.push({
      key: "core",
      text: (
        <>
          The most important file is probably <FilePath path={core.file} className="inline font-medium" truncate={false} />.{" "}
          <span className="text-muted">{core.reason}</span>
        </>
      ),
    });
  }
  if (entry) {
    sentences.push({
      key: "entry",
      text: (
        <>
          A good file to read first is <FilePath path={entry.file} className="inline font-medium" truncate={false} />.{" "}
          <span className="text-muted">{entry.reason}</span>
        </>
      ),
    });
  }
  if (guide.unresolved_dependencies) {
    sentences.push({
      key: "unresolved",
      text: (
        <span className="text-muted">
          {guide.unresolved_dependencies} imports point outside this repository (usually libraries such as frameworks or
          packages). They are not part of the map.
        </span>
      ),
    });
  }

  return (
    <section className="panel p-5" aria-labelledby="in-words-heading">
      <h2 id="in-words-heading" className="flex items-center gap-2 text-base font-semibold">
        <Lightbulb className="h-4 w-4 text-accent" aria-hidden /> The architecture in simple words
      </h2>
      <ol className="mt-3 space-y-3 text-sm">
        {sentences.map((sentence, index) => (
          <li key={sentence.key} className="flex gap-3">
            <span className="tabular mt-px w-4 shrink-0 text-right text-faint">{index + 1}</span>
            <div className="min-w-0">{sentence.text}</div>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-faint">
        Written from folder names, file counts and imports found by static analysis. CodePulse does not read what the code
        does.
      </p>
    </section>
  );
}

/** One concrete file to start with, and exactly what to do next. */
export function FirstContribution({
  repoId,
  repoUrl,
  file,
  difficulty,
  reason,
  title = "Your first contribution",
}: {
  repoId: string;
  repoUrl: string | null | undefined;
  file: string;
  difficulty: string;
  reason: string;
  title?: string;
}) {
  const { open } = useOpenFile();
  const github = githubFileUrl(repoUrl, file);
  return (
    <section className="rounded-md border-2 border-accent/40 bg-surface p-5" aria-labelledby="first-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="first-heading" className="text-base font-semibold">
            {title}
          </h2>
          <p className="mt-0.5 text-sm text-muted">If you are new to this repository, CodePulse suggests starting with this file:</p>
        </div>
        <LevelBadge level={difficulty} />
      </div>
      <div className="mt-3 rounded border border-line bg-canvas px-3 py-2.5">
        <FilePath path={file} className="!text-[14px] font-medium" />
        <p className="mt-1 text-sm text-muted">{reason}</p>
      </div>
      <h3 className="mt-4 flex items-center gap-2 text-sm font-medium">
        <ListChecks className="h-4 w-4 text-accent" aria-hidden /> What to do
      </h3>
      <ol className="mt-2 space-y-2 text-sm">
        <li className="flex gap-3">
          <span className="tabular w-4 shrink-0 text-right text-faint">1</span>
          <span>
            Open the file and read it.{" "}
            {github && (
              <a href={github} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
                Open on GitHub <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
          </span>
        </li>
        <li className="flex gap-3">
          <span className="tabular w-4 shrink-0 text-right text-faint">2</span>
          <span>
            Check what CodePulse found about it: what it depends on, what uses it, and any issues.{" "}
            <button type="button" onClick={() => open(file, "before")} className="text-accent hover:underline">
              See the file details
            </button>
          </span>
        </li>
        <li className="flex gap-3">
          <span className="tabular w-4 shrink-0 text-right text-faint">3</span>
          <span>
            Follow the step-by-step plan.{" "}
            <Link to={`/app/r/${repoId}/file?path=${encodeURIComponent(file)}&tab=plan`} className="text-accent hover:underline">
              Open the contribution plan
            </Link>
          </span>
        </li>
        <li className="flex gap-3">
          <span className="tabular w-4 shrink-0 text-right text-faint">4</span>
          <span>Make one small change, run the project's tests, and open a pull request on GitHub.</span>
        </li>
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="primary" icon={<FileSearch className="h-3.5 w-3.5" />} onClick={() => open(file, "before")}>
          Start with this file
        </Button>
        <Link to={`/app/r/${repoId}/opportunities`}>
          <Button size="sm">See other options</Button>
        </Link>
      </div>
      <p className="mt-3 text-xs text-faint">
        This is a suggestion based on the analysis, not a guarantee the change is easy or wanted. Check the project's
        contributing guide and open issues first.
      </p>
    </section>
  );
}

/** Plain-language meanings of the words used across CodePulse. */
export function Glossary() {
  return (
    <Explainer title="New to this? What the words mean">
      <dl className="space-y-2">
        {[
          ["Contribution opportunity", "A file where a change could help the project, such as clearer code, comments or tests."],
          ["Difficulty (Beginner / Intermediate / Advanced)", "CodePulse's estimate of how hard a change in that file is likely to be. Beginner files are smaller and simpler."],
          ["Risk", "How much the file's past looks like files that needed bug fixes. High risk means: be careful and test well."],
          ["Technical debt", "How hard the file is to work with today, for example long or complicated code. Higher means more room to improve."],
          ["Connections / used by", "How many other files use this file. If many files use it, a change here can affect a lot of the project."],
          ["Architecture", "How the project's folders and files are organised and which files use which."],
        ].map(([term, meaning]) => (
          <div key={term}>
            <dt className="font-medium text-ink">{term}</dt>
            <dd>{meaning}</dd>
          </div>
        ))}
      </dl>
    </Explainer>
  );
}
