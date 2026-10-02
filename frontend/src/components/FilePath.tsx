import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { cx } from "./ui";
import { splitPath } from "../lib/format";

/**
 * A repository-relative path: dimmed directory, bright file name.
 * Used everywhere a file appears so paths scan like a code tree.
 */
export function FilePath({ path, className, truncate = true }: { path: string; className?: string; truncate?: boolean }) {
  const { dir, base } = splitPath(path);
  return (
    <span
      className={cx("font-mono text-[12.5px]", truncate && "block min-w-0 truncate", className)}
      title={path}
      dir="ltr"
    >
      {dir && <span className="text-faint">{dir}</span>}
      <span className="text-ink">{base}</span>
    </span>
  );
}

/** Opens the file intelligence drawer for a path (via the ?file= URL parameter). */
export function useOpenFile() {
  const [params, setParams] = useSearchParams();
  const open = useCallback(
    (path: string, tab?: string) => {
      const next = new URLSearchParams(params);
      next.set("file", path);
      if (tab) next.set("tab", tab);
      else next.delete("tab");
      setParams(next);
    },
    [params, setParams],
  );
  const close = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete("file");
    next.delete("tab");
    setParams(next);
  }, [params, setParams]);
  return { file: params.get("file"), tab: params.get("tab"), open, close };
}

/** A file path that opens its intelligence drawer. */
export function FileLink({ path, className }: { path: string; className?: string }) {
  const { open } = useOpenFile();
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        open(path);
      }}
      className={cx("block min-w-0 max-w-full text-left hover:underline decoration-faint underline-offset-2", className)}
    >
      <FilePath path={path} />
    </button>
  );
}
