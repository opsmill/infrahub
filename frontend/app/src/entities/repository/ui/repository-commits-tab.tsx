import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";
import { isShowingTrunkHistory } from "@/entities/repository/domain/rules/is-showing-trunk-history";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import { isLoadingFirstPage } from "@/entities/repository/ui/repository-commits.view";

export interface RepositoryCommitsTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryCommitsTab({ objectKind, objectId }: RepositoryCommitsTabProps) {
  const { currentBranch } = useCurrentBranch();
  // The trunk's commits are never imported onto this branch, so there is nothing to count as pending.
  const countsPendingImports = !isShowingTrunkHistory({
    repositoryKind: objectKind,
    branch: currentBranch,
  });
  const {
    isPending,
    failureReason,
    data: pendingImportCount,
  } = useGetRepositoryCommits(
    { repositoryId: objectId },
    {
      select: ({ pages: [firstPage] }) =>
        firstPage && countsPendingImports ? getPendingImportCount(firstPage) : null,
    }
  );

  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB)}
      scrollIntoViewOnActive
    >
      Commits
      {isLoadingFirstPage({ isPending, failureReason }) ? (
        <Spinner />
      ) : (
        pendingImportCount !== null &&
        pendingImportCount !== undefined && (
          <Badge className="rounded-full font-medium text-subtle">
            {pendingImportCount}
            <span className="sr-only"> pending import</span>
          </Badge>
        )
      )}
    </LinkTab>
  );
}
