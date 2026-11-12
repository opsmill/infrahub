export interface CanRunGeneratorsParams {
  isAuthenticated: boolean;
  isDefaultBranch: boolean;
  hasEditDefaultBranch: boolean | undefined;
}

// Mirrors the server, which refuses mutations from anonymous users and, on the default branch,
// from users without the permission to edit it.
export const canRunGenerators = ({
  isAuthenticated,
  isDefaultBranch,
  hasEditDefaultBranch,
}: CanRunGeneratorsParams): boolean => {
  return isAuthenticated && (!isDefaultBranch || hasEditDefaultBranch === true);
};
