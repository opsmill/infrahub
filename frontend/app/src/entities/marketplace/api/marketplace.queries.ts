import { fetchUrl } from "@/shared/api/rest/fetch";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import type {
  MarketplaceCollectionsListResponse,
  MarketplaceSchemasListResponse,
  MarketplaceTagCount,
  MarketplaceVersionContent,
} from "@/entities/marketplace/types";

const MARKETPLACE_API_BASE = `${INFRAHUB_API_SERVER_URL}/api/marketplace`;

export async function fetchMarketplaceSchemas(
  search?: string,
  tags?: string
): Promise<MarketplaceSchemasListResponse> {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (tags) params.set("tags", tags);

  const queryString = params.toString();
  const url = `${MARKETPLACE_API_BASE}/schemas${queryString ? `?${queryString}` : ""}`;
  return fetchUrl(url);
}

export async function fetchMarketplaceCollections(): Promise<MarketplaceCollectionsListResponse> {
  return fetchUrl(`${MARKETPLACE_API_BASE}/collections`);
}

export async function fetchMarketplaceTags(): Promise<MarketplaceTagCount[]> {
  return fetchUrl(`${MARKETPLACE_API_BASE}/tags`);
}

export async function fetchSchemaVersionContent(
  schemaId: string,
  versionId: string
): Promise<MarketplaceVersionContent> {
  return fetchUrl(`${MARKETPLACE_API_BASE}/schemas/${schemaId}/versions/${versionId}`);
}

export async function installMarketplaceSchemas(params: {
  repositoryId: string;
  schemaIds: string[];
  collectionIds: string[];
  branchName: string;
}): Promise<{ task_id: string; message: string }> {
  return fetchUrl(`${MARKETPLACE_API_BASE}/install`, {
    method: "POST",
    body: JSON.stringify({
      repository_id: params.repositoryId,
      schema_ids: params.schemaIds,
      collection_ids: params.collectionIds,
      branch_name: params.branchName,
    }),
  });
}
