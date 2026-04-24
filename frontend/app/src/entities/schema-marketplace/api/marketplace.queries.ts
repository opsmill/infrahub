import { fetchUrl } from "@/shared/api/rest/fetch";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import type {
  CliSnippetResponse,
  MarketplaceCollectionDetail,
  MarketplaceCollectionsListResponse,
  MarketplaceInstallRequest,
  MarketplaceInstallResponse,
  MarketplaceSchemaDetail,
  MarketplaceSchemasListResponse,
  MarketplaceStatus,
  MarketplaceTagsResponse,
  MarketplaceVersionContent,
} from "@/entities/schema-marketplace/types";

const BASE = `${INFRAHUB_API_SERVER_URL}/api/marketplace`;

function qs(params: Record<string, string | number | undefined | null>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export function fetchMarketplaceStatus(): Promise<MarketplaceStatus> {
  return fetchUrl(`${BASE}/status`);
}

export function fetchMarketplaceSchemas(args: {
  search?: string;
  tags?: string[];
  limit?: number;
  after?: string;
}): Promise<MarketplaceSchemasListResponse> {
  return fetchUrl(
    `${BASE}/schemas${qs({
      search: args.search,
      tags: args.tags?.join(","),
      limit: args.limit,
      after: args.after,
    })}`
  );
}

export function fetchMarketplaceSchema(
  namespace: string,
  name: string
): Promise<MarketplaceSchemaDetail> {
  return fetchUrl(`${BASE}/schemas/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`);
}

// Uses the /preview route that maps to the upstream /download path, not the
// flaky /versions/{id}/content path -- see the backend docstring on
// `get_schema_version_preview` for why.
export function fetchMarketplaceSchemaVersionPreview(
  namespace: string,
  name: string,
  semver: string
): Promise<MarketplaceVersionContent> {
  return fetchUrl(
    `${BASE}/schemas/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}/versions/${encodeURIComponent(semver)}/preview`
  );
}

export function fetchMarketplaceCollections(args: {
  search?: string;
  limit?: number;
  after?: string;
}): Promise<MarketplaceCollectionsListResponse> {
  return fetchUrl(
    `${BASE}/collections${qs({
      search: args.search,
      limit: args.limit,
      after: args.after,
    })}`
  );
}

export function fetchMarketplaceCollection(
  namespace: string,
  name: string
): Promise<MarketplaceCollectionDetail> {
  return fetchUrl(
    `${BASE}/collections/${encodeURIComponent(namespace)}/${encodeURIComponent(name)}`
  );
}

export function fetchMarketplaceTags(): Promise<MarketplaceTagsResponse> {
  return fetchUrl(`${BASE}/tags`);
}

export function installFromMarketplace(
  body: MarketplaceInstallRequest
): Promise<MarketplaceInstallResponse> {
  return fetchUrl(`${BASE}/install`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchCliSnippet(args: {
  items: string[];
  branchName?: string;
  outputDir?: string;
}): Promise<CliSnippetResponse> {
  const search = new URLSearchParams();
  for (const item of args.items) {
    search.append("items", item);
  }
  if (args.branchName) search.set("branch_name", args.branchName);
  if (args.outputDir) search.set("output_dir", args.outputDir);
  return fetchUrl(`${BASE}/cli-snippet?${search.toString()}`);
}
