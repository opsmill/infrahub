import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import Accordion from "@/components/display/accordion";
import { Badge } from "@/components/display/badge";
import { DateDisplay } from "@/components/display/date-display";
import SlideOver from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import ModalDelete from "@/components/modals/modal-delete";
import { List } from "@/components/table/list";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
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
import { constructPath, getCurrentQsp } from "@/utils/fetch";
import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/20/solid";
import { ArrowPathIcon, PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
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

  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [displayModal, setDisplayModal] = useState(false);
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  const navigate = useNavigate();

  const branchAction = async ({ successMessage, errorMessage, mutation }: any) => {
    if (!branchName) return;

    try {
      setIsLoadingRequest(true);

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
    } catch (error: any) {
      console.error("error: ", error);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={errorMessage} />);
    }

    setIsLoadingRequest(false);
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
                  buttonType={BUTTON_TYPES.VALIDATE}
                >
                  Merge
                  <CheckIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={!isAuthenticated || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() => setShowCreateDrawer(true)}
                >
                  Propose change
                  <PlusIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

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
                  buttonType={BUTTON_TYPES.WARNING}
                >
                  Validate
                  <ShieldCheckIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={!isAuthenticated || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() => setDisplayModal(true)}
                  buttonType={BUTTON_TYPES.CANCEL}
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

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">Create Proposed Changes</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true"
              >
                <circle cx={3} cy={3} r={3} />
              </svg>
              {PROPOSED_CHANGES_OBJECT}
            </span>
          </div>
        }
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}
      >
        <ObjectForm
          kind={PROPOSED_CHANGES_OBJECT}
          onSuccess={() => setShowCreateDrawer(false)}
          onCancel={() => setShowCreateDrawer(false)}
        />
      </SlideOver>

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
