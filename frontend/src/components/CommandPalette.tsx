import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CornerDownLeft, FileCode2, LayoutGrid, Search } from "lucide-react";
import { useFileList, useRepositories } from "../hooks/queries";
import { repoSections, useCurrentRepoId } from "../hooks/currentRepo";
import { FilePath } from "./FilePath";
import { cx, Kbd } from "./ui";

interface Item {
  id: string;
  kind: "page" | "file" | "repo";
  label: string;
  hint?: string;
  run: () => void;
}

const MAX_FILES = 40;

/** Quick navigation: repository pages and files of the current repository. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const repoId = useCurrentRepoId();
  const repositories = useRepositories();
  const current = repositories.data?.find((repo) => repo.id === repoId);
  const files = useFileList(open && current?.has_results ? current.id : undefined);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const items = useMemo<Item[]>(() => {
    const text = query.trim().toLowerCase();
    const result: Item[] = [];
    const go = (path: string) => () => {
      navigate(path);
      onClose();
    };

    if (current) {
      for (const section of repoSections) {
        if (!text || section.label.toLowerCase().includes(text)) {
          result.push({
            id: `page:${section.path}`,
            kind: "page",
            label: section.label,
            hint: current.full_name,
            run: go(`/app/r/${current.id}${section.path ? `/${section.path}` : ""}`),
          });
        }
      }
    }
    for (const repo of repositories.data ?? []) {
      if (repo.id !== current?.id && (!text || repo.full_name.toLowerCase().includes(text))) {
        result.push({ id: `repo:${repo.id}`, kind: "repo", label: repo.full_name, hint: "Open repository", run: go(`/app/r/${repo.id}`) });
      }
    }
    if (current && text) {
      const matches = (files.data?.files ?? []).filter((file) => file.file.toLowerCase().includes(text)).slice(0, MAX_FILES);
      for (const file of matches) {
        result.push({
          id: `file:${file.file}`,
          kind: "file",
          label: file.file,
          run: go(`/app/r/${current.id}/file?path=${encodeURIComponent(file.file)}`),
        });
      }
    }
    return result;
  }, [query, current, repositories.data, files.data, navigate, onClose]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]">
      <div className="absolute inset-0 bg-canvas/70 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div role="dialog" aria-modal="true" aria-label="Search" className="panel relative w-full max-w-xl overflow-hidden">
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 text-faint" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClose();
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActive((index) => Math.min(items.length - 1, index + 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((index) => Math.max(0, index - 1));
              }
              if (event.key === "Enter") items[active]?.run();
            }}
            placeholder={current ? `Search pages and files in ${current.full_name}` : "Search repositories"}
            aria-label="Search query"
            aria-controls="palette-results"
            aria-activedescendant={items[active] ? `palette-${active}` : undefined}
            className="h-12 w-full bg-transparent text-sm text-ink placeholder:text-faint focus:outline-none"
          />
          <Kbd>Esc</Kbd>
        </div>
        <ul ref={listRef} id="palette-results" role="listbox" className="scroll-thin max-h-[50vh] overflow-y-auto p-1.5">
          {items.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted">
              {current ? "No pages or files match." : "Add a repository to search its files."}
            </li>
          )}
          {items.map((item, index) => (
            <li
              key={item.id}
              id={`palette-${index}`}
              data-index={index}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onClick={item.run}
              className={cx(
                "flex cursor-pointer items-center gap-2.5 rounded px-2.5 py-2 text-sm",
                index === active ? "bg-raised" : "",
              )}
            >
              {item.kind === "file" ? (
                <FileCode2 className="h-4 w-4 shrink-0 text-faint" aria-hidden />
              ) : (
                <LayoutGrid className="h-4 w-4 shrink-0 text-faint" aria-hidden />
              )}
              {item.kind === "file" ? (
                <FilePath path={item.label} />
              ) : (
                <span className="truncate text-ink">{item.label}</span>
              )}
              {item.hint && <span className="ml-auto shrink-0 truncate text-xs text-faint">{item.hint}</span>}
              {index === active && <CornerDownLeft className="ml-auto h-3.5 w-3.5 shrink-0 text-faint" aria-hidden />}
            </li>
          ))}
        </ul>
        {current && !query && (
          <p className="border-t border-line px-3 py-2 text-xs text-faint">Type part of a file path to jump to its intelligence.</p>
        )}
      </div>
    </div>
  );
}
