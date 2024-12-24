import { Button, LinkButton } from "@/components/buttons/button-primitive";
import Accordion from "@/components/display/accordion";
import { Badge } from "@/components/display/badge";
import { DateDisplay } from "@/components/display/date-display";
import ModalDelete from "@/components/modals/modal-delete";
import { List } from "@/components/table/list";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { QSP } from "@/config/qsp";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { BRANCH_DELETE } from "@/graphql/mutations/branches/deleteBranch";
import { BRANCH_MERGE } from "@/graphql/mutations/branches/mergeBranch";
import { BRANCH_REBASE } from "@/graphql/mutations/branches/rebaseBranch";
import { BRANCH_VALIDATE } from "@/graphql/mutations/branches/validateBranch";
import { getBranchDetailsQuery } from "@/graphql/queries/branches/getBranchDetails";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { branchesState } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { constructPath, getCurrentQsp } from "@/utils/fetch";
import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/20/solid";
import { ArrowPathIcon, PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import {
  BRANCH_MERGE_WORKFLOW,
  BRANCH_REBASE_WORKFLOW,
  BRANCH_VALIDATE_WORKFLOW,
} from "../tasks/constants";
import { TaskDisplay } from "./task-display";

export const BranchDetails = () => {
  const { "*": branchName } = useParams();
  const date = useAtomValue(datetimeAtom);
  const { isAuthenticated } = useAuth();
  const [branches, setBranches] = useAtom(branchesState);

  const [displayModal, setDisplayModal] = useState(false);

  const navigate = useNavigate();

  const branchAction = async ({ successMessage, errorMessage, mutation }: any) => {
    if (!branchName) return;

    try {
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
    } catch (error) {
      console.error(error);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={errorMessage} />);
    }
  };

  const { loading, error, data } = useQuery(getBranchDetailsQuery, { variables: { branchName } });

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the branch details." />;
  }

  const branchData = data?.Branch;

  if (!branchData || branchData.length === 0) {
    return <NoDataFound message={`Branch ${branchName} does not exists.`} />;
  }

  const branch = branchData[0];

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "origin_branch",
      label: "Origin branch",
    },
    {
      name: "branched_at",
      label: "Started at",
    },
    {
      name: "created_at",
      label: "Completed at",
    },
  ];

  const row = {
    values: {
      name: branch.name,
      origin_branch: <Badge className="text-sm">{branch.origin_branch}</Badge>,
      branched_at: <DateDisplay date={branch.branched_at} />,
      created_at: <DateDisplay date={branch.created_at} />,
    },
  };

  return (
    <div className="flex flex-col gap-4">
      <List columns={columns} row={row} />

      <div className="flex flex-col gap-4">
        <div>
          {branch?.name && (
            <>
              <div className="flex flex-1 flex-col md:flex-row">
                <Button
                  disabled={!isAuthenticated || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "Branch merge requested!",
                      errorMessage: "An error occurred while merging the branch",
                      mutation: BRANCH_MERGE,
                    })
                  }
                  variant={"active"}
                >
                  Merge
                  <CheckIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

                <LinkButton
                  onClick={(event) => {
                    if (!isAuthenticated || branch.is_default) {
                      event?.preventDefault();
                    }
                  }}
                  className={classNames(
                    "mr-0 md:mr-3",
                    (!isAuthenticated || branch.is_default) && "opacity-50 cursor-not-allowed"
                  )}
                  to={constructPath("/proposed-changes/new", [
                    { name: "source_branch", value: branch?.name },
                  ])}
                >
                  Propose change
                  <PlusIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </LinkButton>

                <Button
                  disabled={!isAuthenticated || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "Branch rebase requested!",
                      errorMessage: "An error occurred while rebasing the branch",
                      mutation: BRANCH_REBASE,
                    })
                  }
                  variant={"dark"}
                >
                  Rebase
                  <ArrowPathIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "Branch validation requested!",
                      errorMessage: "An error occurred while validating the branch",
                      mutation: BRANCH_VALIDATE,
                    })
                  }
                  variant={"warning"}
                >
                  Validate
                  <ShieldCheckIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={!isAuthenticated || branch.is_default}
                  className="mr-0 md:mr-3"
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
        />
      )}
    </div>
  );
};
