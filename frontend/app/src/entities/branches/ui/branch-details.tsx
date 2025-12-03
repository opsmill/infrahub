import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useAtom, useAtomValue } from "jotai";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { Button, LinkButton } from "@/shared/components/buttons/button-primitive";
import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_DELETE } from "@/entities/branches/api/deleteBranch";
import { useGetBranchDetails } from "@/entities/branches/domain/get-branch-details.query";
import { branchesState } from "@/entities/branches/stores";
import { BranchAttributes } from "@/entities/branches/ui/branch-details/branch-attributes";
import { BranchMergeButton } from "@/entities/branches/ui/branch-merge-button";
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
  const date = useAtomValue(datetimeAtom);
  const { isAuthenticated } = useAuth();
  const [branches, setBranches] = useAtom(branchesState);

  const [displayModal, setDisplayModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();

  const { isPending, error, data: branch } = useGetBranchDetails({ branchName });

  if (isPending) {
    return <LoadingIndicator className="h-[239px]" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the branch details." />;
  }

  if (!branch) {
    return <NoDataFound message={`Branch ${branchName} does not exists.`} />;
  }

  const branchAction = async ({ successMessage, errorMessage, mutation }: any) => {
    if (!branchName) return;

    try {
      setIsLoading(true);

      await graphqlClient.mutate({
        mutation,
        variables: {
          name: branch.name,
        },
        context: {
          branch: branchName,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />, {
        toastId: "alert-success",
      });
      setIsLoading(false);
    } catch (error) {
      console.error(error);
      toast(<Alert type={ALERT_TYPES.ERROR} message={errorMessage} />);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <BranchAttributes branch={branch} />

      <div className="flex flex-col gap-4">
        <div>
          {branch?.name && (
            <>
              <div className="flex flex-1 flex-col gap-4 md:flex-row">
                <BranchMergeButton branch={branch} />

                <LinkButton
                  onClick={(event) => {
                    if (!isAuthenticated || branch.is_default) {
                      event?.preventDefault();
                    }
                  }}
                  className={classNames(
                    (!isAuthenticated || branch.is_default) && "cursor-not-allowed opacity-50"
                  )}
                  to={constructPath("/proposed-changes/new", [
                    { name: QSP.SOURCE_BRANCH, value: branch?.name },
                  ])}
                >
                  Propose change
                  <PlusIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </LinkButton>

                <BranchRebaseButton branch={branch} />

                <BranchValidateButton branch={branch} />

                <Button
                  disabled={!isAuthenticated || !!branch.is_default}
                  onClick={() => setDisplayModal(true)}
                  variant={"danger"}
                >
                  Delete
                  <TrashIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </>
          )}
        </div>

        <Accordion
          title={<div className="font-normal text-xs">Tasks</div>}
          data-testid="tasks-accordion"
        >
          <div className="mt-2">
            <TaskDisplay
              branch={branch?.name}
              workflow={[BRANCH_VALIDATE_WORKFLOW, BRANCH_MERGE_WORKFLOW, BRANCH_REBASE_WORKFLOW]}
            />
          </div>
        </Accordion>
      </div>

      {displayModal && (
        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to remove the branch
              <br /> <b>`{branch?.name}`</b>?
            </>
          }
          onCancel={() => setDisplayModal(false)}
          onDelete={async () => {
            await branchAction({
              successMessage: "Branch deleted requested!",
              errorMessage: "An error occurred while deleting the branch",
              mutation: BRANCH_DELETE,
            });

            const queryStringParams = getCurrentQsp();
            const isDeletedBranchSelected = queryStringParams.get(QSP.BRANCH) === branch.name;

            const path = isDeletedBranchSelected
              ? constructPath("/branches", [{ name: QSP.BRANCH, exclude: true }])
              : constructPath("/branches");

            navigate(path);
            const nextBranches = branches.filter(({ name }) => name !== branch.name);
            setBranches(nextBranches);
          }}
          open={displayModal}
          setOpen={() => setDisplayModal(false)}
          isLoading={isLoading}
        />
      )}
    </div>
  );
};
