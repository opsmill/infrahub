// @ts-nocheck
import { Button } from "@infrahub/ui";
import { ArrowDownIcon, ArrowUpIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import React from "react";

import { Icon } from "@/shared/components/display/icon";
import { Skeleton } from "@/shared/components/loading/skeleton";
import Content from "@/shared/components/layout/content";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { isExact, KINDS, type ProtoNode, searchExactFirst } from "./data";
import { ExactMatchBadge, nodeColumns, useFakeSearch, useProto } from "./shared";

const PAGE_SIZE = 10;

/** Every match on one page, grouped by node kind, one sortable paged table per kind (the PR #8448 shape). */
export function ResultsPage() {
  const { query, setQuery, caseSensitive } = useProto();
  const search = useFakeSearch(query, (q) => searchExactFirst(q, caseSensitive, 0), {
    key: String(caseSensitive),
    delay: [900, 1600],
  });

  const groups = (() => {
    if (search.status !== "success") return [];
    const byKind = new Map<string, ProtoNode[]>();
    for (const node of search.data.nodes) {
      if (node.kind === "CoreAccount") continue;
      byKind.set(node.kind, [...(byKind.get(node.kind) ?? []), node]);
    }
    return [...byKind.entries()].sort(
      ([, a], [, b]) =>
        Number(b.some((n) => isExact(n, query, caseSensitive))) -
          Number(a.some((n) => isExact(n, query, caseSensitive))) || b.length - a.length
    );
  })();

  const total = groups.reduce((sum, [, nodes]) => sum + nodes.length, 0);

  return (
    <Content className="p-1">
      <Content.Card className="min-h-full">
        <Content.CardTitle
          title="Search results"
          description={
            search.status === "success" ? (
              <span className="tabular-nums">
                {total} {total === 1 ? "object matches" : "objects match"} “{query.trim()}”
              </span>
            ) : search.status === "error" ? (
              "The search failed"
            ) : (
              "Loading every match…"
            )
          }
          end={
            <label className="relative flex h-9 w-full max-w-sm items-center rounded-lg border border-input-border bg-input shadow-input focus-within:border-ring">
              <span className="sr-only">Search</span>
              <Icon icon="mdi:magnify" aria-hidden="true" className="absolute left-2.5 text-accent text-lg" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                spellCheck={false}
                autoComplete="off"
                className="h-full w-full bg-transparent pr-3 pl-9 text-base text-foreground outline-hidden md:text-sm"
              />
            </label>
          }
        />

        <div className="space-y-4 p-4">
          {search.status === "loading" &&
            Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="space-y-3 rounded-lg border p-4" aria-hidden="true">
                <Skeleton className="h-4 w-40" />
                {Array.from({ length: 4 }, (__, j) => (
                  <Skeleton key={j} className="h-3 w-full" />
                ))}
              </div>
            ))}

          {search.status === "error" && (
            <div role="alert" className="flex flex-col items-center gap-2 py-12 text-center">
              <p className="font-medium text-sm">The search failed</p>
              <Button size="xs" variant="outline" onPress={search.retry}>
                Try again
              </Button>
            </div>
          )}

          {search.status === "success" && total === 0 && (
            <p className="py-12 text-center text-sm text-subtle">No object matches “{query.trim()}”.</p>
          )}

          {groups.map(([kind, nodes]) => (
            <KindTable key={kind} kind={kind} nodes={nodes} />
          ))}
        </div>
      </Content.Card>
    </Content>
  );
}

function KindTable({ kind, nodes }: { kind: string; nodes: ProtoNode[] }) {
  const { query, caseSensitive, openNode } = useProto();
  const [page, setPage] = React.useState(0);
  const [direction, setDirection] = React.useState<"relevance" | "asc" | "desc">("relevance");
  const meta = KINDS[kind];

  const sorted =
    direction === "relevance"
      ? nodes
      : [...nodes].sort((a, b) =>
          direction === "asc" ? a.label.localeCompare(b.label) : b.label.localeCompare(a.label)
        );
  const rows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const columns = nodeColumns(nodes[0]).slice(0, 4);
  const pageCount = Math.ceil(nodes.length / PAGE_SIZE);

  const cycleSort = () => {
    setDirection((d) => (d === "relevance" ? "asc" : d === "asc" ? "desc" : "relevance"));
    setPage(0);
  };

  return (
    <section className="overflow-hidden rounded-lg border bg-content" aria-label={meta.plural}>
      <header className="flex items-center gap-2 border-b px-4 py-2.5">
        <Icon icon={meta.icon} aria-hidden="true" className="text-accent text-lg" />
        <h2 className="font-semibold text-sm">{meta.plural}</h2>
        <Badge variant="blue" className="py-0 text-xxs">
          {meta.namespace}
        </Badge>
        <span className="text-subtle text-xs tabular-nums">{nodes.length}</span>
      </header>

      <table className="w-full table-fixed text-sm">
        <thead>
          <tr className="border-b text-left text-subtle text-xs">
            <th className="w-[32%] px-4 py-2 font-medium">
              <button
                type="button"
                onClick={cycleSort}
                className="inline-flex items-center gap-1 rounded outline-hidden hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                Name
                {direction === "asc" && <ArrowUpIcon aria-label="ascending" className="size-3" />}
                {direction === "desc" && <ArrowDownIcon aria-label="descending" className="size-3" />}
              </button>
            </th>
            {columns.map((col) => (
              <th key={col.name} className="px-4 py-2 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((node) => (
            <tr key={node.id} className="border-b last:border-b-0 hover:bg-highlight">
              <td className="px-4 py-2">
                <button
                  type="button"
                  onClick={() => openNode(node)}
                  className="flex w-full min-w-0 items-center gap-2 rounded text-left outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="truncate font-semibold text-accent">{node.label}</span>
                  {isExact(node, query, caseSensitive) && <ExactMatchBadge />}
                </button>
              </td>
              {nodeColumns(node)
                .slice(0, 4)
                .map((col) => (
                  <td key={col.name} className="truncate px-4 py-2 text-foreground-muted">
                    {col.value || "-"}
                  </td>
                ))}
            </tr>
          ))}
        </tbody>
      </table>

      {pageCount > 1 && (
        <div
          className={classNames(
            "flex items-center justify-end gap-2 border-t px-4 py-2 text-subtle text-xs tabular-nums"
          )}
        >
          {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, nodes.length)} of {nodes.length}
          <Button
            size="xs"
            variant="outline"
            shape="square"
            aria-label="Previous page"
            isDisabled={page === 0}
            onPress={() => setPage((p) => p - 1)}
          >
            <ChevronLeftIcon />
          </Button>
          <Button
            size="xs"
            variant="outline"
            shape="square"
            aria-label="Next page"
            isDisabled={page + 1 >= pageCount}
            onPress={() => setPage((p) => p + 1)}
          >
            <ChevronRightIcon />
          </Button>
        </div>
      )}
    </section>
  );
}
