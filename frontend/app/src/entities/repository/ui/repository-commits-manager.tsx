import { Button, Spinner } from "@infrahub/ui";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import type { RepositoryRemoteCheck } from "@/entities/repository/ui/repository-check-remote-button";
import {
  type CommitLogEmptyState,
  canLoadOlderCommits,
  getCommitLogWithoutPages,
  getEmptyState,
  getLoadedCommits,
  getNextPageState,
  getNoCommitLogState,
  isShowingStaleCommits,
} from "@/entities/repository/ui/repository-commits.view";
import {
  RepositoryCommitsHeader,
  RepositoryCommitsRefreshButton,
} from "@/entities/repository/ui/repository-commits-header";
import { RepositoryCommitsNotice } from "@/entities/repository/ui/repository-commits-notice";

interface RepositoryCheckRemoteProps {
  remoteCheck: RepositoryRemoteCheck | null;
}

export interface RepositoryCommitsManagerProps extends RepositoryCheckRemoteProps {
  repositoryId: string;
  repositoryLocation: string | null;
}

const gridTemplateColumns = () =>
  "fit-content(8rem) minmax(16rem, 1fr) fit-content(14rem) fit-content(12rem) fit-content(16rem) 2.5rem";

export function RepositoryCommitsManager({
  repositoryId,
  repositoryLocation,
  remoteCheck,
}: RepositoryCommitsManagerProps) {
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

  if (!log) {
    const withoutPages = getCommitLogWithoutPages({ error, failureReason, isFetching });

    switch (withoutPages.kind) {
      case "unavailable":
        return (
          <RepositoryCommitsEmptyState
            log={withoutPages.error.log}
            repositoryId={repositoryId}
            remoteCheck={remoteCheck}
            emptyState={getEmptyState(withoutPages.error, {
              isRetrying: withoutPages.isRetrying,
            })}
          />
        );
      case "failed":
        return (
          <Col className="h-full gap-0">
            <Row className="p-2">
              <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
            </Row>
            <ErrorScreen message={withoutPages.error.message} />
          </Col>
        );
      default:
        return <LoadingIndicator className="h-full p-4" />;
    }
  }

  const commits = getLoadedCommits(pages);
  const noCommitLogState = commits.length === 0 ? getNoCommitLogState(log) : null;
  const nextPageState = getNextPageState({
    isFetchNextPageError,
    isFetchingNextPage,
    failureReason,
  });

  if (noCommitLogState) {
    return (
      <RepositoryCommitsEmptyState
        log={log}
        repositoryId={repositoryId}
        remoteCheck={remoteCheck}
        emptyState={noCommitLogState}
      />
    );
  }

  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} repositoryId={repositoryId} remoteCheck={remoteCheck} />
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

interface RepositoryCommitsEmptyStateProps extends RepositoryCheckRemoteProps {
  log: RepositoryCommitLog;
  repositoryId: string;
  emptyState: CommitLogEmptyState;
}

function RepositoryCommitsEmptyState({
  log,
  repositoryId,
  remoteCheck,
  emptyState,
}: RepositoryCommitsEmptyStateProps) {
  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} repositoryId={repositoryId} remoteCheck={remoteCheck} />
      <NoDataFound title={emptyState.title} message={emptyState.message} />
    </Col>
  );
}
