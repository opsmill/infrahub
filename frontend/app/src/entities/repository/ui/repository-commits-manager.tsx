import { Button, Spinner } from "@infrahub/ui";
import { useState } from "react";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  getEmptyState,
  getHistoryRetry,
  getLoadedCommits,
  type HistoryRetry,
} from "@/entities/repository/ui/repository-commits.view";
import {
  RepositoryCommitsHeader,
  RepositoryCommitsRefreshButton,
} from "@/entities/repository/ui/repository-commits-header";

export interface RepositoryCommitsManagerProps {
  repositoryId: string;
  repositoryLocation: string | null;
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
  const [retryInFlight, setRetryInFlight] = useState<HistoryRetry | null>(null);
  const pages = data?.pages ?? [];
  const [log] = pages;
  const commits = getLoadedCommits(pages);
  // Starting a retry clears the error it answers, so the notice stays up until the retry settles.
  const historyRetry = retryInFlight ?? getHistoryRetry(pages, { isFetchNextPageError });
  const isLoadingMoreOnScroll = isFetchingNextPage && !retryInFlight;

  const retryHistory = async (retry: HistoryRetry) => {
    setRetryInFlight(retry);
    await (retry === "fetch-next-page" ? fetchNextPage() : refetch());
    setRetryInFlight(null);
  };

  if (error && commits.length === 0) {
    return (
      <Col className="h-full gap-0">
        <Row className="p-2">
          <RepositoryCommitsRefreshButton />
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
      return <NoDataFound title={emptyState.title} message={emptyState.message} />;
    }
  }

  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} />
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
          <Row className="items-center justify-center gap-2 p-2 text-foreground-muted text-sm">
            <p>Older commits could not be loaded right now.</p>
            <Button
              variant="outline"
              size="sm"
              isPending={retryInFlight !== null}
              onPress={() => retryHistory(historyRetry)}
            >
              Retry
            </Button>
          </Row>
        )}
      </InfiniteScroll>
    </Col>
  );
}
