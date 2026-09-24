import NoDataFound from "@/shared/components/errors/no-data-found";

import {
  NO_BRANCH_AT_ALL,
  NO_BRANCH_IN_SCOPE,
  NO_BRANCH_MATCHES_FILTERS,
} from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesEmptyProps {
  hasFilters: boolean;
  listsEveryBranch: boolean;
}

export function RepositoryBranchesEmpty({
  hasFilters,
  listsEveryBranch,
}: RepositoryBranchesEmptyProps) {
  if (hasFilters) return <NoDataFound message={NO_BRANCH_MATCHES_FILTERS} />;

  return <NoDataFound message={listsEveryBranch ? NO_BRANCH_AT_ALL : NO_BRANCH_IN_SCOPE} />;
}
