// Types for the Schema Marketplace feature.
//
// These mirror backend/infrahub/marketplace/models.py. They are hand-written for
// now; if/when pnpm codegen covers REST schemas we can switch to generated types.

export type MarketplaceItemKind = "schema" | "collection";

export interface MarketplaceTag {
  id: string;
  name: string;
}

export interface MarketplaceTagCount {
  id: string;
  name: string;
  count: number;
}

export interface MarketplaceAuthor {
  id: string;
  username: string;
  avatar_url: string | null;
}

export interface MarketplaceVersionSummary {
  id: string;
  semver: string;
  status: "published" | "draft" | "deprecated";
  changelog: string | null;
  download_count: number;
  download_url: string;
  created_at: string;
}

export interface MarketplaceSchemaSummary {
  id: string;
  namespace: string;
  name: string;
  display_name: string | null;
  description: string | null;
  visibility: "public" | "private";
  download_count: number;
  upvote_count: number;
  fork_count: number;
  viewer_has_upvoted: boolean;
  created_at: string;
  updated_at: string;
  author: MarketplaceAuthor;
  tags: MarketplaceTag[];
  latest_version: MarketplaceVersionSummary | null;
  already_installed: boolean;
}

export interface MarketplaceSchemaDetail extends MarketplaceSchemaSummary {
  versions: MarketplaceVersionSummary[];
  readme: string | null;
}

export interface MarketplaceCollectionItem {
  namespace: string;
  name: string;
  semver: string;
  order: number;
}

export interface MarketplaceCollectionSummary {
  id: string;
  namespace: string;
  name: string;
  display_name: string | null;
  description: string | null;
  schema_count: number;
  download_count: number;
  author: MarketplaceAuthor;
  tags: MarketplaceTag[];
  already_installed: boolean;
}

export interface MarketplaceCollectionDetail extends MarketplaceCollectionSummary {
  items: MarketplaceCollectionItem[];
  readme: string | null;
}

export interface MarketplaceVersionContent {
  version_id: string;
  semver: string;
  content: string;
  content_type: "schema";
  sha256: string | null;
}

export interface PageInfo {
  has_next_page: boolean;
  end_cursor: string | null;
}

export interface MarketplaceSchemasListResponse {
  items: MarketplaceSchemaSummary[];
  page_info: PageInfo;
  total_count: number;
}

export interface MarketplaceCollectionsListResponse {
  items: MarketplaceCollectionSummary[];
  page_info: PageInfo;
  total_count: number;
}

export interface MarketplaceTagsResponse {
  tags: MarketplaceTagCount[];
}

export interface MarketplaceStatus {
  marketplace_url: string;
  url_configured: boolean;
  url_scheme_valid: boolean;
  upstream_reachable: boolean;
  checked_at: string;
}

export interface MarketplaceInstallItem {
  kind: MarketplaceItemKind;
  namespace: string;
  name: string;
  semver: string | null;
}

export interface MarketplaceInstallRequest {
  repository_id: string;
  branch_name: string;
  items: MarketplaceInstallItem[];
}

export interface MarketplaceInstallResponse {
  task_id: string;
  message: string;
}

export interface CliSnippetDownload {
  kind: MarketplaceItemKind;
  namespace: string;
  name: string;
  semver: string | null;
  command: string;
}

export interface CliSnippetResponse {
  downloads: CliSnippetDownload[];
  load_command: string;
  rendered: string;
}

// UI-only view model for the install drawer state machine.
export type InstallDrawerState =
  | { phase: "idle" }
  | { phase: "selecting"; selection: MarketplaceInstallItem[] }
  | { phase: "submitting" }
  | { phase: "pending"; taskId: string }
  | { phase: "running"; taskId: string }
  | { phase: "completed"; taskId: string }
  | { phase: "failed"; taskId: string; error: string };
