import { Link } from "react-router-dom";
import { Button, EmptyState } from "../components/ui";
import { Logo } from "../components/Logo";

export default function NotFound({ standalone }: { standalone?: boolean }) {
  const content = (
    <EmptyState
      title="Page not found"
      action={
        <Link to={standalone ? "/" : "/app"}>
          <Button>{standalone ? "Go to the home page" : "Back to overview"}</Button>
        </Link>
      }
    >
      The address may be mistyped, or the page has moved.
    </EmptyState>
  );
  if (!standalone) return content;
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-6 p-6">
      <Logo />
      {content}
    </div>
  );
}
