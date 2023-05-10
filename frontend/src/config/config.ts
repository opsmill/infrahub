export const INFRAHUB_API_SERVER_URL =
  process.env.REACT_APP_INFRAHUB_API_SERVER_URL || "http://localhost:8000";

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
      ? `${INFRAHUB_API_SERVER_URL}/schema?branch=${branch}`
      : `${INFRAHUB_API_SERVER_URL}/schema`,
  CONFIG_URL: `${INFRAHUB_API_SERVER_URL}/config`,
  DATA_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/diff/data?branch=${branch}`,
  FILES_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/diff/files?branch=${branch}`,
  SCHEMA_DIFF_URL: (branch?: string) => `${INFRAHUB_API_SERVER_URL}/diff/schema?branch=${branch}`,
};
