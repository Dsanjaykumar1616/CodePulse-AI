import type {
  Architecture,
  Debt,
  EnrichedOpportunities,
  Guide,
  IssueFiles,
  IssueWork,
  Duplicates,
  FileIntelligence,
  FileList,
  Health,
  Issues,
  Job,
  Overview,
  Repository,
  RepositoryCreated,
  Review,
  Risk,
  TokenResponse,
  User,
} from "../types/api";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "codepulse.token";

// "Keep me signed in" stores the token in localStorage; otherwise it lives in
// sessionStorage and ends with the browser session.
export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string, remember: boolean) {
    try {
      this.clear();
      (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
    } catch {
      /* storage unavailable: the session will not persist */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();
export function onUnauthorized(listener: Listener) {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

function describeError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {};
    for (const item of detail as ValidationIssue[]) {
      const field = String(item.loc?.[item.loc.length - 1] ?? "form");
      fields[field] = (item.msg ?? "Invalid value").replace(/^Value error, /, "");
    }
    const first = Object.values(fields)[0];
    return new ApiError(status, first ?? "Some fields are invalid.", fields);
  }
  if (status >= 500) return new ApiError(status, "The server ran into a problem. Try again in a moment.");
  return new ApiError(status, `Request failed (${status}).`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${BASE}/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Cannot reach the CodePulse server. Check that the backend is running.");
  }

  if (response.status === 401 && token) {
    tokenStore.clear();
    unauthorizedListeners.forEach((listener) => listener());
  }
  if (response.status === 204) return undefined as T;

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await response.json().catch(() => null) : null;
  if (!response.ok) throw describeError(response.status, body);
  return body as T;
}

const json = (data: unknown) => JSON.stringify(data);
const q = (params: Record<string, string | number | undefined | null>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
};

export const api = {
  signup: (body: { name: string; email: string; password: string }) =>
    request<TokenResponse>("/auth/signup", { method: "POST", body: json(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: json(body) }),
  me: () => request<User>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),

  repositories: () => request<Repository[]>("/repositories"),
  repository: (id: string) => request<Repository>(`/repositories/${id}`),
  addRepository: (url: string) =>
    request<RepositoryCreated>("/repositories", { method: "POST", body: json({ url, analyze: true }) }),
  deleteRepository: (id: string) => request<void>(`/repositories/${id}`, { method: "DELETE" }),
  analyze: (id: string) => request<Job>(`/repositories/${id}/analyze`, { method: "POST" }),
  job: (jobId: string) => request<Job>(`/analysis/${jobId}`),

  overview: (id: string) => request<Overview>(`/repositories/${id}/overview`),
  health: (id: string) => request<Health>(`/repositories/${id}/health`),
  risk: (id: string) => request<Risk>(`/repositories/${id}/risk`),
  debt: (id: string) => request<Debt>(`/repositories/${id}/debt`),
  duplicates: (id: string) => request<Duplicates>(`/repositories/${id}/duplicates`),
  review: (id: string) => request<Review>(`/repositories/${id}/review`),
  issues: (id: string) => request<Issues>(`/repositories/${id}/issues`),
  opportunities: (id: string) => request<EnrichedOpportunities>(`/repositories/${id}/opportunities`),
  guide: (id: string) => request<Guide>(`/repositories/${id}/guide`),
  issueFiles: (id: string, issue: number) => request<IssueFiles>(`/repositories/${id}/issues/${issue}/files`),
  issueWork: (id: string, issue: number) => request<IssueWork>(`/repositories/${id}/issues/${issue}/work`),
  files: (id: string) => request<FileList>(`/repositories/${id}/files`),
  architecture: (
    id: string,
    params: { limit?: number; directory?: string | null; focus?: string | null; depth?: number },
  ) => request<Architecture>(`/repositories/${id}/architecture${q(params)}`),
  fileIntelligence: (id: string, path: string) =>
    request<FileIntelligence>(`/repositories/${id}/files/intelligence${q({ path })}`),

  /** Downloads the HTML report through an authenticated request. */
  async downloadReport(id: string, fullName: string) {
    const token = tokenStore.get();
    let response: Response;
    try {
      response = await fetch(`${BASE}/api/repositories/${id}/report?download=true`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      throw new ApiError(0, "Cannot reach the CodePulse server.");
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw describeError(response.status, body);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `codepulse-${fullName.replace(/[^A-Za-z0-9._-]+/g, "-")}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
