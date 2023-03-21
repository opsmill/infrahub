export const INFRAHUB_API_SERVER_URL = process.env.REACT_APP_INFRAHUB_API_SERVER_URL || "http://localhost:8000"

export const CONFIG = {
  GRAPHQL_URL: (branch: string = "main", time?: Date | null) => {
    if(!time) {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch}`;
    } else {
      return `${INFRAHUB_API_SERVER_URL}/graphql/${branch}?at=${time.toISOString()}`;
    }
  },
  SCHEMA_URL: (branch: string = "main") => `${INFRAHUB_API_SERVER_URL}/schema/?branch=${branch}`
};