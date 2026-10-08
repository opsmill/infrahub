// PROTO number-pool — small helpers shared by the page, the scope picker and the sheets. Delete with the prototype.
import { Tooltip } from "@infrahub/ui";
import { useSearchParams } from "react-router";

import MultipleProgressBar from "@/shared/components/stats/multiple-progress-bar";
import { classNames } from "@/shared/utils/common";

import type { Dataset, Range, Scope, Usage } from "./data";

export const fmt = new Intl.NumberFormat("en-US");

export const ALL = "__all";

export function formatPercent(value: number) {
  if (value === 0) return "0%";
  if (value < 0.1) return "<0.1%";
  if (value < 10) return `${value.toFixed(1).replace(/\.0$/, "")}%`;
  return `${Math.floor(value)}%`;
}

export const rangeLabel = (range: Range) => `${fmt.format(range.start)} – ${fmt.format(range.end)}`;

const pct = (n: number, total: number) => (total === 0 ? 0 : (n / total) * 100);

export const usedPercent = (usage: Usage) => pct(usage.defaultUsed + usage.branchUsed, usage.total);

function UsageTooltip({ title, value }: { title: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-white/70 text-xxs">{title}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

export function UsageBar({ usage, className }: { usage: Usage; className?: string }) {
  const used = usage.defaultUsed + usage.branchUsed;
  return (
    <div className={classNames("flex w-full items-center gap-2", className)}>
      <MultipleProgressBar
        className="h-1.5"
        aria-label="Usage"
        elements={[
          {
            value: pct(usage.defaultUsed, usage.total),
            color: "var(--accent-strong)",
            tooltip: (
              <UsageTooltip
                title="Default branch"
                value={`${fmt.format(usage.defaultUsed)} of ${fmt.format(usage.total)}`}
              />
            ),
          },
          {
            value: pct(usage.branchUsed, usage.total),
            color: "color-mix(in oklch, var(--accent-strong) 45%, transparent)",
            tooltip: (
              <UsageTooltip
                title="Other branches only"
                value={`${fmt.format(usage.branchUsed)} of ${fmt.format(usage.total)}`}
              />
            ),
          },
        ]}
      />
      <Tooltip
        nonInteractiveTrigger
        message={
          <UsageTooltip title="Used" value={`${fmt.format(used)} of ${fmt.format(usage.total)}`} />
        }
      >
        <span className="w-11 shrink-0 text-right font-medium text-foreground text-xs tabular-nums">
          {formatPercent(pct(used, usage.total))}
        </span>
      </Tooltip>
    </div>
  );
}

// the picked scope lives in the URL, so a scope can be linked and opened in a new tab
export function useSelectedScope(dataset: Dataset) {
  const [params, setParams] = useSearchParams();
  const id = params.get("scope");
  const scope = dataset.scopes?.find((s) => s.id === id) ?? null;
  const setScope = (next: Scope | null) =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next) p.set("scope", next.id);
        else p.delete("scope");
        return p;
      },
      { replace: true }
    );
  return [scope, setScope] as const;
}
