export const INFRAHUB_GITHUB_URL = "https://github.com/opsmill/infrahub";

export const INFRAHUB_DOC_URL = "https://docs.infrahub.app/";

export const INFRAHUB_API_SERVER_URL = import.meta.env.DEV
  ? "http://localhost:8000"
  : window.location.origin.toString();

export const CONFIG = {
  LOGOUT_URL: `${INFRAHUB_API_SERVER_URL}/api/auth/logout`,
  GRAPHQL_URL: (branch: string | null | undefined, date?: Date | null | undefined) => {
    if (!date) {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}`;
    } else {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch ?? "main"}?at=${date.toISOString()}`;
    }
  },
  SCHEMA_URL: (branch?: string | null) =>
    branch
      ? `${INFRAHUB_API_SERVER_URL}/api/schema?branch=${branch}`
      : `${INFRAHUB_API_SERVER_URL}/api/schema`,
  CONFIG_URL: `${INFRAHUB_API_SERVER_URL}/api/config`,
  AUTH_SIGN_IN_URL: `${INFRAHUB_API_SERVER_URL}/api/auth/login`,
  AUTH_REFRESH_TOKEN_URL: `${INFRAHUB_API_SERVER_URL}/api/auth/refresh`,
  DATA_DIFF_URL: (branch?: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/diff/data?branch=${branch}`,
  FILES_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/api/diff/files?branch=${branch}`,
  SCHEMA_DIFF_URL: (branch?: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/diff/schema?branch=${branch}`,
  ARTIFACTS_DIFF_URL: (branch?: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/diff/artifacts?branch=${branch}`,
  ARTIFACTS_GENERATE_URL: (id?: string) => `${INFRAHUB_API_SERVER_URL}/api/artifact/generate/${id}`,
  ARTIFACTS_CONTENT_URL: (storageId: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`,
  ARTIFACT_DETAILS_URL: (id: string) => `${INFRAHUB_API_SERVER_URL}/api/artifact/${id}`,
  FILES_CONTENT_URL: (repositoryId: string, location: string) =>
    `${INFRAHUB_API_SERVER_URL}/api/file/${repositoryId}/${encodeURIComponent(location)}`,
  STORAGE_DETAILS_URL: (id: string) => `${INFRAHUB_API_SERVER_URL}/api/storage/object/${id}`,
};
