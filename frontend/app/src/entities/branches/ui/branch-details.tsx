import { Col, Row } from "@/shared/components/container";
import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetBranchDetails } from "@/entities/branches/domain/get-branch-details.query";
import { BranchDeleteButton } from "@/entities/branches/ui/branch-delete-button";
import { BranchAttributes } from "@/entities/branches/ui/branch-details/branch-attributes";
import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
import { BranchProposeChangeButton } from "@/entities/branches/ui/branch-propose-change-button";
import { BranchRebaseButton } from "@/entities/branches/ui/branch-rebase-button";
import { BranchValidateButton } from "@/entities/branches/ui/branch-validate-button";
import {
  BRANCH_MERGE_WORKFLOW,
  BRANCH_REBASE_WORKFLOW,
  BRANCH_VALIDATE_WORKFLOW,
} from "@/entities/tasks/constants";
import { TaskDisplay } from "@/entities/tasks/ui/task-display";

interface BranchDetailsProps {
  branchName: string;
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
        <Col>
          <Row className="flex-wrap">
            <BranchMergeButton branch={branch} />
            <BranchProposeChangeButton branch={branch} />
            <BranchRebaseButton branch={branch} />
            <BranchValidateButton branch={branch} />
            <BranchDeleteButton branch={branch} />
          </Row>

          <Accordion
            title={<div className="py-2 font-normal text-xs">Tasks</div>}
            data-testid="tasks-accordion"
          >
            <TaskDisplay
              branch={branch.name}
              workflow={[BRANCH_VALIDATE_WORKFLOW, BRANCH_MERGE_WORKFLOW, BRANCH_REBASE_WORKFLOW]}
            />
          </Accordion>
        </Col>
      )}
    </Col>
  );
};
