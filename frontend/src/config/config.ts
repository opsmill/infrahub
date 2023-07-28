export const INFRAHUB_API_SERVER_URL = import.meta.env.DEV
  ? "http://localhost:8000"
  : window.location.origin.toString();

export const CONFIG = {
  GRAPHQL_URL: (branch: string | null | undefined, date?: Date | null | undefined) => {
    if (!date) {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}`;
    } else {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}?at=${date.toISOString()}`;
    }
  },
  SCHEMA_URL: (branch?: string) =>
    branch
      ? `${INFRAHUB_API_SERVER_URL}/api/schema?branch=${branch}`
      : `${INFRAHUB_API_SERVER_URL}/api/schema`,
  CONFIG_URL: `${INFRAHUB_API_SERVER_URL}/api/config`,
  AUTH_SIGN_IN_URL: `${INFRAHUB_API_SERVER_URL}/api/auth/login`,
  AUTH_REFRESH_TOKEN_URL: `${INFRAHUB_API_SERVER_URL}/api/auth/refresh`,
  DATA_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/api/diff/data?branch=${branch}`,
  FILES_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/api/diff/files?branch=${branch}`,
  SCHEMA_DIFF_URL: (branch?: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/diff/schema?branch=${branch}`,
  FILES_CONTENT_URL: (repositoryId: string, location: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/file/${repositoryId}/${encodeURIComponent(location)}`,
};
