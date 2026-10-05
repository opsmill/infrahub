import { Button, Spinner } from "@infrahub/ui";
import { useState } from "react";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  getEmptyState,
  getHistoryRetry,
  getLoadedCommits,
  type HistoryRetry,
  isShowingStaleCommits,
} from "@/entities/repository/ui/repository-commits.view";
import {
  RepositoryCommitsHeader,
  RepositoryCommitsRefreshButton,
} from "@/entities/repository/ui/repository-commits-header";
import { RepositoryCommitsNotice } from "@/entities/repository/ui/repository-commits-notice";

export interface RepositoryCommitsManagerProps {
  repositoryId: string;
  repositoryLocation: string | null;
}

interface RetryInFlight {
  retry: HistoryRetry;
  repositoryId: string;
  branchName: string;
}

const gridTemplateColumns = () =>
  "fit-content(8rem) minmax(16rem, 1fr) fit-content(14rem) fit-content(12rem) fit-content(16rem) 2.5rem";

export function RepositoryCommitsManager({
  repositoryId,
  repositoryLocation,
}: RepositoryCommitsManagerProps) {
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    refetch,
  } = useGetRepositoryCommits({ repositoryId });
  const { currentBranch } = useCurrentBranch();
  const [startedRetry, setStartedRetry] = useState<RetryInFlight | null>(null);
  const retryInFlight =
    startedRetry?.repositoryId === repositoryId && startedRetry.branchName === currentBranch.name
      ? startedRetry.retry
      : null;
  const pages = data?.pages ?? [];
  const [log] = pages;
  const commits = getLoadedCommits(pages);
  // Starting a retry clears the error it answers, so the notice stays up until the retry settles.
  const historyRetry = retryInFlight ?? getHistoryRetry(pages, { isFetchNextPageError });
  const isLoadingMoreOnScroll = isFetchingNextPage && !retryInFlight;

  const retryHistory = async (retry: HistoryRetry) => {
    const started = { retry, repositoryId, branchName: currentBranch.name };
    setStartedRetry(started);
    try {
      await (retry === "fetch-next-page" ? fetchNextPage() : refetch());
    } finally {
      setStartedRetry((current) => (current === started ? null : current));
    }
  };

  if (error && commits.length === 0) {
    return (
      <Col className="h-full gap-0">
        <Row className="p-2">
          <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
        </Row>
        <ErrorScreen message={error.message} />
      </Col>
    );
  }

  if (!log) {
    return <LoadingIndicator className="h-full p-4" />;
  }

  if (commits.length === 0) {
    const emptyState = getEmptyState(log);
    if (emptyState) {
      return (
        <Col className="h-full gap-0">
          <Row className="p-2">
            <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
          </Row>
          <NoDataFound title={emptyState.title} message={emptyState.message} />
        </Col>
      );
    }
  }

  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} repositoryId={repositoryId} />
      {isShowingStaleCommits({
        firstPage: log,
        hasError: error !== null,
        isFetchNextPageError,
        loadedCommitCount: commits.length,
      }) && (
        <RepositoryCommitsNotice>
          <p>Couldn't refresh the commit log right now. Showing the last loaded commits.</p>
        </RepositoryCommitsNotice>
      )}
      <InfiniteScroll
        scrollX
        className="bg-table-frame"
        hasNextPage={hasNextPage}
        onLoadMore={fetchNextPage}
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
        {isLoadingMoreOnScroll && <Spinner className="mx-auto my-2" />}
        {historyRetry && !isLoadingMoreOnScroll && (
          <RepositoryCommitsNotice>
            <p>Older commits could not be loaded right now.</p>
            <Button
              variant="outline"
              size="sm"
              isPending={retryInFlight !== null}
              onPress={() => retryHistory(historyRetry)}
            >
              Retry
            </Button>
          </RepositoryCommitsNotice>
        )}
      </InfiniteScroll>
    </Col>
  );
}
