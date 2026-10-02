import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { GitBranch } from "lucide-react";
import { useAddRepository } from "../hooks/queries";
import { Button, Callout, Input } from "./ui";

const NAME = "[A-Za-z0-9][A-Za-z0-9._-]{0,99}";
const PATTERNS = [
  new RegExp(`^https?://(?:www\\.)?github\\.com/${NAME}/${NAME}(?:\\.git)?/?$`),
  new RegExp(`^(?:www\\.)?github\\.com/${NAME}/${NAME}(?:\\.git)?/?$`),
  new RegExp(`^git@github\\.com:${NAME}/${NAME}(?:\\.git)?$`),
  new RegExp(`^${NAME}/${NAME}$`),
];

/** Mirrors backend/app/services/github_url.py; the backend re-validates. */
export function isGitHubUrl(value: string): boolean {
  const text = value
    .trim()
    .replace(/(github\.com\/[^/\s]+\/[^/\s]+)\/(?:tree|blob|issues|pulls|wiki)(?:\/.*)?$/, "$1");
  return PATTERNS.some((pattern) => pattern.test(text));
}

export function AnalyzeForm({ autoFocus }: { autoFocus?: boolean }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const add = useAddRepository();
  const navigate = useNavigate();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!isGitHubUrl(url)) {
      setError("Enter a GitHub repository URL such as https://github.com/psf/requests");
      return;
    }
    setError(null);
    add.mutate(url.trim(), {
      onSuccess: (result) => {
        if (result.job) navigate(`/app/analysis/${result.job.id}`);
        else navigate(`/app/r/${result.repository.id}`);
      },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-2.5">
      <label htmlFor="repo-url" className="sr-only">
        GitHub repository URL
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <GitBranch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" aria-hidden />
          <Input
            id="repo-url"
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              if (error) setError(null);
            }}
            placeholder="https://github.com/psf/requests"
            autoComplete="off"
            spellCheck={false}
            autoFocus={autoFocus}
            invalid={Boolean(error)}
            aria-describedby={error ? "repo-url-error" : undefined}
            className="h-10 pl-9 font-mono text-[13px]"
          />
        </div>
        <Button type="submit" variant="primary" loading={add.isPending} className="h-10 px-5">
          Analyze Repository
        </Button>
      </div>
      {error && (
        <div id="repo-url-error">
          <Callout tone="error">{error}</Callout>
        </div>
      )}
    </form>
  );
}
