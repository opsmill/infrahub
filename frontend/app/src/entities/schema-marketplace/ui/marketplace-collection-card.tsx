import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import type { MarketplaceCollectionSummary } from "@/entities/schema-marketplace/types";

interface MarketplaceCollectionCardProps {
  collection: MarketplaceCollectionSummary;
  selected?: boolean;
  disabled?: boolean;
  onSelect?: (collection: MarketplaceCollectionSummary) => void;
  onViewDetails?: (collection: MarketplaceCollectionSummary) => void;
}

export function MarketplaceCollectionCard({
  collection,
  selected,
  disabled,
  onSelect,
  onViewDetails,
}: MarketplaceCollectionCardProps) {
  const title = collection.display_name || collection.name;

  return (
    // Wrapper div because the card has two sibling buttons: a primary
    // select/deselect button covering the body and an overlay details button.
    // Nested <button> is invalid HTML.
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        aria-pressed={selected}
        onClick={() => onSelect?.(collection)}
        className={classNames(
          "flex min-h-[8.5rem] w-full flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3 text-left transition-colors",
          "hover:border-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-custom-blue-700",
          "disabled:cursor-not-allowed disabled:opacity-60",
          selected && "border-custom-blue-700"
        )}
      >
        <header className="flex w-full items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Icon icon="mdi:package-variant-closed" className="shrink-0" />
            <span className="truncate font-semibold">{title}</span>
          </div>
          {/* pr-8 reserves space for the overlay details button at top-right */}
          <div className="flex shrink-0 items-center gap-1 pr-8">
            <Badge variant="gray-outline">{collection.schema_count} schemas</Badge>
          </div>
        </header>

        <p className="line-clamp-2 flex-1 text-gray-500 text-sm">
          {collection.description || <span className="italic">No description provided.</span>}
        </p>

        <footer className="flex w-full items-center gap-1.5 pt-1 text-xs">
          <span className="truncate text-gray-500">{collection.namespace}</span>
        </footer>
      </button>

      {onViewDetails && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute top-2 right-2"
          aria-label="View collection details"
          onClick={() => onViewDetails(collection)}
        >
          <Icon icon="mdi:eye-outline" />
        </Button>
      )}
    </div>
  );
}
