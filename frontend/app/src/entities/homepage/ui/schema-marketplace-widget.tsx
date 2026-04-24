import { useQuery } from "@tanstack/react-query";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Card } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import {
  fetchMarketplaceCollections,
  fetchMarketplaceSchemas,
} from "@/entities/schema-marketplace/api/marketplace.queries";
import { useHasUserSchemas } from "@/entities/schema-marketplace/hooks/use-has-user-schemas";
import type { MarketplaceSchemaSummary } from "@/entities/schema-marketplace/types";

interface SchemaMarketplaceWidgetProps {
  className?: string;
}

const PREVIEW_LIMIT = 4;

/**
 * Live counts come from the already-cached proxy list endpoints at
 * `limit=1` (cheap — we only read `total_count`). The preview list pulls
 * `limit={PREVIEW_LIMIT}` for the real items; same 30s cache, same request
 * shape the Marketplace page uses, so the cache is shared.
 */
function useMarketplaceSnapshot() {
  const previewQuery = useQuery({
    queryKey: ["schema-marketplace", "widget-preview"],
    queryFn: () => fetchMarketplaceSchemas({ limit: PREVIEW_LIMIT }),
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
    preview: previewQuery.data?.items ?? [],
    schemas: previewQuery.data?.total_count ?? null,
    collections: collectionsCount.data?.total_count ?? null,
    isPending: previewQuery.isPending,
    isError: !!previewQuery.error,
  };
}

function pluralize(count: number, singular: string): string {
  return `${count} ${count === 1 ? singular : `${singular}s`}`;
}

function countSummary(schemas: number | null, collections: number | null): string | null {
  const parts: string[] = [];
  if (schemas !== null && schemas > 0) parts.push(pluralize(schemas, "schema"));
  if (collections !== null && collections > 0) parts.push(pluralize(collections, "collection"));
  if (parts.length === 0) return null;
  return parts.join(" · ");
}

function SchemaPreviewRow({ schema }: { schema: MarketplaceSchemaSummary }) {
  const label = schema.display_name || schema.name;
  return (
    <Link
      to="/schema-marketplace"
      className="group flex items-center justify-between gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-gray-50"
    >
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <Icon icon="mdi:file-code" className="shrink-0 text-gray-500" />
        <span className="min-w-0 truncate font-medium text-gray-800">{label}</span>
        <span className="shrink-0 truncate text-gray-400 text-xs">{schema.namespace}</span>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {schema.latest_version && (
          <Badge variant="lightgray-outline">v{schema.latest_version.semver}</Badge>
        )}
        <Icon
          icon="mdi:chevron-right"
          className="text-gray-300 transition-colors group-hover:text-custom-blue-700"
        />
      </div>
    </Link>
  );
}

export function SchemaMarketplaceWidget({ className }: SchemaMarketplaceWidgetProps) {
  const hasUserSchemas = useHasUserSchemas();
  const snapshot = useMarketplaceSnapshot();
  const isOnboarding = !hasUserSchemas;
  const summary = countSummary(snapshot.schemas, snapshot.collections);

  return (
    <Card
      className={classNames(
        "relative flex flex-col overflow-hidden p-0",
        isOnboarding
          ? "border-custom-blue-700/40 bg-gradient-to-br from-custom-blue-700/5 via-white to-purple-500/5"
          : "bg-white",
        className
      )}
    >
      <header className="flex items-center justify-between gap-2 border-gray-200 border-b p-3">
        <div className="flex min-w-0 items-center gap-2 font-bold">
          <Icon
            icon="mdi:storefront-outline"
            className={classNames(
              "shrink-0 text-lg",
              isOnboarding ? "text-custom-blue-700" : "text-gray-700"
            )}
          />
          <span className="truncate">Schema Marketplace</span>
        </div>
        <Link
          to="/schema-marketplace"
          className="flex shrink-0 items-center gap-0.5 whitespace-nowrap font-normal text-gray-500 text-sm hover:text-custom-blue-700 hover:underline"
        >
          View all
          <Icon icon="mdi:chevron-right" />
        </Link>
      </header>

      <div className="flex flex-1 flex-col gap-3 p-3">
        {isOnboarding ? (
          <OnboardingBody summary={summary} />
        ) : (
          <PopulatedBody
            preview={snapshot.preview}
            summary={summary}
            isPending={snapshot.isPending}
            isError={snapshot.isError}
          />
        )}
      </div>
    </Card>
  );
}

function OnboardingBody({ summary }: { summary: string | null }) {
  return (
    <>
      <div className="flex items-start gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-custom-blue-700/10">
          <Icon icon="mdi:rocket-launch-outline" className="text-custom-blue-700" />
        </div>
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="font-semibold">Install your first schema</p>
          <p className="text-gray-500 text-xs">
            Browse ready-made schemas, then apply them to this instance — with or without a Git
            repository.
          </p>
        </div>
      </div>
      {summary && (
        <p className="flex items-center gap-1.5 text-gray-500 text-xs">
          <Icon icon="mdi:package-variant-closed" className="shrink-0 text-gray-400" />
          <span className="truncate">{summary} available</span>
        </p>
      )}
      <div className="flex-1" />
      <Link
        to="/schema-marketplace"
        className="inline-flex items-center justify-center gap-1 rounded-md bg-custom-blue-700 px-3 py-2 font-medium text-sm text-white shadow-sm transition-colors hover:bg-custom-blue-700/90"
      >
        Get started
        <Icon icon="mdi:arrow-right" />
      </Link>
    </>
  );
}

function PopulatedBody({
  preview,
  summary,
  isPending,
  isError,
}: {
  preview: MarketplaceSchemaSummary[];
  summary: string | null;
  isPending: boolean;
  isError: boolean;
}) {
  if (isError) {
    return (
      <>
        <p className="text-gray-500 text-sm">
          The Marketplace is unreachable right now. Retry from the full page.
        </p>
        <div className="flex-1" />
        <Link
          to="/schema-marketplace"
          className="inline-flex items-center justify-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 font-medium text-gray-800 text-sm transition-colors hover:bg-gray-100"
        >
          Open Marketplace
          <Icon icon="mdi:arrow-right" />
        </Link>
      </>
    );
  }

  return (
    <>
      <div className="flex items-center justify-between gap-2 text-gray-500 text-xs">
        <span>Featured schemas</span>
        {summary && <span className="shrink-0 truncate">{summary} available</span>}
      </div>
      <div className="-mx-1 flex flex-1 flex-col gap-0.5 overflow-hidden">
        {isPending && preview.length === 0 && (
          <p className="px-2 py-1 text-gray-400 text-xs">Loading…</p>
        )}
        {!isPending && preview.length === 0 && (
          <p className="px-2 py-1 text-gray-400 text-xs">Nothing published yet.</p>
        )}
        {preview.slice(0, PREVIEW_LIMIT).map((schema) => (
          <SchemaPreviewRow key={schema.id} schema={schema} />
        ))}
      </div>
      <Link
        to="/schema-marketplace"
        className="inline-flex items-center justify-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 font-medium text-gray-800 text-sm transition-colors hover:bg-gray-100"
      >
        Browse Marketplace
        <Icon icon="mdi:arrow-right" />
      </Link>
    </>
  );
}
