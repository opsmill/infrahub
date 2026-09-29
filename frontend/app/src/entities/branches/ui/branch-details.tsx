import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { BranchDetail } from "@/entities/branches/domain/model/branch";
import { BranchDeleteButton } from "@/entities/branches/ui/branch-delete-button";
import { BranchAttributes } from "@/entities/branches/ui/branch-details/branch-attributes";
import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { BranchProposeChangeButton } from "@/entities/branches/ui/branch-propose-change-button";
import { BranchRebaseButton } from "@/entities/branches/ui/branch-rebase-button";
import { BranchValidateButton } from "@/entities/branches/ui/branch-validate-button";
import { useGetBranchDetails } from "@/entities/branches/ui/queries/get-branch-details.query";
import { BranchRepositoriesCard } from "@/entities/repository/ui/branch-repositories/branch-repositories-card";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { BranchTasksCard } from "@/entities/tasks/ui/branch-tasks/branch-tasks-card";

interface BranchDetailsProps {
  branchName: string;
  reposPage: number;
  onReposPageChange: (page: number) => void;
  tasksPage: number;
  onTasksPageChange: (page: number) => void;
}

export const BranchDetails = ({
  branchName,
  reposPage,
  onReposPageChange,
  tasksPage,
  onTasksPageChange,
}: BranchDetailsProps) => {
  const { isPending, error, data: branch } = useGetBranchDetails({ branchName });

  if (isPending) {
    return <LoadingIndicator className="h-59.75" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the branch details." />;
  }

  if (!branch) {
    return <NoDataFound message={`Branch ${branchName} does not exists.`} />;
  }

  return (
    <Col>
      <BranchAttributes branch={branch} />

      {!branch.is_default && (
        <BranchRepositoriesCard
          branchName={branch.name}
          isDefaultBranch={!!branch.is_default}
          syncWithGit={!!branch.sync_with_git}
          page={reposPage}
          onPageChange={onReposPageChange}
        />
      )}

      {!branch.is_default && (
        <Row className="flex-wrap">
          <BranchMergeButton branch={branch} />
          <BranchProposeChangeButton branch={branch} />
          <BranchRebaseButton branch={branch} />
          <BranchValidateButton branch={branch} />
          <BranchDeleteButton branch={branch} />
        </Row>
      )}

      {!branch.is_default && (
        <BranchTasksSection branch={branch} page={tasksPage} onPageChange={onTasksPageChange} />
      )}
    </Col>
  );
};

interface BranchTasksSectionProps {
  branch: BranchDetail;
  page: number;
  onPageChange: (page: number) => void;
}

function BranchTasksSection({ branch, page, onPageChange }: BranchTasksSectionProps) {
  const { data } = useGetBranchRepositories({
    branchName: branch.name,
    syncWithGit: !!branch.sync_with_git,
  });
  const repositoryNames = new Map(
    data?.status === "ok" ? data.repositories.map(({ id, name }) => [id, name]) : []
  );

  return (
    <BranchTasksCard
      branchName={branch.name}
      isDefaultBranch={!!branch.is_default}
      page={page}
      onPageChange={onPageChange}
      repositoryNames={repositoryNames}
    />
  );
}
