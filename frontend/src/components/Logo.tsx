import { cx } from "./ui";

/** The CodePulse mark: a pulse trace inside a rounded square. */
export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <svg viewBox="0 0 32 32" className="h-6 w-6 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="7" className="fill-ink" />
        <path
          d="M5 17h6l3-8 4 15 3-9h6"
          fill="none"
          stroke="rgb(var(--accent))"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {withText && (
        <span className="text-[15px] font-semibold tracking-tight text-ink">
          CodePulse <span className="font-normal text-muted">AI</span>
        </span>
      )}
    </span>
  );
}
