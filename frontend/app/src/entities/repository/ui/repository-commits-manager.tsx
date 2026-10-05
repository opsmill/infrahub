import { Button, Spinner } from "@infrahub/ui";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import { RepositoryGitUnavailableError } from "@/entities/repository/domain/model/repository-git-unavailable-error";
import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import {
  type CommitLogEmptyState,
  getEmptyState,
  getLoadedCommits,
  getNoCommitLogState,
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
    isRefetchError,
  } = useGetRepositoryCommits({ repositoryId });
  const pages = data?.pages ?? [];
  const [log] = pages;

  if (!log) {
    if (error instanceof RepositoryGitUnavailableError) {
      return (
        <RepositoryCommitsEmptyState
          log={error.log}
          repositoryId={repositoryId}
          emptyState={getEmptyState(error)}
        />
      );
    }

    if (error) {
      return (
        <Col className="h-full gap-0">
          <Row className="p-2">
            <RepositoryCommitsRefreshButton repositoryId={repositoryId} />
          </Row>
          <ErrorScreen message={error.message} />
        </Col>
      );
    }

    return <LoadingIndicator className="h-full p-4" />;
  }

  const commits = getLoadedCommits(pages);
  const noCommitLogState = commits.length === 0 ? getNoCommitLogState(log) : null;

  if (noCommitLogState) {
    return (
      <RepositoryCommitsEmptyState
        log={log}
        repositoryId={repositoryId}
        emptyState={noCommitLogState}
      />
    );
  }

  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} repositoryId={repositoryId} />
      {isRefetchError && (
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
        {isFetchNextPageError ? (
          <RepositoryCommitsNotice>
            <p>Older commits could not be loaded right now.</p>
            <Button
              variant="outline"
              size="sm"
              isPending={isFetchingNextPage}
              onPress={() => fetchNextPage()}
            >
              Retry
            </Button>
          </RepositoryCommitsNotice>
        ) : (
          isFetchingNextPage && <Spinner className="mx-auto my-2" />
        )}
      </InfiniteScroll>
    </Col>
  );
}

interface RepositoryCommitsEmptyStateProps {
  log: RepositoryCommitLog;
  repositoryId: string;
  emptyState: CommitLogEmptyState;
}

function RepositoryCommitsEmptyState({
  log,
  repositoryId,
  emptyState,
}: RepositoryCommitsEmptyStateProps) {
  return (
    <Col className="h-full gap-0">
      <RepositoryCommitsHeader log={log} repositoryId={repositoryId} />
      <NoDataFound title={emptyState.title} message={emptyState.message} />
    </Col>
  );
}
