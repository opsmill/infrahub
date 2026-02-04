export const INFRAHUB_GITHUB_URL = "https://github.com/opsmill/infrahub";
export const INFRAHUB_DISCORD_URL = "https://discord.gg/opsmill";

export const INFRAHUB_API_SERVER_URL = import.meta.env.DEV
  ? "http://localhost:8000"
  : window.location.origin.toString();

export const INFRAHUB_DOC_LOCAL = `${INFRAHUB_API_SERVER_URL}/docs`;

export const INFRAHUB_SWAGGER_DOC_URL = `${INFRAHUB_API_SERVER_URL}/api/docs`;

export const CONFIG = {
  GRAPHQL_URL: (branch?: string | null, date?: Date | null) => {
    if (!date) {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}`;
    } else {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}?at=${date.toISOString()}`;
    }
  },
  SEARCH_URL: (query: string, limit: number = 3) =>
    `${INFRAHUB_API_SERVER_URL}/api/search/docs?query=${query}&limit=${limit}`,
  ARTIFACTS_CONTENT_URL: (storageId: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`,
  // File endpoints - for CoreObjectFile nodes
  FILE_BY_NODE_ID_URL: (nodeId: string, preview = false) =>
    `${INFRAHUB_API_SERVER_URL}/api/storage/files/${nodeId}${preview ? "?preview=true" : ""}`,
  FILE_BY_STORAGE_ID_URL: (storageId: string, preview = false) =>
    `${INFRAHUB_API_SERVER_URL}/api/storage/files/by-storage-id/${storageId}${preview ? "?preview=true" : ""}`,
  FILES_CONTENT_URL: (repositoryId: string, location: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/file/${repositoryId}/${encodeURIComponent(location)}`,
};
