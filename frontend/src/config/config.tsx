export const INFRAHUB_API_SERVER_URL = process.env.REACT_APP_INFRAHUB_API_SERVER_URL || "http://localhost:8000";

export const CONFIG = {
  QSP_BRANCH: "branch",
  QSP_DATETIME: "at",
  GRAPHQL_URL: (() => {
    let lastUpdatedBranch = "main";
    let lastUpdatedTime: Date | undefined | null = undefined;

    return (branch: string | null | undefined, time?: Date | null | undefined) => {
      lastUpdatedBranch = branch ?? lastUpdatedBranch;
      lastUpdatedTime = time;

      if(!lastUpdatedTime) {
        return `${INFRAHUB_API_SERVER_URL}/graphql/${lastUpdatedBranch}`;
      } else {
        return `${INFRAHUB_API_SERVER_URL}/graphql/${lastUpdatedBranch}?at=${lastUpdatedTime.toISOString()}`;
      }
    };
  })(),
  SCHEMA_URL: (branch?: string) => branch
    ? `${INFRAHUB_API_SERVER_URL}/schema/?branch=${branch}`
    : `${INFRAHUB_API_SERVER_URL}/schema/`
};