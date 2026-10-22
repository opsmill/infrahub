import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";
import { isUpdatedOnlyByRebase } from "@/entities/repository/domain/rules/is-updated-only-by-rebase";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  getPendingCountLabel,
  isLoadingFirstPage,
} from "@/entities/repository/ui/repository-commits.view";

export interface RepositoryCommitsTabProps {
  objectKind: string;
  objectId: string;
  internalStatus: string | null;
}

export function RepositoryCommitsTab({
  objectKind,
  objectId,
  internalStatus,
}: RepositoryCommitsTabProps) {
  const { currentBranch } = useCurrentBranch();
  const updatedOnlyByRebase = isUpdatedOnlyByRebase({
    repositoryKind: objectKind,
    internalStatus,
    branch: currentBranch,
  });
  const {
    isPending,
    failureReason,
    data: pendingImportCount,
  } = useGetRepositoryCommits(
    { repositoryId: objectId },
    {
      select: ({ pages: [firstPage] }) => (firstPage ? getPendingImportCount(firstPage) : null),
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
            <span className="sr-only"> {getPendingCountLabel({ updatedOnlyByRebase })}</span>
          </Badge>
        )
      )}
    </LinkTab>
  );
}
