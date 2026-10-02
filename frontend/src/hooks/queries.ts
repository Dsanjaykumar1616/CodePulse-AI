import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../services/api";
import type { Job } from "../types/api";

const STALE = 5 * 60 * 1000;

export const keys = {
  repositories: ["repositories"] as const,
  repository: (id: string) => ["repository", id] as const,
  job: (id: string) => ["job", id] as const,
  section: (id: string, section: string) => ["section", id, section] as const,
};

export function useRepositories() {
  return useQuery({
    queryKey: keys.repositories,
    queryFn: api.repositories,
    // Keep the list fresh while any analysis is in flight.
    refetchInterval: (query) =>
      query.state.data?.some((repo) => repo.status === "queued" || repo.status === "running") ? 4000 : false,
  });
}

export function useRepository(id: string | undefined) {
  return useQuery({
    queryKey: keys.repository(id ?? ""),
    queryFn: () => api.repository(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 4000 : false;
    },
  });
}

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: keys.job(jobId ?? ""),
    queryFn: () => api.job(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 1500;
    },
  });
}

/** Result sections are keyed by repository; a new analysis invalidates them. */
function useSection<T>(id: string | undefined, section: string, fetcher: (id: string) => Promise<T>) {
  return useQuery({
    queryKey: keys.section(id ?? "", section),
    queryFn: () => fetcher(id!),
    enabled: Boolean(id),
    staleTime: STALE,
    retry: (count, error) => (error as { status?: number }).status !== 404 && count < 2,
  });
}

export const useOverview = (id?: string) => useSection(id, "overview", api.overview);
export const useHealth = (id?: string) => useSection(id, "health", api.health);
export const useRisk = (id?: string) => useSection(id, "risk", api.risk);
export const useDebt = (id?: string) => useSection(id, "debt", api.debt);
export const useDuplicates = (id?: string) => useSection(id, "duplicates", api.duplicates);
export const useReview = (id?: string) => useSection(id, "review", api.review);
export const useIssues = (id?: string) => useSection(id, "issues", api.issues);
export const useOpportunities = (id?: string) => useSection(id, "opportunities", api.opportunities);
export const useFileList = (id?: string) => useSection(id, "files", api.files);
export const useGuide = (id?: string) => useSection(id, "guide", api.guide);

export function useIssueFiles(id: string | undefined, issue: number | null) {
  return useQuery({
    queryKey: ["section", id, "issue-files", issue],
    queryFn: () => api.issueFiles(id!, issue!),
    enabled: Boolean(id && issue !== null),
    staleTime: STALE,
  });
}

export function useIssueWork(id: string | undefined, issue: number | null) {
  return useQuery({
    queryKey: ["section", id, "issue-work", issue],
    queryFn: () => api.issueWork(id!, issue!),
    enabled: Boolean(id && issue !== null && Number.isFinite(issue)),
    staleTime: STALE,
    retry: (count, error) => (error as { status?: number }).status !== 404 && count < 2,
  });
}

export function useFileIntelligence(id: string | undefined, path: string | null) {
  return useQuery({
    queryKey: ["file", id, path],
    queryFn: () => api.fileIntelligence(id!, path!),
    enabled: Boolean(id && path),
    staleTime: STALE,
    retry: (count, error) => (error as { status?: number }).status !== 404 && count < 2,
  });
}

export function useArchitecture(
  id: string | undefined,
  params: { limit: number; directory: string | null; focus: string | null; depth: number },
) {
  return useQuery({
    queryKey: ["architecture", id, params],
    queryFn: () => api.architecture(id!, params),
    enabled: Boolean(id),
    staleTime: STALE,
    placeholderData: (previous) => previous,
  });
}

export function useAddRepository() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => api.addRepository(url),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.repositories }),
  });
}

export function useAnalyze() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.analyze(id),
    onSuccess: (job: Job) => {
      client.invalidateQueries({ queryKey: keys.repositories });
      client.invalidateQueries({ queryKey: keys.repository(job.repository_id) });
    },
  });
}

export function useDeleteRepository() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteRepository(id),
    onSuccess: (_, id) => {
      client.invalidateQueries({ queryKey: keys.repositories });
      client.removeQueries({ queryKey: keys.repository(id) });
      client.removeQueries({ queryKey: ["section", id] });
    },
  });
}

/** Drop cached results for a repository once a new analysis completes. */
export function useInvalidateResults() {
  const client = useQueryClient();
  return (id: string) => {
    client.invalidateQueries({ queryKey: ["section", id] });
    client.invalidateQueries({ queryKey: ["architecture", id] });
    client.invalidateQueries({ queryKey: ["file", id] });
    client.invalidateQueries({ queryKey: keys.repository(id) });
    client.invalidateQueries({ queryKey: keys.repositories });
  };
}

// ---------------------------------------------------------------------------
// Client-side table state: search, sort and pagination over a loaded section.
// ---------------------------------------------------------------------------

export type SortDir = "asc" | "desc";

export function useTable<T>(
  rows: T[],
  options: {
    search?: (row: T, query: string) => boolean;
    initialSort?: { key: keyof T & string; dir: SortDir };
    pageSize?: number;
    filter?: (row: T) => boolean;
  } = {},
) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState(options.initialSort ?? null);
  const [page, setPage] = useState(0);
  const pageSize = options.pageSize ?? 25;
  const { search, filter } = options;

  const filtered = useMemo(() => {
    const text = query.trim().toLowerCase();
    let result = filter ? rows.filter(filter) : rows;
    if (text && search) result = result.filter((row) => search(row, text));
    if (sort) {
      const { key, dir } = sort;
      result = [...result].sort((a, b) => {
        const av = a[key] as unknown;
        const bv = b[key] as unknown;
        // Missing values always sort last.
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        const cmp =
          typeof av === "number" && typeof bv === "number"
            ? av - bv
            : String(av).localeCompare(String(bv), undefined, { numeric: true });
        return dir === "asc" ? cmp : -cmp;
      });
    }
    return result;
  }, [rows, query, sort, search, filter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  return {
    query,
    setQuery: (value: string) => {
      setQuery(value);
      setPage(0);
    },
    sort,
    toggleSort: (key: keyof T & string) => {
      setPage(0);
      setSort((current) =>
        current?.key === key ? { key, dir: current.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" },
      );
    },
    page: safePage,
    setPage,
    pageCount,
    pageSize,
    total: filtered.length,
    rows: pageRows,
    resetPage: () => setPage(0),
  };
}
