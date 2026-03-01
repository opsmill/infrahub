import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";

import type { MarketplaceCollection } from "@/entities/marketplace/types";

interface MarketplaceCollectionCardProps {
  collection: MarketplaceCollection;
  isSelected: boolean;
  onToggle: (collectionId: string) => void;
}

export function MarketplaceCollectionCard({
  collection,
  isSelected,
  onToggle,
}: MarketplaceCollectionCardProps) {
  return (
    <Card
      className={`cursor-pointer transition-colors ${
        isSelected
          ? "border-custom-blue-700 bg-custom-blue-700/5 ring-1 ring-custom-blue-700"
          : "hover:border-gray-300"
      }`}
      onClick={() => onToggle(collection.id)}
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-medium text-gray-900 text-sm">
              {collection.display_name || collection.name}
            </h3>
            <p className="text-gray-500 text-xs">
              {collection.schema_count} schema{collection.schema_count !== 1 ? "s" : ""}
            </p>
          </div>
          {isSelected && (
            <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-custom-blue-700 text-white text-xs">
              &#10003;
            </div>
          )}
        </div>

        {collection.description && (
          <p className="line-clamp-2 text-gray-600 text-xs">{collection.description}</p>
        )}

        <div className="flex items-center gap-3 text-gray-400 text-xs">
          <span title="Downloads">&darr; {collection.download_count}</span>
          <span title="Upvotes">&uarr; {collection.upvote_count}</span>
        </div>

        {collection.items.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {collection.items.slice(0, 3).map((item) => (
              <Badge key={item.id} variant="gray" className="text-[10px]">
                {item.schema.displayName || item.schema.name}
              </Badge>
            ))}
            {collection.items.length > 3 && (
              <Badge variant="gray" className="text-[10px]">
                +{collection.items.length - 3} more
              </Badge>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
