import NoDataFound from "@/shared/components/errors/no-data-found";

import {
  NO_BRANCH_IN_SCOPE,
  NO_BRANCH_MATCHES_FILTERS,
} from "@/entities/repository/ui/repository-branches-card/messages";

interface RepositoryBranchesEmptyProps {
  hasFilters: boolean;
}

export function RepositoryBranchesEmpty({ hasFilters }: RepositoryBranchesEmptyProps) {
  return <NoDataFound message={hasFilters ? NO_BRANCH_MATCHES_FILTERS : NO_BRANCH_IN_SCOPE} />;
}
