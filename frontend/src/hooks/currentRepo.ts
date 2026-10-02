import { useEffect } from "react";
import { matchPath, useLocation } from "react-router-dom";

const KEY = "codepulse.currentRepo";

export function getCurrentRepoId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setCurrentRepoId(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** The repository in the URL, falling back to the last one the user opened. */
export function useCurrentRepoId(): string | null {
  // Layouts above the repository route cannot see its params, so match the URL.
  const { pathname } = useLocation();
  const repoId: string | undefined = matchPath("/app/r/:repoId/*", pathname)?.params?.repoId;
  useEffect(() => {
    if (repoId) setCurrentRepoId(repoId);
  }, [repoId]);
  return repoId ?? getCurrentRepoId();
}

/** Contributor views first; supporting analysis after. */
export const repoSections = [
  { path: "", label: "Start here", group: "contribute" },
  { path: "opportunities", label: "Contribute", group: "contribute" },
  { path: "architecture", label: "Architecture", group: "contribute" },
  { path: "explore", label: "Explorer", group: "contribute" },
  { path: "issues", label: "Issues", group: "contribute" },
  { path: "metrics", label: "Metrics", group: "analysis" },
  { path: "health", label: "Health", group: "analysis" },
  { path: "risk", label: "Risky files", group: "analysis" },
  { path: "debt", label: "Technical debt", group: "analysis" },
  { path: "duplicates", label: "Duplicates", group: "analysis" },
  { path: "review", label: "Code review", group: "analysis" },
] as const;
