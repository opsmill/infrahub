// PROTO number-pool — the allocation scope card: one searchable select over every scope, fullest first. Delete with the prototype.
import { Autocomplete, ListBox, Popover, Select, SelectItem, SelectTrigger } from "@infrahub/ui";
import React from "react";
import { Link as RouterLink, useSearchParams } from "react-router";

import type { Dataset, Scope, ScopeRelation } from "./data";
import { formatPercent, usedPercent, useSelectedScope } from "./parts";

const valueLabel = (label: string) => label || "No value";

const article = (relation: ScopeRelation) =>
  relation.label === "VRF" ? "a VRF" : `a ${relation.label.toLowerCase()}`;

const placeholderFor = (relations: ScopeRelation[]) =>
  relations.length > 2 ? "Select a scope" : `Select ${relations.map(article).join(" and ")}`;

function PeerLabels({ scope, relations }: { scope: Scope; relations: ScopeRelation[] }) {
  return (
    <>
      {relations.map((r, i) => {
        const label = scope.peers.find((p) => p.relation === r.name)?.label ?? "";
        return (
          <React.Fragment key={r.name}>
            {i > 0 && <span className="text-foreground-muted"> · </span>}
            <span className={label === "" ? "text-foreground-muted italic" : undefined}>
              {valueLabel(label)}
            </span>
          </React.Fragment>
        );
      })}
    </>
  );
}

function MiniMeter({ percent }: { percent: number }) {
  return (
    <span
      className="inline-flex h-1 w-12 overflow-hidden rounded-full bg-custom-blue-600/10"
      aria-hidden
    >
      <span className="h-full bg-accent-strong" style={{ width: `${percent}%` }} />
    </span>
  );
}

function ScopeSearchSelect({ dataset }: { dataset: Dataset }) {
  const relations = dataset.pool.scopedBy;
  const [scope, setScope] = useSelectedScope(dataset);
  const scopes = [...(dataset.scopes ?? [])].sort(
    (a, b) => usedPercent(b.usage) - usedPercent(a.usage)
  );
  const textOf = (s: Scope) => s.peers.map((p) => valueLabel(p.label)).join(" · ");

  return (
    <Select
      aria-label="Allocation scope"
      placeholder={placeholderFor(relations)}
      value={scope?.id ?? null}
      onChange={(key) => setScope(scopes.find((s) => s.id === key) ?? null)}
      className="w-full"
    >
      <SelectTrigger size="sm" />
      <Popover placement="bottom start" className="w-[32rem]">
        <Autocomplete>
          <ListBox selectionMode="single" items={scopes} virtualized className="max-h-80">
            {(s) => (
              <SelectItem id={s.id} textValue={textOf(s)}>
                <span className="flex w-full items-center gap-2">
                  <span className="min-w-0 flex-1 truncate">
                    <PeerLabels scope={s} relations={relations} />
                  </span>
                  <span className="flex in-[button]:hidden shrink-0 items-center gap-2 text-xs tabular-nums">
                    <MiniMeter percent={usedPercent(s.usage)} />
                    <span className="w-10 text-right">{formatPercent(usedPercent(s.usage))}</span>
                  </span>
                </span>
              </SelectItem>
            )}
          </ListBox>
        </Autocomplete>
      </Popover>
    </Select>
  );
}

function AllScopesLink() {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  next.delete("scope");
  return (
    <RouterLink
      to={{ search: `?${next.toString()}` }}
      className="text-foreground-muted text-xs hover:text-foreground hover:underline"
    >
      All scopes
    </RouterLink>
  );
}

export function ScopePickerCard({ dataset }: { dataset: Dataset }) {
  return (
    <div className="flex flex-col gap-1.5 px-3 py-3">
      <span className="flex items-baseline justify-between px-1">
        <span className="font-medium text-foreground-muted text-xs">Allocation scope</span>
        {(dataset.scopes?.length ?? 0) > 1 && <AllScopesLink />}
      </span>
      <ScopeSearchSelect dataset={dataset} />
    </div>
  );
}
