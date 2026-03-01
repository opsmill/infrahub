import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

import {
  fetchMarketplaceCollections,
  fetchMarketplaceSchemas,
  fetchMarketplaceTags,
} from "@/entities/marketplace/api/marketplace.queries";
import type {
  MarketplaceCollection,
  MarketplaceCollectionsListResponse,
  MarketplaceSchema,
  MarketplaceTagCount,
} from "@/entities/marketplace/types";
import { MarketplaceCollectionCard } from "@/entities/marketplace/ui/marketplace-collection-card";
import { MarketplaceSchemaCard } from "@/entities/marketplace/ui/marketplace-schema-card";

type Tab = "schemas" | "collections";

interface MarketplaceBrowserProps {
  selectedSchemaRefs: Set<string>;
  onSelectionChange: (selectedSchemaRefs: Set<string>) => void;
  selectedCollectionRefs: Set<string>;
  onCollectionSelectionChange: (selectedCollectionRefs: Set<string>) => void;
}

export function MarketplaceBrowser({
  selectedSchemaRefs,
  onSelectionChange,
  selectedCollectionRefs,
  onCollectionSelectionChange,
}: MarketplaceBrowserProps) {
  const [activeTab, setActiveTab] = useState<Tab>("schemas");
  const [schemas, setSchemas] = useState<MarketplaceSchema[]>([]);
  const [collections, setCollections] = useState<MarketplaceCollection[]>([]);
  const [tags, setTags] = useState<MarketplaceTagCount[]>([]);
  const [search, setSearch] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (activeTab === "schemas") {
        const [schemasResult, tagsResult] = await Promise.all([
          fetchMarketplaceSchemas(search || undefined, selectedTag || undefined),
          tags.length === 0 ? fetchMarketplaceTags() : Promise.resolve(tags),
        ]);
        if ((schemasResult as { errors?: unknown[] }).errors) {
          throw new Error("Failed to load schemas");
        }
        setSchemas(schemasResult.schemas ?? []);
        if (tags.length === 0) {
          setTags(tagsResult as MarketplaceTagCount[]);
        }
      } else {
        const collectionsResult =
          (await fetchMarketplaceCollections()) as MarketplaceCollectionsListResponse &
            Record<string, unknown>;
        if (collectionsResult.errors) {
          throw new Error("Failed to load collections");
        }
        setCollections(collectionsResult.collections ?? []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load marketplace data");
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, search, selectedTag]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSchemaToggle = (versionId: string) => {
    const next = new Set(selectedSchemaRefs);
    if (next.has(versionId)) {
      next.delete(versionId);
    } else {
      next.add(versionId);
    }
    onSelectionChange(next);
  };

  const handleCollectionToggle = (collectionId: string) => {
    const next = new Set(selectedCollectionRefs);
    if (next.has(collectionId)) {
      next.delete(collectionId);
    } else {
      next.add(collectionId);
    }
    onCollectionSelectionChange(next);
  };

  const totalSelected = selectedSchemaRefs.size + selectedCollectionRefs.size;

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-12 text-center">
        <p className="text-gray-600 text-sm">Marketplace is currently unavailable</p>
        <p className="text-gray-400 text-xs">{error}</p>
        <Button variant="outline" onClick={loadData}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Tabs */}
      <div className="flex gap-1 border-gray-200 border-b">
        <button
          type="button"
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            activeTab === "schemas"
              ? "border-custom-blue-700 border-b-2 text-custom-blue-700"
              : "text-gray-500 hover:text-gray-700"
          }`}
          onClick={() => setActiveTab("schemas")}
        >
          Schemas
          {selectedSchemaRefs.size > 0 && (
            <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-custom-blue-700 px-1.5 text-white text-xs">
              {selectedSchemaRefs.size}
            </span>
          )}
        </button>
        <button
          type="button"
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            activeTab === "collections"
              ? "border-custom-blue-700 border-b-2 text-custom-blue-700"
              : "text-gray-500 hover:text-gray-700"
          }`}
          onClick={() => setActiveTab("collections")}
        >
          Collections
          {selectedCollectionRefs.size > 0 && (
            <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-custom-blue-700 px-1.5 text-white text-xs">
              {selectedCollectionRefs.size}
            </span>
          )}
        </button>
      </div>

      {/* Search and filter (schemas only) */}
      {activeTab === "schemas" && (
        <>
          <div className="flex gap-2">
            <Input
              placeholder="Search schemas..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1"
            />
          </div>

          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <Badge
                variant={selectedTag === null ? "blue" : "gray"}
                className="cursor-pointer"
                onClick={() => setSelectedTag(null)}
              >
                All
              </Badge>
              {tags.map((tag) => (
                <Badge
                  key={tag.id}
                  variant={selectedTag === tag.name ? "blue" : "gray"}
                  className="cursor-pointer"
                  onClick={() => setSelectedTag(selectedTag === tag.name ? null : tag.name)}
                >
                  {tag.name} ({tag.count})
                </Badge>
              ))}
            </div>
          )}
        </>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-xl border border-gray-200 bg-gray-50"
            />
          ))}
        </div>
      ) : activeTab === "schemas" ? (
        schemas.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-gray-600 text-sm">No schemas available in the marketplace</p>
            <p className="mt-1 text-gray-400 text-xs">
              {search || selectedTag
                ? "Try adjusting your search or filter criteria"
                : "Check back later for new schemas"}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {schemas.map((schema) => {
              const schemaRef = `${schema.namespace}/${schema.name}`;
              return (
                <MarketplaceSchemaCard
                  key={schema.id}
                  schema={schema}
                  isSelected={selectedSchemaRefs.has(schemaRef)}
                  onToggle={() => handleSchemaToggle(schemaRef)}
                />
              );
            })}
          </div>
        )
      ) : collections.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-gray-600 text-sm">No collections available in the marketplace</p>
          <p className="mt-1 text-gray-400 text-xs">Check back later for new collections</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {collections.map((collection) => {
            const collectionRef = `${collection.namespace}/${collection.name}`;
            return (
              <MarketplaceCollectionCard
                key={collection.id}
                collection={collection}
                isSelected={selectedCollectionRefs.has(collectionRef)}
                onToggle={() => handleCollectionToggle(collectionRef)}
              />
            );
          })}
        </div>
      )}

      {totalSelected > 0 && (
        <div className="rounded-lg bg-custom-blue-700/5 px-3 py-2 text-custom-blue-700 text-sm">
          {totalSelected} item{totalSelected !== 1 ? "s" : ""} selected
          {selectedSchemaRefs.size > 0 && selectedCollectionRefs.size > 0 && (
            <span className="text-xs">
              {" "}
              ({selectedSchemaRefs.size} schema{selectedSchemaRefs.size !== 1 ? "s" : ""},{" "}
              {selectedCollectionRefs.size} collection{selectedCollectionRefs.size !== 1 ? "s" : ""}
              )
            </span>
          )}
        </div>
      )}
    </div>
  );
}
