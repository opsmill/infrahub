import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import {
  fetchMarketplaceCollections,
  fetchMarketplaceSchemas,
} from "@/entities/schema-marketplace/api/marketplace.queries";
import { useHasUserSchemas } from "@/entities/schema-marketplace/hooks/use-has-user-schemas";

interface SchemaMarketplaceWidgetProps {
  className?: string;
}

// The tile pulls a live count of Marketplace schemas + collections so it has
// something specific to show even when the user has nothing installed yet.
// Both queries hit the already-cached proxy endpoints (30 s TTL) and ask for
// `limit=1` because we only need `total_count`.
function useMarketplaceCounts() {
  const schemasCount = useQuery({
    queryKey: ["schema-marketplace", "widget-count", "schemas"],
    queryFn: () => fetchMarketplaceSchemas({ limit: 1 }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const collectionsCount = useQuery({
    queryKey: ["schema-marketplace", "widget-count", "collections"],
    queryFn: () => fetchMarketplaceCollections({ limit: 1 }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
  return {
    schemas: schemasCount.data?.total_count ?? null,
    collections: collectionsCount.data?.total_count ?? null,
    isPending: schemasCount.isPending || collectionsCount.isPending,
    isError: !!schemasCount.error || !!collectionsCount.error,
  };
}

export function SchemaMarketplaceWidget({ className }: SchemaMarketplaceWidgetProps) {
  const hasUserSchemas = useHasUserSchemas();
  const counts = useMarketplaceCounts();
  const isOnboarding = !hasUserSchemas;

  return (
    <Card
      className={classNames(
        "relative flex flex-col overflow-hidden p-0",
        // The onboarding variant gets an accent gradient and a coloured
        // border — "this is where you should go next" rather than "this is
        // one more widget among many".
        isOnboarding
          ? "border-custom-blue-700/40 bg-gradient-to-br from-custom-blue-700/5 via-white to-purple-500/5"
          : "bg-white",
        className
      )}
    >
      <header className="flex items-center justify-between border-gray-200 border-b p-3 font-bold">
        <div className="flex items-center gap-2">
          <Icon
            icon="mdi:storefront-outline"
            className={classNames("text-lg", isOnboarding ? "text-custom-blue-700" : "text-gray-700")}
          />
          <span>Schema Marketplace</span>
          {counts.schemas !== null && (
            <Badge variant="lightgray-outline">
              {counts.schemas} schemas
              {counts.collections ? ` · ${counts.collections} collections` : ""}
            </Badge>
          )}
        </div>
        <Link
          to="/schema-marketplace"
          className="flex items-center gap-0.5 font-normal text-gray-500 text-sm hover:text-custom-blue-700 hover:underline"
        >
          View all
          <Icon icon="mdi:chevron-right" />
        </Link>
      </header>

      <div className="flex flex-1 flex-col justify-between gap-2 p-3">
        {isOnboarding ? (
          <>
            <div className="flex items-start gap-2">
              <Icon icon="mdi:rocket-launch-outline" className="mt-0.5 shrink-0 text-custom-blue-700 text-lg" />
              <div className="flex min-w-0 flex-col">
                <span className="font-semibold">Install your first schema</span>
                <span className="text-gray-500 text-xs">
                  Ready-made schemas from the Infrahub Marketplace. No Git repo required.
                </span>
              </div>
            </div>
            <Link
              to="/schema-marketplace"
              className="inline-flex items-center justify-center gap-1 self-stretch rounded-md bg-custom-blue-700 px-3 py-1.5 font-medium text-sm text-white shadow-sm transition-colors hover:bg-custom-blue-700/90"
            >
              Get started <Icon icon="mdi:arrow-right" />
            </Link>
          </>
        ) : (
          <>
            <div className="flex items-start gap-2">
              <Icon icon="mdi:package-variant-closed" className="mt-0.5 shrink-0 text-gray-500 text-lg" />
              <div className="flex min-w-0 flex-col">
                <span className="text-sm">Extend this instance</span>
                <span className="text-gray-500 text-xs">
                  Install additional schemas and collections from the Infrahub Marketplace.
                </span>
              </div>
            </div>
            <Link
              to="/schema-marketplace"
              className="inline-flex items-center justify-center gap-1 self-stretch rounded-md border border-gray-200 bg-white px-3 py-1.5 font-medium text-gray-800 text-sm transition-colors hover:bg-gray-100"
            >
              Browse Marketplace <Icon icon="mdi:arrow-right" />
            </Link>
          </>
        )}
      </div>
    </Card>
  );
}
