import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
}

/** Keeps one broken view from taking down the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode; inline?: boolean }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("CodePulse view error", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className={this.props.inline ? "panel p-6" : "flex min-h-full items-center justify-center p-6"}>
        <div className="max-w-md text-center">
          <h2 className="text-base font-semibold">This view could not be displayed</h2>
          <p className="mt-1 text-sm text-muted">
            Something in this part of the page failed to render. The rest of CodePulse still works.
          </p>
          <pre className="mt-3 overflow-x-auto rounded bg-raised p-2 text-left font-mono text-xs text-muted">
            {this.state.error.message}
          </pre>
          <button
            className="mt-4 h-9 rounded border border-line bg-surface px-3.5 text-sm font-medium hover:bg-raised"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }
}
