import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";

import { fetchMarketplaceCollection } from "@/entities/schema-marketplace/api/marketplace.queries";
import type {
  MarketplaceCollectionSummary,
  MarketplaceInstallItem,
} from "@/entities/schema-marketplace/types";

interface CollectionDetailModalProps {
  collection: MarketplaceCollectionSummary | null;
  currentSelection: MarketplaceInstallItem[];
  onApply: (item: MarketplaceInstallItem) => void;
  onRemove: (item: MarketplaceInstallItem) => void;
  onClose: () => void;
}

function collectionKey(namespace: string, name: string): string {
  return `collection:${namespace}/${name}`;
}

export function CollectionDetailModal({
  collection,
  currentSelection,
  onApply,
  onRemove,
  onClose,
}: CollectionDetailModalProps) {
  const isOpen = collection !== null;

  const detail = useQuery({
    queryKey: ["schema-marketplace", "collection", collection?.namespace, collection?.name],
    queryFn: () => fetchMarketplaceCollection(collection!.namespace, collection!.name),
    enabled: isOpen,
  });

  const existing =
    collection &&
    (currentSelection.find(
      (s) =>
        `${s.kind}:${s.namespace}/${s.name}` === collectionKey(collection.namespace, collection.name)
    ) ?? null);

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      className="w-full max-w-3xl"
      aria-label={
        collection ? `${collection.display_name || collection.name} details` : "Collection details"
      }
    >
      {({ close }) => {
        if (!collection) return null;
        const title = collection.display_name || collection.name;
        const items = detail.data?.items ?? [];

        const apply = () => {
          onApply({
            kind: "collection",
            namespace: collection.namespace,
            name: collection.name,
            semver: null,
          });
          close();
        };

        const remove = () => {
          if (!existing) return;
          onRemove(existing);
          close();
        };

        return (
          <div className="flex h-full min-h-0 flex-col gap-3 p-4">
            <header className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <Heading slot="title" className="flex items-center gap-2 font-semibold text-lg">
                  <Icon icon="mdi:package-variant-closed" />
                  <span className="truncate">{title}</span>
                </Heading>
                <p className="font-mono text-gray-500 text-xs">
                  {collection.namespace}/{collection.name}
                </p>
              </div>
              <Button variant="ghost" size="icon" aria-label="Close" onClick={() => close()}>
                <Icon icon="mdi:close" />
              </Button>
            </header>

            {collection.description && (
              <p className="text-gray-600 text-sm">{collection.description}</p>
            )}

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto">
              {detail.data?.readme && (
                <section>
                  <h3 className="mb-1 font-semibold text-sm">Readme</h3>
                  <div className="rounded-md border border-gray-200 p-3">
                    <MarkdownRender markdownText={detail.data.readme} />
                  </div>
                </section>
              )}

              <section className="flex min-h-0 flex-col">
                <h3 className="mb-1 flex items-center gap-2 font-semibold text-sm">
                  Schemas in this collection
                  <Badge variant="gray">{items.length || collection.schema_count}</Badge>
                </h3>
                {detail.isPending && <LoadingIndicator />}
                {detail.error && (
                  <div className="rounded-md bg-red-50 p-3 text-red-700 text-sm">
                    Failed to load collection detail: {(detail.error as Error).message}
                  </div>
                )}
                {!detail.isPending && items.length === 0 && (
                  <p className="rounded-md border border-gray-200 border-dashed p-3 text-gray-500 text-xs">
                    This collection doesn't list its schemas. Install the collection to pull them all
                    from the Marketplace.
                  </p>
                )}
                {items.length > 0 && (
                  <ul className="flex flex-col gap-1">
                    {[...items]
                      .sort((a, b) => a.order - b.order)
                      .map((item) => (
                        <li
                          key={`${item.namespace}/${item.name}@${item.semver}`}
                          className="flex items-center justify-between gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm"
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            <Icon icon="mdi:file-code" className="shrink-0 text-gray-500" />
                            <span className="truncate font-mono text-xs">
                              {item.namespace}/{item.name}
                            </span>
                          </div>
                          <Badge variant="lightgray-outline" className="shrink-0">
                            v{item.semver}
                          </Badge>
                        </li>
                      ))}
                  </ul>
                )}
              </section>
            </div>

            <footer className="flex flex-wrap items-center justify-end gap-2 border-gray-200 border-t pt-3">
              {existing ? (
                <Button variant="outline" onClick={remove}>
                  <Icon icon="mdi:close" className="mr-1" /> Remove from selection
                </Button>
              ) : (
                <Button variant="primary" onClick={apply}>
                  <Icon icon="mdi:plus" className="mr-1" /> Add to install
                </Button>
              )}
            </footer>
          </div>
        );
      }}
    </Modal>
  );
}
