// PROTO number-pool — one scope's numbers: filter bar, sticky column header, infinite scroll. Delete with the prototype.
import { Button, Select, SelectItem, SelectList, SelectTrigger, Spinner } from "@infrahub/ui";
import { GitBranchIcon, XIcon } from "lucide-react";
import React from "react";

import { SearchInput } from "@/shared/components/inputs/search-input";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import {
  ALL_BRANCHES,
  type Allocation,
  type Dataset,
  getAllocations,
  type Range,
  type Scope,
  sortRanges,
} from "./data";
import { ALL, fmt, rangeLabel } from "./parts";

const ROW_HEIGHT = 37;
const BATCH = 100;
const OVERSCAN = 12;

const SOURCES = [
  { id: "Allocated", label: "Allocated" },
  { id: "Provided", label: "Provided" },
];
const BRANCH_OPTIONS = ALL_BRANCHES.map((b) => ({ id: b, label: b }));

const th = "h-8 px-3 text-left font-medium text-foreground-muted text-xs whitespace-nowrap";
const td = "h-9 px-3 text-sm whitespace-nowrap";

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { id: string; label: string }[];
}) {
  return (
    <Select
      aria-label={label}
      value={value}
      onChange={(key) => onChange(String(key))}
      className="w-44"
    >
      <SelectTrigger size="sm" />
      <SelectList
        items={[{ id: ALL, label: `All ${label.toLowerCase()}` }, ...options]}
        width="content"
      >
        {(option) => <SelectItem>{option.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}

function SourceTag({ source }: { source: Allocation["source"] }) {
  return (
    <span
      className={classNames(
        "inline-flex h-5 items-center gap-1.5 rounded-md px-1.5 font-medium text-xs",
        source === "Provided" ? "bg-active-surface text-active" : "bg-accent-surface text-accent"
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {source}
    </span>
  );
}

function AllocationRow({ allocation: a, range }: { allocation: Allocation; range?: Range }) {
  return (
    <tr className="not-last:border-b hover:bg-highlight">
      <td className={classNames(td, "text-right font-medium tabular-nums")}>
        {fmt.format(a.number)}
      </td>
      <td className={td}>
        <Link to=".">{a.objectLabel}</Link>
      </td>
      <td className={classNames(td, "text-foreground-muted")}>{a.kind}</td>
      <td className={td}>
        {a.branch === "main" ? (
          <span className="text-foreground-muted">main</span>
        ) : (
          <span className="inline-flex items-center gap-1">
            <GitBranchIcon className="size-3.5 text-foreground-muted" aria-hidden />
            {a.branch}
          </span>
        )}
      </td>
      {range && (
        <td className={classNames(td, "text-foreground-muted tabular-nums")}>
          {rangeLabel(range)}
        </td>
      )}
      <td className={td}>
        <SourceTag source={a.source} />
      </td>
    </tr>
  );
}

export function Allocations({
  dataset,
  scope,
  rangeFilter,
}: {
  dataset: Dataset;
  scope: Scope;
  rangeFilter: string;
}) {
  const allocations = getAllocations(dataset, scope);
  const ranges = sortRanges(dataset.ranges);
  const rangeById = new Map<string, Range>(ranges.map((r) => [r.id, r]));
  const [search, setSearch] = React.useState("");
  const [source, setSource] = React.useState(ALL);
  const [branch, setBranch] = React.useState(ALL);
  const [loaded, setLoaded] = React.useState(BATCH);
  const [isLoading, setIsLoading] = React.useState(false);
  const [scrollTop, setScrollTop] = React.useState(0);
  const [viewport, setViewport] = React.useState(800);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const isFiltered = search !== "" || source !== ALL || branch !== ALL;

  const filtered = allocations.filter(
    (a) =>
      (rangeFilter === ALL || a.rangeId === rangeFilter) &&
      (search === "" || String(a.number).includes(search.replace(/[^0-9]/g, ""))) &&
      (source === ALL || a.source === source) &&
      (branch === ALL || a.branch === branch)
  );
  const total = filtered.length;
  const available = Math.min(loaded, total);
  const showRangeColumn = ranges.length > 1 && rangeFilter === ALL;
  const columns = showRangeColumn ? 6 : 5;

  // a new filter is a new server query, so the list starts over from the top
  const filterKey = `${search}|${source}|${branch}|${rangeFilter}`;
  const [lastKey, setLastKey] = React.useState(filterKey);
  if (lastKey !== filterKey) {
    setLastKey(filterKey);
    setLoaded(BATCH);
    setScrollTop(0);
    scrollRef.current?.scrollTo({ top: 0 });
  }

  const loadMore = () => {
    if (isLoading || available >= total) return;
    setIsLoading(true);
    // stands in for the next page from the API
    setTimeout(() => {
      setLoaded((n) => n + BATCH);
      setIsLoading(false);
    }, 350);
  };

  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    setScrollTop(el.scrollTop);
    setViewport(el.clientHeight);
    if (el.scrollHeight - el.scrollTop - el.clientHeight < ROW_HEIGHT * 15) loadMore();
  };

  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const end = Math.min(available, Math.ceil((scrollTop + viewport) / ROW_HEIGHT) + OVERSCAN);
  const rows = filtered.slice(start, end);

  if (allocations.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-foreground-muted text-sm">No allocations yet</p>
    );
  }

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <span className="font-semibold text-sm">Allocations</span>
        <span className="text-foreground-muted text-sm tabular-nums">
          {fmt.format(allocations.length)}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {isFiltered && (
            <Button
              variant="ghost"
              size="xxs"
              className="text-foreground-muted"
              onPress={() => {
                setSearch("");
                setSource(ALL);
                setBranch(ALL);
              }}
            >
              <XIcon />
              Clear
            </Button>
          )}
          <SearchInput
            className="h-7 w-48 text-sm"
            placeholder="Search number"
            value={search}
            onChange={setSearch}
            onPressReset={() => setSearch("")}
          />
          <FilterSelect label="Sources" value={source} onChange={setSource} options={SOURCES} />
          <FilterSelect
            label="Branches"
            value={branch}
            onChange={setBranch}
            options={BRANCH_OPTIONS}
          />
        </div>
      </div>
      <div ref={scrollRef} onScroll={onScroll} className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-table-cell-pinned shadow-[0_1px_0_var(--border)]">
            <tr>
              <th className={classNames(th, "text-right")}>Number</th>
              <th className={th}>Object</th>
              <th className={th}>Kind</th>
              <th className={th}>Branch</th>
              {showRangeColumn && <th className={th}>Range</th>}
              <th className={th}>Source</th>
            </tr>
          </thead>
          <tbody className="bg-table-cell">
            {start > 0 && (
              <tr aria-hidden style={{ height: start * ROW_HEIGHT }}>
                <td colSpan={columns} />
              </tr>
            )}
            {rows.map((a) => (
              <AllocationRow
                key={a.objectId}
                allocation={a}
                range={showRangeColumn ? rangeById.get(a.rangeId) : undefined}
              />
            ))}
            {end < available && (
              <tr aria-hidden style={{ height: (available - end) * ROW_HEIGHT }}>
                <td colSpan={columns} />
              </tr>
            )}
          </tbody>
        </table>
        {total === 0 && (
          <p className="py-8 text-center text-foreground-muted text-sm">
            {rangeFilter !== ALL && !isFiltered
              ? `No allocations in ${rangeLabel(rangeById.get(rangeFilter)!)}`
              : "No allocations match these filters"}
          </p>
        )}
        {available < total && (
          <div className="flex h-12 items-center justify-center gap-2 text-foreground-muted text-xs">
            <Spinner className="size-3.5" /> Loading more
          </div>
        )}
        <div className="h-24" aria-hidden />
      </div>
    </section>
  );
}
