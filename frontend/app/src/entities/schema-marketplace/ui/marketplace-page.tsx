import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { useMemo, useState } from "react";

import Content from "@/shared/components/layout/content";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
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
import type {
  MarketplaceCollectionSummary,
  MarketplaceInstallItem,
  MarketplaceSchemaSummary,
} from "@/entities/schema-marketplace/types";

type BrowseTab = "schemas" | "collections";

function keyOf(item: MarketplaceInstallItem): string {
  return `${item.kind}:${item.namespace}/${item.name}@${item.semver ?? "latest"}`;
}

export function MarketplacePage() {
  const [tab, setTab] = useState<BrowseTab>("schemas");
  const [search, setSearch] = useState<string>("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selection, setSelection] = useState<MarketplaceInstallItem[]>([]);

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

  const schemas = useQuery({
    queryKey: ["schema-marketplace", "schemas", search, selectedTags.join(",")],
    queryFn: () =>
      fetchMarketplaceSchemas({
        search: search || undefined,
        tags: selectedTags.length ? selectedTags : undefined,
      }),
    enabled: tab === "schemas",
  });

  const collections = useQuery({
    queryKey: ["schema-marketplace", "collections", search, selectedTags.join(",")],
    queryFn: () =>
      fetchMarketplaceCollections({
        search: search || undefined,
        tags: selectedTags.length ? selectedTags : undefined,
      }),
    enabled: tab === "collections",
  });

  const selectionMap = useMemo(() => new Set(selection.map(keyOf)), [selection]);

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

  const showPrerequisite =
    !repos.isPending && (repos.writableRepositories.length === 0 || !repos.hasWritePermission);

  const showConfigError =
    !!status.data && (!status.data.url_scheme_valid || !status.data.url_configured);

  const showConnectivityError = !!status.data && !status.data.upstream_reachable;

  return (
    <Content className="flex flex-col gap-4 p-4">
      <header className="flex items-center justify-between gap-2">
        <div>
          <h1 className="font-bold text-2xl">Schema Marketplace</h1>
          <p className="text-gray-500 text-sm">
            Install schemas from the Infrahub Marketplace into a Git repository or via{" "}
            <code className="font-mono">infrahubctl</code>.
          </p>
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
        <div className="rounded-md bg-yellow-50 p-3 text-yellow-800 text-sm">
          <p className="mb-1 font-semibold">Marketplace is unreachable</p>
          <p>
            The Infrahub backend can't reach the configured Marketplace. Listings below may be
            stale or empty. Retry or contact your administrator.
          </p>
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
          </Button>
          <Button
            type="button"
            variant={tab === "collections" ? "primary" : "ghost"}
            size="sm"
            onClick={() => setTab("collections")}
          >
            Collections
          </Button>
        </div>
        <input
          className="flex-1 rounded-md border border-gray-200 p-2 text-sm"
          type="search"
          placeholder="Search the Marketplace…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      {tags.data && tags.data.tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="mr-1 text-gray-500 text-xs">Tags:</span>
          {tags.data.tags.map((tag) => {
            const active = selectedTags.includes(tag.name);
            return (
              <button
                key={tag.id ?? tag.name}
                type="button"
                onClick={() =>
                  setSelectedTags((prev) =>
                    active ? prev.filter((t) => t !== tag.name) : [...prev, tag.name]
                  )
                }
                className={classNames(
                  "cursor-pointer rounded-md border px-1.5 py-0.5 text-xs",
                  active
                    ? "border-custom-blue-700 bg-custom-blue-700/10 text-custom-blue-700"
                    : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"
                )}
              >
                {tag.name} <Badge variant="lightgray-outline">{tag.count}</Badge>
              </button>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <section className="flex flex-col gap-3">
          {tab === "schemas" && (
            <SchemaList
              isPending={schemas.isPending}
              error={schemas.error}
              items={schemas.data?.items ?? []}
              onSelect={selectSchema}
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
          {showPrerequisite ? (
            <>
              <PrerequisiteState
                hasAnyRepository={repos.hasAnyRepository}
                hasWritePermission={repos.hasWritePermission}
              />
              <CliAlternative selection={selection} />
            </>
          ) : (
            <>
              <InstallDrawer
                selection={selection}
                writableRepositories={repos.writableRepositories}
                onRemove={(item) =>
                  setSelection((prev) => prev.filter((p) => keyOf(p) !== keyOf(item)))
                }
              />
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
            </>
          )}
        </aside>
      </div>
    </Content>
  );
}

interface SchemaListProps {
  isPending: boolean;
  error: Error | null;
  items: MarketplaceSchemaSummary[];
  onSelect: (schema: MarketplaceSchemaSummary) => void;
  selectionMap: Set<string>;
}

function SchemaList({ isPending, error, items, onSelect, selectionMap }: SchemaListProps) {
  if (isPending) return <LoadingIndicator />;
  if (error) return <ErrorScreen message={error.message} />;
  if (!items.length) {
    return (
      <Card>
        <p className="text-gray-500 text-sm">No schemas match your filters.</p>
      </Card>
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((schema) => {
        const selected = selectionMap.has(`schema:${schema.namespace}/${schema.name}@${schema.latest_version?.semver ?? "latest"}`);
        return (
          <MarketplaceSchemaCard
            key={schema.id}
            schema={schema}
            selected={selected}
            onSelect={onSelect}
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
  if (isPending) return <LoadingIndicator />;
  if (error) return <ErrorScreen message={error.message} />;
  if (!items.length) {
    return (
      <Card>
        <p className="text-gray-500 text-sm">No collections match your filters.</p>
      </Card>
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((collection) => {
        const selected = selectionMap.has(
          `collection:${collection.namespace}/${collection.name}@latest`
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
