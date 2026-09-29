import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { BranchDeleteButton } from "@/entities/branches/ui/branch-delete-button";
import { BranchAttributes } from "@/entities/branches/ui/branch-details/branch-attributes";
import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { BranchProposeChangeButton } from "@/entities/branches/ui/branch-propose-change-button";
import { BranchRebaseButton } from "@/entities/branches/ui/branch-rebase-button";
import { BranchValidateButton } from "@/entities/branches/ui/branch-validate-button";
import { useGetBranchDetails } from "@/entities/branches/ui/queries/get-branch-details.query";

interface BranchDetailsProps {
  branchName: string;
  reposPage: number;
  onReposPageChange: (page: number) => void;
  tasksPage: number;
  onTasksPageChange: (page: number) => void;
}

export const BranchDetails = ({ branchName }: BranchDetailsProps) => {
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
        <Row className="flex-wrap">
          <BranchMergeButton branch={branch} />
          <BranchProposeChangeButton branch={branch} />
          <BranchRebaseButton branch={branch} />
          <BranchValidateButton branch={branch} />
          <BranchDeleteButton branch={branch} />
        </Row>
      )}
    </Col>
  );
};
