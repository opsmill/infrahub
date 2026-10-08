// PROTO number-pool — the details page: header, then the scope and ranges cards beside the allocations card. Delete with the prototype.
import { Button } from "@infrahub/ui";
import { PencilLineIcon } from "lucide-react";
import React from "react";

import { classNames } from "@/shared/utils/common";

import { Allocations } from "./allocations";
import { type Dataset, type Scope, sortRanges, weightLabel } from "./data";
import { EditPoolContext } from "./editor";
import { PoolHeader } from "./header";
import { ALL, rangeLabel, UsageBar, useSelectedScope } from "./parts";
import { ScopePickerCard } from "./scope-picker";
import { ScopeTable } from "./scope-table";

const card = "overflow-hidden rounded-xl border bg-card shadow-card";

// the same selected-row classes as the IPAM, hierarchy and diff trees
const selectedRow =
  "bg-selected text-selected-foreground shadow-selected hover:bg-selected-highlight";

type RangeChoice = { id: string; title: string; subtitle: string; usage: Scope["usage"] };

function rangeChoices(dataset: Dataset, scope: Scope): RangeChoice[] {
  const ranges = sortRanges(dataset.ranges);
  if (ranges.length === 0) return [];
  return [
    {
      id: ALL,
      title: "All ranges",
      subtitle: `${ranges.length} ${ranges.length === 1 ? "range" : "ranges"}`,
      usage: scope.usage,
    },
    ...ranges.map((r, i) => ({
      id: r.id,
      title: rangeLabel(r),
      subtitle: weightLabel(r),
      usage: scope.rangeUsage[i]!,
    })),
  ];
}

function NoRanges({ dataset }: { dataset: Dataset }) {
  const openEdit = React.use(EditPoolContext);
  return (
    <div className="flex flex-col items-start gap-2 px-4 py-3 text-sm">
      <p className="font-medium">No ranges</p>
      <p className="text-pretty text-foreground-muted">
        This pool can't hand out numbers until it has a range.
        {dataset.pool.schemaDefined ? " Add one in the schema." : ""}
      </p>
      {!dataset.pool.schemaDefined && openEdit && (
        <Button variant="outline" size="sm" onPress={openEdit}>
          <PencilLineIcon />
          Add a range
        </Button>
      )}
    </div>
  );
}

function RangesCard({
  dataset,
  scope,
  rangeId,
  onChange,
}: {
  dataset: Dataset;
  scope: Scope;
  rangeId: string;
  onChange: (id: string) => void;
}) {
  const choices = rangeChoices(dataset, scope);
  return (
    <div className={classNames("shrink-0 pb-2", card)}>
      <h2 className="px-4 pt-3 pb-1 font-medium text-foreground-muted text-xs">Ranges</h2>
      {choices.length === 0 ? (
        <NoRanges dataset={dataset} />
      ) : (
        <div role="radiogroup" aria-label="Range" className="flex flex-col px-1.5">
          {choices.map((choice) => {
            const isSelected = choice.id === rangeId;
            return (
              <button
                key={choice.id}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => onChange(choice.id)}
                className={classNames(
                  "flex flex-col gap-1.5 rounded-lg px-2.5 py-2 text-left transition-[background-color,box-shadow,color] duration-150",
                  "focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2",
                  isSelected ? selectedRow : "hover:bg-highlight"
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium text-sm tabular-nums">{choice.title}</span>
                  <span className="shrink-0 text-foreground-muted text-xs">{choice.subtitle}</span>
                </span>
                <UsageBar usage={choice.usage} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ScopeView({ dataset, scope }: { dataset: Dataset; scope: Scope }) {
  const [rangeId, setRangeId] = React.useState(rangeChoices(dataset, scope)[0]?.id ?? ALL);
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[18rem_minmax(0,1fr)] gap-2 px-2 pb-2">
      <aside className="relative flex min-h-0 flex-col gap-2 overflow-y-auto overscroll-contain">
        {dataset.scopes && (
          <div className={classNames("shrink-0", card)}>
            <ScopePickerCard dataset={dataset} />
          </div>
        )}
        <RangesCard dataset={dataset} scope={scope} rangeId={rangeId} onChange={setRangeId} />
      </aside>
      <div className={classNames("flex min-h-0 min-w-0 flex-col", card)}>
        <Allocations dataset={dataset} scope={scope} rangeFilter={rangeId} />
      </div>
    </div>
  );
}

export function PoolDetails({ dataset }: { dataset: Dataset }) {
  const [selected, setScope] = useSelectedScope(dataset);
  const scope = dataset.scopes ? selected : dataset.implicitScope;
  const onlyScope = dataset.scopes?.length === 1 ? dataset.scopes[0]! : null;

  // a list of one scope is a dead end, so the page opens it directly
  React.useEffect(() => {
    if (onlyScope && !selected) setScope(onlyScope);
  });

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PoolHeader dataset={dataset} />
      {scope ? (
        <ScopeView key={scope.id} dataset={dataset} scope={scope} />
      ) : (
        // the scope table already searches and opens scopes, so it is the only card until one is picked
        <div className="flex min-h-0 flex-1 flex-col px-2 pb-2">
          <div className={classNames("flex min-h-0 min-w-0 flex-1 flex-col", card)}>
            <ScopeTable dataset={dataset} />
          </div>
        </div>
      )}
    </div>
  );
}
