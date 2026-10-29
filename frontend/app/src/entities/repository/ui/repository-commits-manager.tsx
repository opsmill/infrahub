import { Button, Spinner } from "@infrahub/ui";

import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import {
  REPOSITORY_INTERNAL_STATUS_ACTIVE,
  REPOSITORY_INTERNAL_STATUS_STAGING,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import { isReadOnlyRepositoryKind } from "@/entities/repository/domain/rules/is-read-only-repository";
import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useIsRebaseOnly } from "@/entities/repository/ui/hooks/use-is-rebase-only";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  canLoadOlderCommits,
  getCommitLogHeaderState,
  getCommitLogWithoutPages,
  getLoadedCommits,
  getNextPageState,
  isShowingStaleCommits,
  type RepositoryCommitsRepository,
} from "@/entities/repository/ui/repository-commits.view";
import { RepositoryCommitsHeader } from "@/entities/repository/ui/repository-commits-header";
import { RepositoryCommitsNotice } from "@/entities/repository/ui/repository-commits-notice";

export interface RepositoryCommitsManagerProps {
  repositoryId: string;
  repositoryKind: string;
  repositoryName: string;
  repositoryInternalStatus: string | null;
  repositoryLocation: string | null;
  updatePermission: PermissionDecision;
}

const gridTemplateColumns = () =>
  "fit-content(8rem) minmax(16rem, 1fr) fit-content(14rem) fit-content(12rem) fit-content(16rem) 2.5rem";

const CONDITIONS_EXPLAINING_EMPTY_LOG: RepositoryGitCondition[] = [
  RepositoryGitCondition.NOT_TRACKED,
  RepositoryGitCondition.NO_REMOTE,
  RepositoryGitCondition.REF_MISSING,
  RepositoryGitCondition.UNAVAILABLE,
];

export function RepositoryCommitsManager({
  repositoryId,
  repositoryKind,
  repositoryName,
  repositoryInternalStatus,
  repositoryLocation,
  updatePermission,
}: RepositoryCommitsManagerProps) {
  const rebaseOnly = useIsRebaseOnly({
    repositoryKind,
    internalStatus: repositoryInternalStatus,
  });
  const repository: RepositoryCommitsRepository = {
    id: repositoryId,
    name: repositoryName,
    isReadOnly: isReadOnlyRepositoryKind(repositoryKind),
    isStaging: repositoryInternalStatus === REPOSITORY_INTERNAL_STATUS_STAGING,
    isActive: repositoryInternalStatus === REPOSITORY_INTERNAL_STATUS_ACTIVE,
    updatePermission,
  };
  const {
    data,
    error,
    failureReason,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    isFetchNextPageError,
    isRefetchError,
    isRefetching,
  } = useGetRepositoryCommits({ repositoryId });
  const pages = data?.pages ?? [];
  const [log] = pages;
  const withoutPages = getCommitLogWithoutPages({ error, failureReason, isFetching });
  const header = (
    <RepositoryCommitsHeader
      commitLog={getCommitLogHeaderState(log, withoutPages)}
      repository={repository}
      rebaseOnly={rebaseOnly}
    />
  );

  if (!log) {
    return (
      <Col className="h-full gap-0">
        {header}
        {withoutPages.kind === "failed" && <ErrorScreen message={withoutPages.error.message} />}
      </Col>
    );
  }

  const commits = getLoadedCommits(pages);
  const nextPageState = getNextPageState({
    isFetchNextPageError,
    isFetchingNextPage,
    failureReason,
  });

  if (commits.length === 0 && CONDITIONS_EXPLAINING_EMPTY_LOG.includes(log.condition)) {
    return <Col className="h-full gap-0">{header}</Col>;
  }

  return (
    <Col className="h-full gap-0">
      {header}
      {isShowingStaleCommits({ isRefetchError, isRefetching, failureReason }) && (
        <RepositoryCommitsNotice>
          <p>
            Couldn't refresh the commit log right now. Showing the last loaded commits; older
            commits load after a successful refresh.
          </p>
        </RepositoryCommitsNotice>
      )}
      <InfiniteScroll
        scrollX
        className="bg-table-frame"
        hasNextPage={canLoadOlderCommits({ hasNextPage, isRefetching, isRefetchError })}
        // An older page that is still retrying must not be cancelled and restarted by another scroll.
        onLoadMore={() => fetchNextPage({ cancelRefetch: false })}
      >
        <DataTable
          columns={getRepositoryCommitsColumns({
            importedCommit: log.imported_commit,
            condition: log.condition,
            rebaseOnly,
            repositoryLocation,
          })}
          data={commits}
          getRowId={(commit) => commit.hash}
          gridTemplateColumns={gridTemplateColumns}
          renderEmpty={() => <NoDataFound message="This ref has no commits." />}
        />
        {nextPageState === "loading" && <Spinner className="mx-auto my-2" />}
        {(nextPageState === "failed" || nextPageState === "retry-pending") && (
          <RepositoryCommitsNotice>
            <p>Older commits could not be loaded right now.</p>
            <Button
              variant="outline"
              size="sm"
              isPending={nextPageState === "retry-pending"}
              onPress={() => fetchNextPage()}
            >
              Retry
            </Button>
          </RepositoryCommitsNotice>
        )}
      </InfiniteScroll>
    </Col>
  );
}
