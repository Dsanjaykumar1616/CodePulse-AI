import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cx, NotAvailable, Tooltip } from "./ui";
import { severityText, type Severity } from "../lib/format";
import type { SortDir } from "../hooks/queries";
import type { Metric } from "../types/api";

export function MetricCard({
  label,
  metric,
  format = (value) => value.toLocaleString(),
  severity,
  hint,
  suffix,
  detail,
}: {
  label: string;
  metric: Metric;
  format?: (value: number) => string;
  severity?: Severity;
  hint?: string;
  suffix?: string;
  detail?: ReactNode;
}) {
  return (
    <div className="panel min-w-0 px-4 py-3.5">
      <div className="flex items-center gap-1 text-xs text-muted">
        {hint ? (
          <Tooltip content={hint}>
            <span className="cursor-help underline decoration-dotted decoration-faint underline-offset-2">{label}</span>
          </Tooltip>
        ) : (
          label
        )}
      </div>
      <div className="mt-1.5">
        {metric.available && metric.value !== null ? (
          <div className="flex items-baseline gap-1">
            <span className={cx("tabular text-2xl font-semibold tracking-tight", severity ? severityText[severity] : "text-ink")}>
              {format(metric.value)}
            </span>
            {suffix && <span className="text-xs text-faint">{suffix}</span>}
          </div>
        ) : (
          <NotAvailable reason={metric.reason} />
        )}
      </div>
      {detail && metric.available && <div className="mt-1 text-xs text-muted">{detail}</div>}
    </div>
  );
}

/** A circular score (0–100). */
export function ScoreRing({
  value,
  size = 120,
  severity,
  label,
  caption,
}: {
  value: number | null;
  size?: number;
  severity: Severity;
  label: string;
  caption?: string;
}) {
  const stroke = Math.max(6, size / 14);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = value === null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${label}: ${value ?? "not available"}`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgb(var(--raised))" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={severity === "none" ? "rgb(var(--faint))" : `rgb(var(--sev-${severity}))`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circumference * fraction} ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray 600ms ease-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular font-semibold tracking-tight" style={{ fontSize: size / 3.6 }}>
          {value === null ? "—" : Math.round(value)}
        </span>
        {caption && <span className="text-2xs text-muted">{caption}</span>}
      </div>
    </div>
  );
}

/** A sortable column header for plain HTML tables. */
export function SortHeader<K extends string>({
  label,
  column,
  sort,
  onSort,
  align = "left",
  title,
}: {
  label: string;
  column: K;
  sort: { key: string; dir: SortDir } | null;
  onSort: (column: K) => void;
  align?: "left" | "right";
  title?: string;
}) {
  const active = sort?.key === column;
  const Icon = !active ? ArrowUpDown : sort!.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"}
      className={cx("px-3 py-2 font-medium", align === "right" && "text-right")}
    >
      <button
        type="button"
        title={title}
        onClick={() => onSort(column)}
        className={cx(
          "inline-flex items-center gap-1 whitespace-nowrap hover:text-ink",
          active ? "text-ink" : "text-muted",
          align === "right" && "flex-row-reverse",
        )}
      >
        {label}
        <Icon className={cx("h-3 w-3", active ? "opacity-100" : "opacity-40")} aria-hidden />
      </button>
    </th>
  );
}

export function Th({ children, align = "left" }: { children?: ReactNode; align?: "left" | "right" }) {
  return (
    <th scope="col" className={cx("whitespace-nowrap px-3 py-2 font-medium text-muted", align === "right" && "text-right")}>
      {children}
    </th>
  );
}

export function TableShell({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="scroll-thin -mx-4 overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm" aria-label={label}>
        {children}
      </table>
    </div>
  );
}

export const theadClass = "border-y border-line bg-raised/50 text-left text-xs";
export const rowClass = "border-b border-line last:border-0 hover:bg-raised/40";
export const cellClass = "px-3 py-2 align-middle";
