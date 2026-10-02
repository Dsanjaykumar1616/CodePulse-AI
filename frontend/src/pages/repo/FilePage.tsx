import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { FileIntelligenceView } from "../../components/FileIntelligence";
import { Button, EmptyState } from "../../components/ui";

/** Full-page file intelligence (the drawer's content, with room to read). */
export default function FilePage() {
  const { repoId } = useParams<"repoId">();
  const [params, setParams] = useSearchParams();
  const path = params.get("path");

  if (!path || !repoId) {
    return (
      <EmptyState
        title="No file selected"
        action={
          <Link to={`/app/r/${repoId}/risk`}>
            <Button>Browse files</Button>
          </Link>
        }
      >
        Choose a file from Risky files, Technical debt or the architecture graph.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-3">
      <Link to={`/app/r/${repoId}/opportunities`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Contribution opportunities
      </Link>
      <div className="panel overflow-hidden">
        <FileIntelligenceView
          repositoryId={repoId}
          path={path}
          tab={params.get("tab")}
          onTabChange={(value) => {
            const next = new URLSearchParams(params);
            next.set("tab", value);
            setParams(next, { replace: true });
          }}
        />
      </div>
    </div>
  );
}
