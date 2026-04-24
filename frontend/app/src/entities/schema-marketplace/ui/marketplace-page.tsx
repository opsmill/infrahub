import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import Content from "@/shared/components/layout/content";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { classNames } from "@/shared/utils/common";

import {
  fetchMarketplaceCollections,
  fetchMarketplaceSchemas,
  fetchMarketplaceStatus,
  fetchMarketplaceTags,
} from "@/entities/schema-marketplace/api/marketplace.queries";
import { useWritableRepositories } from "@/entities/schema-marketplace/hooks/use-writable-repositories";
import { CliAlternative } from "@/entities/schema-marketplace/ui/cli-alternative";
import { InstallDrawer } from "@/entities/schema-marketplace/ui/install-drawer";
import { MarketplaceCollectionCard } from "@/entities/schema-marketplace/ui/marketplace-collection-card";
import { MarketplaceSchemaCard } from "@/entities/schema-marketplace/ui/marketplace-schema-card";
import { PrerequisiteState } from "@/entities/schema-marketplace/ui/prerequisite-state";
import { SchemaDetailModal } from "@/entities/schema-marketplace/ui/schema-detail-modal";
import type {
  MarketplaceCollectionSummary,
  MarketplaceInstallItem,
  MarketplaceSchemaSummary,
} from "@/entities/schema-marketplace/types";

type BrowseTab = "schemas" | "collections";

// Selection identity is `kind:namespace/name`, excluding semver — clicking a
// card twice must toggle the same selection even if the upstream cache
// flipped `latest_version.semver` between clicks. The version to install is
// captured on the payload (`MarketplaceInstallItem.semver`), not the key.
function keyOf(item: Pick<MarketplaceInstallItem, "kind" | "namespace" | "name">): string {
  return `${item.kind}:${item.namespace}/${item.name}`;
}

export function MarketplacePage() {
  const [tab, setTab] = useState<BrowseTab>("schemas");
  const [search, setSearch] = useState<string>("");
  // Debounce the search term so we don't fire a request on every keystroke.
  // 300 ms is the cached-list sweet spot — long enough that fast typing
  // coalesces into one request, short enough that the list feels responsive.
  const debouncedSearch = useDebounce(search, 300);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selection, setSelection] = useState<MarketplaceInstallItem[]>([]);
  const [detailSchema, setDetailSchema] = useState<MarketplaceSchemaSummary | null>(null);
  const hasActiveFilters = search.length > 0 || selectedTags.length > 0;

  const status = useQuery({
    queryKey: ["schema-marketplace", "status"],
    queryFn: fetchMarketplaceStatus,
    refetchOnWindowFocus: false,
  });

  const repos = useWritableRepositories();

  const tags = useQuery({
    queryKey: ["schema-marketplace", "tags"],
    queryFn: fetchMarketplaceTags,
    staleTime: 30_000,
  });

  // Both queries run regardless of which tab is active so the inactive tab's
  // count is available in the label ("Collections · 1"). They're already
  // cached on the backend (30s TTL) and idle otherwise; the upfront cost
  // is two cheap list calls.
  const schemas = useQuery({
    queryKey: ["schema-marketplace", "schemas", debouncedSearch, selectedTags.join(",")],
    queryFn: () =>
      fetchMarketplaceSchemas({
        search: debouncedSearch || undefined,
        tags: selectedTags.length ? selectedTags : undefined,
      }),
  });

  const collections = useQuery({
    queryKey: ["schema-marketplace", "collections", debouncedSearch, selectedTags.join(",")],
    queryFn: () =>
      fetchMarketplaceCollections({
        search: debouncedSearch || undefined,
        tags: selectedTags.length ? selectedTags : undefined,
      }),
  });

  const selectionMap = new Set(selection.map(keyOf));

  const selectSchema = (schema: MarketplaceSchemaSummary) => {
    const item: MarketplaceInstallItem = {
      kind: "schema",
      namespace: schema.namespace,
      name: schema.name,
      semver: schema.latest_version?.semver ?? null,
    };
    setSelection((prev) =>
      prev.some((p) => keyOf(p) === keyOf(item)) ? prev.filter((p) => keyOf(p) !== keyOf(item)) : [...prev, item]
    );
  };

  const selectCollection = (collection: MarketplaceCollectionSummary) => {
    const item: MarketplaceInstallItem = {
      kind: "collection",
      namespace: collection.namespace,
      name: collection.name,
      semver: null,
    };
    setSelection((prev) =>
      prev.some((p) => keyOf(p) === keyOf(item)) ? prev.filter((p) => keyOf(p) !== keyOf(item)) : [...prev, item]
    );
  };

  // Upsert: add the item if its key is new, otherwise replace in place so the
  // semver (or any future per-selection metadata) picked in the detail modal
  // overrides whatever one-click-add put there.
  const upsertSelection = (item: MarketplaceInstallItem) => {
    setSelection((prev) => {
      const idx = prev.findIndex((p) => keyOf(p) === keyOf(item));
      if (idx === -1) return [...prev, item];
      const next = prev.slice();
      next[idx] = item;
      return next;
    });
  };

  const removeSelection = (item: MarketplaceInstallItem) => {
    setSelection((prev) => prev.filter((p) => keyOf(p) !== keyOf(item)));
  };

  const showConfigError =
    !!status.data && (!status.data.url_scheme_valid || !status.data.url_configured);

  const showConnectivityError = !!status.data && !status.data.upstream_reachable;

  return (
    <Content className="flex flex-col gap-4 p-4">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-custom-blue-700/10 text-custom-blue-700">
            <Icon icon="mdi:storefront-outline" className="text-xl" />
          </span>
          <div className="flex min-w-0 flex-col">
            <h1 className="font-bold text-2xl">Schema Marketplace</h1>
            <p className="text-gray-500 text-sm">
              Browse and install ready-made schemas — to a Git repository or directly to this
              instance.
            </p>
          </div>
        </div>
      </header>

      {showConfigError && (
        <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
          <p className="mb-1 font-semibold">Marketplace is not configured correctly</p>
          <p>
            Check the <code className="font-mono">INFRAHUB_MARKETPLACE_URL</code> backend
            environment variable; it must start with <code className="font-mono">http://</code> or{" "}
            <code className="font-mono">https://</code>.
          </p>
        </div>
      )}

      {showConnectivityError && !showConfigError && (
        <div className="flex items-start justify-between gap-3 rounded-md bg-yellow-50 p-3 text-yellow-800 text-sm">
          <div>
            <p className="mb-1 font-semibold">Marketplace is unreachable</p>
            <p>
              The Infrahub backend can't reach the configured Marketplace. Listings below may be
              stale or empty. Retry or contact your administrator.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="xs"
            onClick={() => status.refetch()}
            disabled={status.isFetching}
          >
            <Icon icon="mdi:refresh" className="mr-1" />
            {status.isFetching ? "Retrying…" : "Retry"}
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-gray-200 p-0.5">
          <Button
            type="button"
            variant={tab === "schemas" ? "primary" : "ghost"}
            size="sm"
            onClick={() => setTab("schemas")}
          >
            Schemas
            {typeof schemas.data?.total_count === "number" && (
              <span className="ml-1.5 text-gray-500 text-xs">{schemas.data.total_count}</span>
            )}
          </Button>
          <Button
            type="button"
            variant={tab === "collections" ? "primary" : "ghost"}
            size="sm"
            onClick={() => setTab("collections")}
          >
            Collections
            {typeof collections.data?.total_count === "number" && (
              <span className="ml-1.5 text-gray-500 text-xs">{collections.data.total_count}</span>
            )}
          </Button>
        </div>
        <div className="relative flex-1">
          <Icon
            icon="mdi:magnify"
            className="-translate-y-1/2 absolute top-1/2 left-2.5 text-gray-400"
          />
          <input
            className="w-full rounded-md border border-gray-200 p-2 pl-8 text-sm"
            type="search"
            placeholder="Search the Marketplace…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {search.length > 0 && search !== debouncedSearch && (
            <Icon
              icon="mdi:loading"
              className="-translate-y-1/2 absolute top-1/2 right-2.5 animate-spin text-gray-400"
              aria-label="Searching"
            />
          )}
        </div>
        {hasActiveFilters && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setSearch("");
              setSelectedTags([]);
            }}
          >
            <Icon icon="mdi:filter-off-outline" className="mr-1" /> Clear filters
          </Button>
        )}
      </div>

      {tags.data && tags.data.tags.length > 0 && (
        <TagCloud
          tags={tags.data.tags}
          selectedTags={selectedTags}
          onToggle={(tagName) =>
            setSelectedTags((prev) =>
              prev.includes(tagName) ? prev.filter((t) => t !== tagName) : [...prev, tagName]
            )
          }
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <section className="flex flex-col gap-3">
          {tab === "schemas" && (
            <SchemaList
              isPending={schemas.isPending}
              error={schemas.error}
              items={schemas.data?.items ?? []}
              onSelect={selectSchema}
              onViewDetails={setDetailSchema}
              selectionMap={selectionMap}
            />
          )}
          {tab === "collections" && (
            <CollectionList
              isPending={collections.isPending}
              error={collections.error}
              items={collections.data?.items ?? []}
              onSelect={selectCollection}
              selectionMap={selectionMap}
            />
          )}
        </section>

        <aside className="flex flex-col gap-3">
          <InstallDrawer
            selection={selection}
            writableRepositories={repos.writableRepositories}
            onRemove={removeSelection}
            onClearSelection={() => setSelection([])}
          />
          {!repos.isPending && repos.writableRepositories.length === 0 && (
            <PrerequisiteState hasAnyRepository={repos.hasAnyRepository} />
          )}
          {selection.length > 0 && (
            <Card className="flex flex-col gap-2">
              <header className="flex items-center gap-2 font-semibold text-sm">
                <Icon icon="mdi:console" /> CLI alternative
              </header>
              <p className="text-gray-500 text-xs">
                Prefer to apply directly from your machine? Use the commands below.
              </p>
              <CliAlternative selection={selection} />
            </Card>
          )}
        </aside>
      </div>

      <SchemaDetailModal
        schema={detailSchema}
        currentSelection={selection}
        onApply={upsertSelection}
        onRemove={removeSelection}
        onClose={() => setDetailSchema(null)}
      />
    </Content>
  );
}

interface SchemaListProps {
  isPending: boolean;
  error: Error | null;
  items: MarketplaceSchemaSummary[];
  onSelect: (schema: MarketplaceSchemaSummary) => void;
  onViewDetails: (schema: MarketplaceSchemaSummary) => void;
  selectionMap: Set<string>;
}

function SchemaList({
  isPending,
  error,
  items,
  onSelect,
  onViewDetails,
  selectionMap,
}: SchemaListProps) {
  if (isPending) return <CardGridSkeleton />;
  if (error) return <ErrorScreen message={error.message} />;
  if (!items.length) {
    return <EmptyResults label="schemas" />;
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((schema) => {
        const selected = selectionMap.has(keyOf({ kind: "schema", namespace: schema.namespace, name: schema.name }));
        return (
          <MarketplaceSchemaCard
            key={schema.id}
            schema={schema}
            selected={selected}
            onSelect={onSelect}
            onViewDetails={onViewDetails}
          />
        );
      })}
    </div>
  );
}

interface CollectionListProps {
  isPending: boolean;
  error: Error | null;
  items: MarketplaceCollectionSummary[];
  onSelect: (collection: MarketplaceCollectionSummary) => void;
  selectionMap: Set<string>;
}

function CollectionList({ isPending, error, items, onSelect, selectionMap }: CollectionListProps) {
  if (isPending) return <CardGridSkeleton />;
  if (error) return <ErrorScreen message={error.message} />;
  if (!items.length) {
    return <EmptyResults label="collections" />;
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((collection) => {
        const selected = selectionMap.has(
          keyOf({ kind: "collection", namespace: collection.namespace, name: collection.name })
        );
        return (
          <MarketplaceCollectionCard
            key={collection.id}
            collection={collection}
            selected={selected}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2" aria-busy aria-label="Loading">
      {Array.from({ length: 6 }).map((_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton set
        <Card key={i} className="flex flex-col gap-2" aria-hidden>
          <div className="flex items-center justify-between gap-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-10" />
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <div className="flex gap-1 pt-1">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-3 w-16" />
          </div>
        </Card>
      ))}
    </div>
  );
}

function EmptyResults({ label }: { label: string }) {
  return (
    <Card className="flex flex-col items-center gap-2 py-10 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-gray-100 text-gray-400">
        <Icon icon="mdi:magnify" className="text-xl" />
      </span>
      <p className="font-medium text-gray-700 text-sm">No {label} match your filters</p>
      <p className="max-w-xs text-gray-500 text-xs">
        Try a different keyword, clear active tags, or open the CLI alternative below to install
        something you already know the name of.
      </p>
    </Card>
  );
}

interface TagCloudProps {
  tags: { id: string | null; name: string; count: number }[];
  selectedTags: string[];
  onToggle: (tagName: string) => void;
}

const TAG_COLLAPSE_THRESHOLD = 12;

function TagCloud({ tags, selectedTags, onToggle }: TagCloudProps) {
  const [expanded, setExpanded] = useState(false);
  // Always keep selected tags visible so the user can still deselect them when
  // the list is collapsed. Then fill the remaining slots with the highest-count
  // unselected tags until we hit the collapse threshold.
  const selectedSet = new Set(selectedTags);
  const selectedEntries = tags.filter((t) => selectedSet.has(t.name));
  const unselectedEntries = tags
    .filter((t) => !selectedSet.has(t.name))
    .sort((a, b) => b.count - a.count);
  const needsCollapse = tags.length > TAG_COLLAPSE_THRESHOLD;
  const visible =
    expanded || !needsCollapse
      ? tags
      : [
          ...selectedEntries,
          ...unselectedEntries.slice(0, Math.max(0, TAG_COLLAPSE_THRESHOLD - selectedEntries.length)),
        ];
  const hiddenCount = tags.length - visible.length;

  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="mr-1 text-gray-500 text-xs">Tags:</span>
      {visible.map((tag) => {
        const active = selectedSet.has(tag.name);
        return (
          <button
            key={tag.id ?? tag.name}
            type="button"
            onClick={() => onToggle(tag.name)}
            className={classNames(
              "cursor-pointer rounded-md border px-1.5 py-0.5 text-xs",
              active
                ? "border-custom-blue-700 bg-custom-blue-700/10 text-custom-blue-700"
                : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"
            )}
            aria-pressed={active}
          >
            {tag.name} <Badge variant="lightgray-outline">{tag.count}</Badge>
          </button>
        );
      })}
      {needsCollapse && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="rounded-md px-1.5 py-0.5 text-custom-blue-700 text-xs hover:underline"
        >
          {expanded ? "Show fewer" : `+${hiddenCount} more`}
        </button>
      )}
    </div>
  );
}
