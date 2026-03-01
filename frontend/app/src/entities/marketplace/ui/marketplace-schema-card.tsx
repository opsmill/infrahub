import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";

import type { MarketplaceSchema } from "@/entities/marketplace/types";

interface MarketplaceSchemaCardProps {
  schema: MarketplaceSchema;
  isSelected: boolean;
  onToggle: (schemaId: string) => void;
}

export function MarketplaceSchemaCard({
  schema,
  isSelected,
  onToggle,
}: MarketplaceSchemaCardProps) {
  const latestVersion = schema.versions.length > 0 ? schema.versions[0] : null;

  return (
    <Card
      className={`cursor-pointer transition-colors ${
        isSelected
          ? "border-custom-blue-700 bg-custom-blue-700/5 ring-1 ring-custom-blue-700"
          : "hover:border-gray-300"
      }`}
      onClick={() => onToggle(latestVersion?.id ?? schema.id)}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-medium text-gray-900 text-sm">
              {schema.display_name || schema.name}
            </h3>
            <p className="text-gray-500 text-xs">{schema.namespace}</p>
          </div>
          {isSelected && (
            <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-custom-blue-700 text-white text-xs">
              &#10003;
            </div>
          )}
        </div>

        {schema.description && (
          <p className="line-clamp-2 text-gray-600 text-xs">{schema.description}</p>
        )}

        <div className="flex items-center gap-3 text-gray-400 text-xs">
          <span title="Downloads">&darr; {schema.download_count}</span>
          <span title="Upvotes">&uarr; {schema.upvote_count}</span>
          {latestVersion && <span>v{latestVersion.semver}</span>}
        </div>

        {schema.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {schema.tags.slice(0, 3).map((tag) => (
              <Badge key={tag.id} variant="gray" className="text-[10px]">
                {tag.name}
              </Badge>
            ))}
            {schema.tags.length > 3 && (
              <Badge variant="gray" className="text-[10px]">
                +{schema.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
