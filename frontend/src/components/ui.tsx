import { clsx } from "clsx";
import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type RefObject,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { AlertTriangle, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Info, Loader2, Search, X } from "lucide-react";
import { capitalize, severityBg, severityOf, severityText, type Severity } from "../lib/format";

export const cx = clsx;

// ---------------------------------------------------------------------------
// Buttons and inputs
// ---------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent/90 border border-transparent",
  secondary: "bg-surface text-ink border border-line hover:bg-raised",
  ghost: "text-muted hover:text-ink hover:bg-raised border border-transparent",
  danger: "bg-critical text-white hover:bg-critical/90 border border-transparent",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode }
>(function Button({ variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        variants[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(
  function Input({ className, invalid, ...rest }, ref) {
    return (
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cx(
          "h-9 w-full rounded border bg-surface px-3 text-sm text-ink placeholder:text-faint",
          "focus:outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/25 focus-visible:outline-none",
          invalid ? "border-critical" : "border-line",
          className,
        )}
        {...rest}
      />
    );
  },
);

export function Field({
  label,
  error,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  error?: string;
  hint?: ReactNode;
  children: ReactNode;
  htmlFor: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-critical" role="alert">
          {error}
        </p>
      ) : hint ? (
        <div className="text-xs text-muted">{hint}</div>
      ) : null}
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
  label,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label: string;
  className?: string;
}) {
  return (
    <div className={cx("relative", className)}>
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" aria-hidden />
      <Input
        type="search"
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="pl-8"
      />
    </div>
  );
}

export function Select({
  label,
  className,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <select
      aria-label={label}
      className={cx(
        "h-9 rounded border border-line bg-surface px-2.5 text-sm text-ink focus:outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/25",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
}

/** A row of mutually exclusive filter buttons. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string; count?: number }[];
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded border border-line bg-surface p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={cx(
            "h-7 rounded-[4px] px-2.5 text-xs font-medium transition-colors",
            value === option.value ? "bg-raised text-ink" : "text-muted hover:text-ink",
          )}
        >
          {option.label}
          {option.count !== undefined && <span className="ml-1.5 tabular text-faint">{option.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Display
// ---------------------------------------------------------------------------

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cx("panel min-w-0", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cx("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Badge({
  children,
  severity = "none",
  className,
  title,
}: {
  children: ReactNode;
  severity?: Severity;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-[4px] px-1.5 py-px text-2xs font-medium",
        severity === "none" ? "bg-raised text-muted" : severityText[severity],
        className,
      )}
      style={severity === "none" ? undefined : { backgroundColor: `rgb(var(--sev-${severity}) / 0.12)` }}
    >
      {children}
    </span>
  );
}

/** Badge for an engine level label (Low, HIGH, Critical, BEGINNER…). */
export function LevelBadge({ level, fallback = "Not available" }: { level: string | null | undefined; fallback?: string }) {
  if (!level || level === "Not available") return <Badge>{fallback}</Badge>;
  return (
    <Badge severity={severityOf(level)}>
      <span className={cx("h-1.5 w-1.5 rounded-full", severityBg[severityOf(level)])} aria-hidden />
      {capitalize(level)}
    </Badge>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded bg-raised", className)} aria-hidden />;
}

export function PageLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-7 w-56" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-3 text-faint">{icon}</div>}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Callout({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "error";
  title?: string;
  children: ReactNode;
}) {
  const Icon = tone === "info" ? Info : AlertTriangle;
  const color = tone === "error" ? "text-critical" : tone === "warning" ? "text-medium" : "text-accent";
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className="flex gap-2.5 rounded border border-line bg-surface px-3 py-2.5 text-sm"
    >
      <Icon className={cx("mt-0.5 h-4 w-4 shrink-0", color)} aria-hidden />
      <div className="min-w-0 text-muted">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children}
      </div>
    </div>
  );
}

/** Shown in place of a metric the engine could not produce. */
export function NotAvailable({ reason, compact }: { reason?: string | null; compact?: boolean }) {
  return (
    <span className="text-sm text-faint" title={reason ?? undefined}>
      Not available
      {!compact && reason && <span className="mt-1 block text-xs leading-snug text-muted">{reason}</span>}
    </span>
  );
}

export function Progress({ value, severity, label }: { value: number; severity?: Severity; label: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-1.5 w-full overflow-hidden rounded-full bg-raised"
    >
      <div
        className={cx("h-full rounded-full transition-[width] duration-500", severity ? severityBg[severity] : "bg-accent")}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-line bg-raised px-1 font-mono text-2xs text-muted">{children}</kbd>
  );
}

// ---------------------------------------------------------------------------
// Tabs, pagination, overlays
// ---------------------------------------------------------------------------

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: { value: T; label: string; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const id = useId();
  return (
    <div
      role="tablist"
      aria-label={label}
      className="scroll-thin -mb-px flex gap-1 overflow-x-auto"
      onKeyDown={(event) => {
        const index = tabs.findIndex((tab) => tab.value === value);
        if (event.key === "ArrowRight") onChange(tabs[(index + 1) % tabs.length].value);
        if (event.key === "ArrowLeft") onChange(tabs[(index - 1 + tabs.length) % tabs.length].value);
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.value}
          id={`${id}-${tab.value}`}
          role="tab"
          aria-selected={tab.value === value}
          tabIndex={tab.value === value ? 0 : -1}
          onClick={() => onChange(tab.value)}
          className={cx(
            "whitespace-nowrap border-b-2 px-2.5 py-2 text-sm transition-colors",
            tab.value === value
              ? "border-accent font-medium text-ink"
              : "border-transparent text-muted hover:text-ink",
          )}
        >
          {tab.label}
          {tab.count !== undefined && <span className="ml-1.5 tabular text-xs text-faint">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Pagination({
  page,
  pageCount,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  if (total === 0) return null;
  const from = page * pageSize + 1;
  const to = Math.min(total, from + pageSize - 1);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 px-1 pt-3 text-xs text-muted">
      <span className="tabular">
        {from}–{to} of {total.toLocaleString()}
      </span>
      {pageCount > 1 && (
        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={() => onPage(page - 1)} disabled={page === 0} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="tabular">
            {page + 1} / {pageCount}
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onPage(page + 1)}
            disabled={page >= pageCount - 1}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </nav>
  );
}

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);
}

/** Moves focus into an overlay when it opens and back when it closes. */
function useFocusReturn(open: boolean, container: RefObject<HTMLElement>) {
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    container.current?.focus();
    return () => previous?.focus?.();
  }, [open, container]);
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEscape(open, onClose);
  useFocusReturn(open, ref);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-canvas/70 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="panel relative w-full max-w-md focus:outline-none"
      >
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="px-4 py-4 text-sm text-muted">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  label,
  children,
  width = "max-w-3xl",
}: {
  open: boolean;
  onClose: () => void;
  label: string;
  children: ReactNode;
  width?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEscape(open, onClose);
  useFocusReturn(open, ref);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-canvas/60" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className={cx(
          "absolute inset-y-0 right-0 flex w-full flex-col border-l border-line bg-canvas focus:outline-none",
          "animate-[drawer-in_160ms_ease-out]",
          width,
        )}
      >
        {children}
      </div>
      <style>{`@keyframes drawer-in{from{transform:translateX(24px);opacity:.4}to{transform:none;opacity:1}}`}</style>
    </div>
  );
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline-flex">
      <span aria-describedby={id} tabIndex={0} className="inline-flex focus:outline-none">
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-30 mb-1.5 w-max max-w-[16rem] -translate-x-1/2 rounded border border-line bg-surface px-2 py-1.5 text-xs leading-snug text-muted opacity-0 transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        {content}
      </span>
    </span>
  );
}

/** A small "?" that answers "What does this mean?" on hover or keyboard focus. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip content={children}>
      <span
        className="inline-flex h-4 w-4 cursor-help items-center justify-center text-faint hover:text-muted"
        aria-label={`What does ${label} mean?`}
        role="img"
      >
        <CircleHelp className="h-3.5 w-3.5" aria-hidden />
      </span>
    </Tooltip>
  );
}

/** An expandable explanation, collapsed by default. */
export function Explainer({ title, children, defaultOpen }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="group rounded border border-line bg-surface" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <ChevronDown className="h-4 w-4 -rotate-90 text-faint transition-transform group-open:rotate-0" aria-hidden />
        {title}
      </summary>
      <div className="border-t border-line px-3 py-2.5 text-sm text-muted">{children}</div>
    </details>
  );
}

/** One evidence line: ✓ met, ⚠ missing, – unavailable. */
export function EvidenceItem({
  status,
  children,
  detail,
}: {
  status: "ok" | "missing" | "unavailable";
  children: ReactNode;
  detail?: ReactNode;
}) {
  const mark =
    status === "ok" ? (
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-low/15 text-[10px] font-bold text-low">✓</span>
    ) : status === "missing" ? (
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-medium/15 text-[10px] font-bold text-medium">!</span>
    ) : (
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-raised text-[10px] font-bold text-faint">–</span>
    );
  return (
    <li className="flex gap-2.5 text-sm">
      <span className="mt-0.5 shrink-0" aria-label={status === "ok" ? "Found" : status === "missing" ? "Not found" : "Unavailable"}>
        {mark}
      </span>
      <span className="min-w-0">
        <span className={status === "ok" ? "text-ink" : "text-muted"}>{children}</span>
        {detail && <span className="block text-xs text-faint">{detail}</span>}
      </span>
    </li>
  );
}
