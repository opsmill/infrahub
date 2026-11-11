import NoDataFound from "@/shared/components/errors/no-data-found";

import {
  NO_BRANCH_AT_ALL,
  NO_BRANCH_IN_SCOPE,
  NO_BRANCH_MATCHES_FILTERS,
  PAGE_PAST_THE_END,
} from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesEmptyProps {
  hasFilters: boolean;
  listsEveryBranch: boolean;
  /** The set holds rows, so an empty page means the url named one past the end. */
  isPagePastTheEnd?: boolean;
}

export function RepositoryBranchesEmpty({
  hasFilters,
  listsEveryBranch,
  isPagePastTheEnd = false,
}: RepositoryBranchesEmptyProps) {
  if (isPagePastTheEnd) return <NoDataFound message={PAGE_PAST_THE_END} />;

  if (hasFilters) return <NoDataFound message={NO_BRANCH_MATCHES_FILTERS} />;

  return <NoDataFound message={listsEveryBranch ? NO_BRANCH_AT_ALL : NO_BRANCH_IN_SCOPE} />;
}
