export interface MarketplaceTag {
  id: string;
  name: string;
}

export interface MarketplaceVersionSummary {
  id: string;
  semver: string;
  status: string;
  downloadCount: number;
}

export interface MarketplaceSchema {
  id: string;
  name: string;
  namespace: string;
  display_name: string;
  description: string;
  download_count: number;
  upvote_count: number;
  fork_count: number;
  visibility: string;
  tags: MarketplaceTag[];
  versions: MarketplaceVersionSummary[];
}

export interface MarketplaceCollectionItemSchema {
  id: string;
  name: string;
  namespace: string;
  displayName: string | null;
  description: string;
}

export interface MarketplaceCollectionItem {
  id: string;
  position: number;
  schema: MarketplaceCollectionItemSchema;
}

export interface MarketplaceCollection {
  id: string;
  name: string;
  namespace: string;
  display_name: string | null;
  description: string;
  schema_count: number;
  download_count: number;
  upvote_count: number;
  items: MarketplaceCollectionItem[];
}

export interface MarketplaceTagCount {
  id: string;
  name: string;
  count: number;
}

export interface MarketplaceSchemasListResponse {
  schemas: MarketplaceSchema[];
  total_count: number;
}

export interface MarketplaceCollectionsListResponse {
  collections: MarketplaceCollection[];
  total_count: number;
}

export interface MarketplaceVersionContent {
  id: string;
  semver: string;
  content: string;
  download_url: string;
  dependencies: Array<{ id: string; name: string; namespace: string }>;
}
