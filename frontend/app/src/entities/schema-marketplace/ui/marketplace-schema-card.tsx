import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";
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
  const alreadyInstalled = schema.already_installed;
  const isDisabled = disabled || alreadyInstalled;

  const handleClick = () => {
    if (isDisabled) return;
    onSelect?.(schema);
  };

  return (
    <Card
      className={classNames(
        "flex cursor-pointer flex-col gap-2 transition-colors",
        selected && "border-custom-blue-700",
        isDisabled && "cursor-not-allowed opacity-60"
      )}
      onClick={handleClick}
      aria-pressed={selected}
      aria-disabled={isDisabled}
      role="button"
      tabIndex={isDisabled ? -1 : 0}
      onKeyDown={(event) => {
        if (isDisabled) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.(schema);
        }
      }}
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon icon="mdi:file-code" className="shrink-0" />
          <span className="truncate font-semibold">{schema.display_name || schema.name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {schema.latest_version && (
            <Badge variant="gray-outline">v{schema.latest_version.semver}</Badge>
          )}
          {alreadyInstalled && <Badge variant="green">Installed</Badge>}
        </div>
      </header>

      <p className="line-clamp-2 text-gray-500 text-sm">
        {schema.description || (
          <span className="italic">No description provided.</span>
        )}
      </p>

      <footer className="flex flex-wrap items-center gap-1.5 pt-1 text-xs">
        <span className="text-gray-500">{schema.namespace}</span>
        {schema.tags.slice(0, 4).map((tag) => (
          <Badge key={tag.id ?? tag.name} variant="lightgray-outline">
            {tag.name}
          </Badge>
        ))}
      </footer>
    </Card>
  );
}
