// @ts-nocheck
import { Button } from "@infrahub/ui";
import { Command } from "cmdk";
import { ArrowRightIcon, ChevronLeftIcon } from "lucide-react";
import React from "react";

import { Icon } from "@/shared/components/display/icon";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Badge } from "@/shared/components/ui/badge";
import { CommandItem } from "@/shared/components/ui/command";
import Kbd from "@/shared/components/ui/kbd";
import { classNames } from "@/shared/utils/common";

import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";

import { isExact, KINDS, type ProtoNode, searchExactFirst } from "./data";
import {
  DocsGroup,
  ExactMatchBadge,
  GoToGroup,
  LoadingObjects,
  NodeRow,
  nodeColumns,
  ParentPrefixesGroup,
  SearchDialogShell,
  SearchInput,
  useFakeSearch,
  useProto,
  useRowDetails,
} from "./shared";

/** Top hit: exact matches as large preselected cards; "Browse all results" turns the dialog into a filterable list. */
export function TopHitVariant() {
  const { query, caseSensitive } = useProto();
  const [browsing, setBrowsing] = React.useState(false);

  React.useEffect(() => {
    if (!query.trim()) setBrowsing(false);
  }, [query]);

  const first = useFakeSearch(query, (q) => searchExactFirst(q, caseSensitive, 4), { key: String(caseSensitive) });

  return (
    <SearchDialogShell>
      <Command shouldFilter={false} loop>
        <SearchInput
          onKeyDown={(e) => {
            if (browsing && e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              setBrowsing(false);
            }
          }}
        />
        {browsing ? (
          <BrowseAll onBack={() => setBrowsing(false)} />
        ) : (
          <Command.List className="[&_[cmdk-group]]:mt-2">
            <GoToGroup />
            <ParentPrefixesGroup prefixes={first.data?.parentPrefixes} />
            {first.status === "loading" && <LoadingObjects />}
            {first.status === "success" && first.data.nodes.length > 0 && (
              <TopResults
                nodes={first.data.nodes}
                hasMore={first.data.hasMore}
                onBrowse={() => setBrowsing(true)}
              />
            )}
            <DocsGroup />
          </Command.List>
        )}
      </Command>
    </SearchDialogShell>
  );
}

function TopResults({ nodes, hasMore, onBrowse }: { nodes: ProtoNode[]; hasMore: boolean; onBrowse: () => void }) {
  const { query, caseSensitive } = useProto();
  const exact = nodes.filter((n) => isExact(n, query, caseSensitive));
  const rest = nodes.filter((n) => !isExact(n, query, caseSensitive));

  return (
    <>
      {exact.length > 0 && (
        <SearchAnywhereGroup heading={exact.length === 1 ? "Top hit" : "Top hits"}>
          {exact.map((node) => (
            <TopHitCard key={node.id} node={node} />
          ))}
        </SearchAnywhereGroup>
      )}
      {(rest.length > 0 || hasMore) && (
        <SearchAnywhereGroup heading={exact.length > 0 ? "Other matches" : "Objects"}>
          {rest.map((node) => (
            <NodeRow key={node.id} node={node} />
          ))}
          {hasMore && (
            <CommandItem value="browse-all" onSelect={onBrowse} className="text-foreground">
              <ArrowRightIcon aria-hidden="true" className="mx-2 size-4 text-subtle" />
              Browse all results
            </CommandItem>
          )}
        </SearchAnywhereGroup>
      )}
    </>
  );
}

function TopHitCard({ node }: { node: ProtoNode }) {
  const { openNode } = useProto();
  const state = useRowDetails(node);
  const meta = KINDS[node.kind];

  if (state === "error") return null;
  if (state === "loading") {
    return (
      <Command.Item disabled className="flex h-[76px] items-center gap-3 px-2">
        <Skeleton className="size-10 rounded-lg" />
        <div className="grow space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-80" />
        </div>
      </Command.Item>
    );
  }

  return (
    <CommandItem value={node.id} onSelect={() => openNode(node)} className="items-start gap-3 px-2 py-3">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-content">
        <Icon icon={meta.icon} aria-hidden="true" className="text-accent text-xl" />
      </span>
      <div className="min-w-0 grow">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold text-accent text-base">{node.label}</span>
          <Badge variant="blue" className="py-0 text-xxs">
            {meta.namespace}
          </Badge>
          <span className="font-medium text-xxs">{meta.label}</span>
        </div>
        <dl className="mt-1.5 grid grid-cols-4 gap-x-4 text-xxs leading-4">
          {nodeColumns(node)
            .slice(0, 4)
            .map((col) => (
              <div key={col.name} className="min-w-0">
                <dt className="text-foreground-muted">{col.label}</dt>
                <dd className="truncate font-medium text-foreground">{col.value || "-"}</dd>
              </div>
            ))}
        </dl>
      </div>
      <Kbd keys="enter" className="hidden shrink-0 self-center bg-surface in-data-[selected=true]:inline-flex" />
    </CommandItem>
  );
}

// ---------- browse all, inside the dialog ----------

function contextOf(node: ProtoNode) {
  if (node.kind === "IpamIPPrefix") return `Namespace ${node.ipNamespace}`;
  return node.context ?? node.peers.find((p) => p.name === "site")?.value ?? node.peers[0]?.value;
}

function BrowseAll({ onBack }: { onBack: () => void }) {
  const { query, caseSensitive } = useProto();
  const [kind, setKind] = React.useState<string | null>(null);
  const all = useFakeSearch(query, (q) => searchExactFirst(q, caseSensitive, 0), {
    key: String(caseSensitive),
    delay: [900, 1600],
  });

  const nodes = all.status === "success" ? all.data.nodes.filter((n) => n.kind !== "CoreAccount") : [];
  const kinds = [...new Set(nodes.map((n) => n.kind))]
    .map((k) => ({ kind: k, count: nodes.filter((n) => n.kind === k).length }))
    .sort((a, b) => b.count - a.count);
  const shown = kind ? nodes.filter((n) => n.kind === kind) : nodes;

  return (
    <div className="mt-2 rounded-xl border bg-input shadow-card">
      <div className="flex items-center gap-2 border-b px-2 py-2">
        <Button variant="ghost" size="xs" shape="square" aria-label="Back to top results" onPress={onBack}>
          <ChevronLeftIcon className="size-4" />
        </Button>
        <span className="min-w-0 truncate font-medium text-sm">
          {all.status === "success" ? (
            <span className="tabular-nums">
              All {nodes.length} results for “{query.trim()}”
            </span>
          ) : (
            "Loading all results…"
          )}
        </span>
        <span className="ml-auto flex shrink-0 items-center gap-1 text-subtle text-xs">
          <Kbd keys="escape" className="bg-surface" /> back
        </span>
      </div>

      {kinds.length > 1 && (
        <div className="flex flex-wrap gap-1.5 border-b px-3 py-2" role="group" aria-label="Filter by kind">
          <KindChip label="All" count={nodes.length} isActive={kind === null} onPress={() => setKind(null)} />
          {kinds.map((k) => (
            <KindChip
              key={k.kind}
              label={KINDS[k.kind].plural}
              count={k.count}
              isActive={kind === k.kind}
              onPress={() => setKind(kind === k.kind ? null : k.kind)}
            />
          ))}
        </div>
      )}

      <Command.List className="max-h-[60vh] overflow-y-auto p-2">
        {all.status === "loading" &&
          Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="flex h-9 items-center gap-3 px-2" aria-hidden="true">
              <Skeleton className="size-4 rounded-sm" />
              <Skeleton className="h-3" style={{ width: `${30 + ((i * 17) % 30)}%` }} />
              <Skeleton className="ml-auto h-3 w-16" />
            </div>
          ))}
        {all.status === "error" && (
          <div role="alert" className="flex flex-col items-center gap-2 py-8 text-center">
            <p className="font-medium text-sm">The search failed</p>
            <Button size="xs" variant="outline" onPress={all.retry}>
              Try again
            </Button>
          </div>
        )}
        {all.status === "success" && nodes.length === 0 && (
          <p className="py-8 text-center text-sm text-subtle">No object matches “{query.trim()}”.</p>
        )}
        {shown.map((node) => (
          <CompactRow key={node.id} node={node} />
        ))}
      </Command.List>
    </div>
  );
}

function KindChip({
  label,
  count,
  isActive,
  onPress,
}: {
  label: string;
  count: number;
  isActive: boolean;
  onPress: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onPress}
      className={classNames(
        "inline-flex h-7 items-center gap-1.5 rounded-lg border px-2.5 text-xs outline-hidden",
        "transition-[background-color,border-color,color] duration-150 ease-out focus-visible:ring-2 focus-visible:ring-ring",
        isActive
          ? "border-custom-blue-700/30 bg-custom-blue-700/10 text-custom-blue-700 dark:text-custom-blue-300"
          : "bg-content text-foreground hover:bg-highlight"
      )}
    >
      {label}
      <span className={classNames("tabular-nums", isActive ? "opacity-80" : "text-subtle")}>{count}</span>
    </button>
  );
}

function CompactRow({ node }: { node: ProtoNode }) {
  const { query, caseSensitive, openNode } = useProto();
  const state = useRowDetails(node);
  const meta = KINDS[node.kind];

  if (state === "error") return null;
  if (state === "loading") {
    return (
      <Command.Item disabled className="flex h-9 items-center gap-3 px-2">
        <Skeleton className="size-4 rounded-sm" />
        <Skeleton className="h-3 w-48" />
        <Skeleton className="ml-auto h-3 w-16" />
      </Command.Item>
    );
  }

  const context = contextOf(node);
  return (
    <CommandItem value={node.id} onSelect={() => openNode(node)} className="h-9 gap-3">
      <Icon icon={meta.icon} aria-hidden="true" className="shrink-0 text-accent text-base" />
      <span className="truncate font-semibold text-accent">{node.label}</span>
      {isExact(node, query, caseSensitive) && <ExactMatchBadge />}
      {context && <span className="min-w-0 truncate text-subtle text-xs">{context}</span>}
      <span className="ml-auto shrink-0 text-subtle text-xs">{meta.label}</span>
    </CommandItem>
  );
}
