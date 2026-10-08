// PROTO number-pool — the page before a scope is picked: every scope, fullest first, as links. Delete with the prototype.
import React from "react";
import { Link as RouterLink, useSearchParams } from "react-router";

import { SearchInput } from "@/shared/components/inputs/search-input";
import { classNames } from "@/shared/utils/common";

import type { Dataset, Scope } from "./data";
import { fmt, UsageBar, usedPercent } from "./parts";

const LIST_LIMIT = 100;

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const NEW_TAB_HINT = `${isMac ? "⌘" : "Ctrl"}-click to open in a new tab`;

// a collapsed table border stays with the table, so the pinned column draws its own edge
const PINNED_EDGE =
  "before:pointer-events-none before:absolute before:inset-y-0 before:left-0 before:w-px before:bg-border";

// the table surface is slightly translucent in dark mode; a pinned cell needs the same colour fully opaque
const PINNED_SURFACE: React.CSSProperties = {
  background:
    "linear-gradient(var(--table-cell-pinned), var(--table-cell-pinned)), var(--color-black)",
};

const th = "h-8 px-3 text-left font-medium text-foreground-muted text-xs whitespace-nowrap";

const scopeText = (s: Scope) => s.peers.map((p) => p.label || "No value").join(" · ");

// a real link keeps every query param and swaps the scope, so the browser's own modifier-click opens a new tab
function ScopeLink({
  scope,
  className,
  children,
}: {
  scope: Scope;
  className?: string;
  children: React.ReactNode;
}) {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  next.set("scope", scope.id);
  return (
    <RouterLink to={{ search: `?${next.toString()}` }} className={className}>
      {children}
    </RouterLink>
  );
}

function PeerValue({ label, kind }: { label: string; kind: string }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className={classNames("truncate", label === "" && "text-foreground-muted italic")}>
        {label || "No value"}
      </span>
      <span className="truncate font-mono text-foreground-muted text-xxs">{kind}</span>
    </span>
  );
}

export function ScopeTable({ dataset }: { dataset: Dataset }) {
  const [search, setSearch] = React.useState("");
  const [sortByName, setSortByName] = React.useState(false);
  const relations = dataset.pool.scopedBy;
  const all = [...(dataset.scopes ?? [])].sort(
    (a, b) => usedPercent(b.usage) - usedPercent(a.usage)
  );
  const needle = search.trim().toLowerCase();
  const searched = needle ? all.filter((s) => scopeText(s).toLowerCase().includes(needle)) : all;
  const sorted = sortByName
    ? [...searched].sort((a, b) => scopeText(a).localeCompare(scopeText(b)))
    : searched;
  const shown = sorted.slice(0, LIST_LIMIT);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b px-3 py-2">
        <span className="font-semibold text-sm">Scopes</span>
        <span className="text-foreground-muted text-sm tabular-nums">{fmt.format(all.length)}</span>
        <SearchInput
          className="h-7 w-64 text-sm"
          placeholder={`Search ${relations.map((r) => r.label.toLowerCase()).join(" or ")}`}
          value={search}
          onChange={setSearch}
          onPressReset={() => setSearch("")}
          autoFocus
        />
        <span className="ml-auto text-foreground-muted text-xs">{NEW_TAB_HINT}</span>
      </div>
      <div className="relative min-h-0 flex-1 overflow-auto overscroll-contain pb-28">
        <table className="min-w-full border-collapse">
          <thead className="sticky top-0 z-20 bg-table-cell-pinned shadow-[0_1px_0_var(--border)]">
            <tr>
              {relations.map((r, i) => (
                <th key={r.name} className={th}>
                  {i === 0 ? (
                    <button
                      type="button"
                      onClick={() => setSortByName(true)}
                      className="hover:text-foreground"
                    >
                      {r.label}
                      {sortByName && " ↑"}
                    </button>
                  ) : (
                    r.label
                  )}
                </th>
              ))}
              <th
                className={classNames(th, "sticky right-0 z-10 w-64 min-w-64", PINNED_EDGE)}
                style={PINNED_SURFACE}
                aria-sort={sortByName ? undefined : "descending"}
              >
                <button
                  type="button"
                  onClick={() => setSortByName(false)}
                  className="hover:text-foreground"
                >
                  Usage{!sortByName && " ↓"}
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="bg-table-cell-pinned">
            {shown.map((s) => (
              <tr key={s.id} className="not-last:border-b hover:bg-highlight">
                {relations.map((r, i) => {
                  const peer = s.peers.find((p) => p.relation === r.name);
                  const value = <PeerValue label={peer?.label ?? ""} kind={peer?.kind ?? ""} />;
                  return (
                    <td
                      key={r.name}
                      className="h-11 min-w-40 max-w-64 whitespace-nowrap px-3 text-sm"
                    >
                      {i === 0 ? (
                        <ScopeLink scope={s} className="block font-medium hover:underline">
                          {value}
                        </ScopeLink>
                      ) : (
                        value
                      )}
                    </td>
                  );
                })}
                <td
                  className={classNames("sticky right-0 w-64 min-w-64 px-3", PINNED_EDGE)}
                  style={PINNED_SURFACE}
                >
                  <UsageBar usage={s.usage} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length > LIST_LIMIT && (
          <p className="px-3 py-3 text-center text-foreground-muted text-xs">
            Showing {LIST_LIMIT} of {fmt.format(sorted.length)}. Search to find others.
          </p>
        )}
        {sorted.length === 0 && (
          <p className="px-3 py-8 text-center text-foreground-muted text-sm">No scope matches</p>
        )}
      </div>
    </div>
  );
}
