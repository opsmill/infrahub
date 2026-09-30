import { Spinner } from "@infrahub/ui";

import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import {
  REPOSITORY_GIT_CONDITION,
  type RepositoryCommitLog,
} from "@/entities/repository/domain/model/repository";
import { getRepositoryCommitsColumns } from "@/entities/repository/ui/get-repository-commits-columns";
import { useLastLoadedCommitPages } from "@/entities/repository/ui/hooks/use-last-loaded-commit-pages";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";
import { RepositoryCommitsHeader } from "@/entities/repository/ui/repository-commits-header";

export interface RepositoryCommitsTabProps {
  objectId: string;
}

export function RepositoryCommitsTab({ objectId }: RepositoryCommitsTabProps) {
  const { data, error, isPending, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGetRepositoryCommits({ repositoryId: objectId });
  const pages = useLastLoadedCommitPages(data?.pages);
  const log = pages?.[0];

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (isPending || !log) {
    return <Spinner className="m-4" />;
  }

  const commits = pages.flatMap((page) => page.commits);

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
          columns={getRepositoryCommitsColumns(log.importedCommit)}
          data={commits}
          isLoading={isFetchingNextPage}
          renderEmpty={() => <NoDataFound message="This ref has no commits." />}
        />
      </InfiniteScroll>
    </Col>
  );
}

function getEmptyState(log: RepositoryCommitLog) {
  switch (log.condition) {
    case REPOSITORY_GIT_CONDITION.UNAVAILABLE:
      return {
        title: "Commit log not available yet",
        message: log.unavailable?.message ?? "Waiting for a worker to answer.",
      };
    case REPOSITORY_GIT_CONDITION.NOT_TRACKED:
      return { title: "No commit log", message: "This branch tracks no remote ref." };
    case REPOSITORY_GIT_CONDITION.NO_REMOTE:
      return { title: "No commit log", message: "The tracked ref has no remote counterpart." };
    default:
      return null;
  }
}
