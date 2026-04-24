import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import type { MarketplaceSchemaSummary } from "@/entities/schema-marketplace/types";

interface MarketplaceSchemaCardProps {
  schema: MarketplaceSchemaSummary;
  selected?: boolean;
  disabled?: boolean;
  onSelect?: (schema: MarketplaceSchemaSummary) => void;
  onViewDetails?: (schema: MarketplaceSchemaSummary) => void;
}

export function MarketplaceSchemaCard({
  schema,
  selected,
  disabled,
  onSelect,
  onViewDetails,
}: MarketplaceSchemaCardProps) {
  const title = schema.display_name || schema.name;

  return (
    // Wrapper is a div because the card has two sibling actions -- a primary
    // "toggle selection" button covering the body, plus an overlay "view
    // details" icon-button. Nested `<button>` is invalid HTML, hence the split.
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        aria-pressed={selected}
        onClick={() => onSelect?.(schema)}
        className={classNames(
          "flex min-h-[8.5rem] w-full flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3 text-left transition-colors",
          "hover:border-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-custom-blue-700",
          "disabled:cursor-not-allowed disabled:opacity-60",
          selected && "border-custom-blue-700"
        )}
      >
        <header className="flex w-full items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Icon icon="mdi:file-code" className="shrink-0" />
            <span className="truncate font-semibold">{title}</span>
          </div>
          {/* pr-8 reserves space for the overlay details button at top-right */}
          <div className="flex shrink-0 items-center gap-1 pr-8">
            {schema.latest_version && (
              <Badge variant="gray-outline">v{schema.latest_version.semver}</Badge>
            )}
          </div>
        </header>

        <p className="line-clamp-2 flex-1 text-gray-500 text-sm">
          {schema.description || <span className="italic">No description provided.</span>}
        </p>

        <footer className="flex w-full flex-wrap items-center gap-1.5 pt-1 text-xs">
          <span className="text-gray-500">{schema.namespace}</span>
          {schema.tags.slice(0, 4).map((tag) => (
            <Badge key={tag.id ?? tag.name} variant="lightgray-outline">
              {tag.name}
            </Badge>
          ))}
        </footer>
      </button>

      {onViewDetails && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute top-2 right-2"
          aria-label="View schema details"
          onClick={() => onViewDetails(schema)}
        >
          <Icon icon="mdi:eye-outline" />
        </Button>
      )}
    </div>
  );
}
