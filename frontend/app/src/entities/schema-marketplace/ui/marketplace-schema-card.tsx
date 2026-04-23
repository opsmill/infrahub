import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import type { MarketplaceSchemaSummary } from "@/entities/schema-marketplace/types";

interface MarketplaceSchemaCardProps {
  schema: MarketplaceSchemaSummary;
  selected?: boolean;
  disabled?: boolean;
  onSelect?: (schema: MarketplaceSchemaSummary) => void;
}

export function MarketplaceSchemaCard({
  schema,
  selected,
  disabled,
  onSelect,
}: MarketplaceSchemaCardProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={selected}
      onClick={() => onSelect?.(schema)}
      className={classNames(
        "flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-3 text-left transition-colors",
        "hover:border-gray-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-custom-blue-700",
        "disabled:cursor-not-allowed disabled:opacity-60",
        selected && "border-custom-blue-700"
      )}
    >
      <header className="flex w-full items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon icon="mdi:file-code" className="shrink-0" />
          <span className="truncate font-semibold">{schema.display_name || schema.name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {schema.latest_version && (
            <Badge variant="gray-outline">v{schema.latest_version.semver}</Badge>
          )}
        </div>
      </header>

      <p className="line-clamp-2 text-gray-500 text-sm">
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
  );
}
