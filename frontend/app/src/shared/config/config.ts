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
  FILES_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/api/diff/files?branch=${branch}`,
  ARTIFACTS_DIFF_URL: (branch?: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/diff/artifacts?branch=${branch}`,
  ARTIFACTS_CONTENT_URL: (storageId: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`,
  FILES_CONTENT_URL: (repositoryId: string, location: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/file/${repositoryId}/${encodeURIComponent(location)}`,
};
