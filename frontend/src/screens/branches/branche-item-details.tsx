import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "../../components/alert";
import { Badge } from "../../components/badge";
import { Button, BUTTON_TYPES } from "../../components/button";
import { Tooltip } from "../../components/tooltip";
import createPullRequest from "../../graphql/mutations/branches/createPullRequest";
import deleteBranch from "../../graphql/mutations/branches/deleteBranch";
import mergeBranch from "../../graphql/mutations/branches/mergeBranch";
import rebaseBranch from "../../graphql/mutations/branches/rebaseBranch";
import validateBranch from "../../graphql/mutations/branches/validateBranch";
import getBranchDetails from "../../graphql/queries/branches/getBranchDetails";
import LoadingScreen from "../loading-screen/loading-screen";

export const BrancheItemDetails = () => {
  const { branchid } = useParams();

  const [branch, setBranch] = useState({} as any);
  const [isLoadingBranch, setIsLoadingBranch] = useState(false);
  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [detailsContent, setDetailsContent] = useState({});

  const branchAction = async ({
    successMessage,
    errorMessage,
    request,
    options
  }: any) => {
    if (!branchid) return;

    try {
      setIsLoadingRequest(true);
      const result = await request(options);
      setDetailsContent(result);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />);
    } catch (error: any) {
      setDetailsContent(error);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={errorMessage} />);
    }

    setIsLoadingRequest(false);
  };

  const fetchBranchDetails = useCallback(
    async () => {
      if (!branchid) return;

      setIsLoadingBranch(true);
      try {
        const branchDetails = await getBranchDetails(branchid);

        setBranch(branchDetails);
      } catch(err) {
        console.error("err: ", err);
      }
      setIsLoadingBranch(false);
    }, [branchid]
  );

  useEffect(
    () => {
      fetchBranchDetails();
    },
    [fetchBranchDetails]
  );

  return (
    <div className="">
      <div className="bg-white sm:flex sm:items-center py-4 px-4 sm:px-6 lg:px-8 w-full">
        <div className="sm:flex-auto flex items-center">
          <h1 className="text-xl font-semibold text-gray-900 mr-2">{branch.name}</h1>
          <Tooltip message={"Origin branch"}>
            <Badge>{branch?.origin_branch}</Badge>
          </Tooltip>
          <p className="mt-2 text-sm text-gray-700 m-0 pl-2 mb-1">Access the branch details and management tools.</p>
        </div>
      </div>

      <div className="bg-white p-6 mb-6">
        {
          isLoadingBranch
          && <LoadingScreen />
        }

        {
          !isLoadingBranch
          && (
            <div className="flex flex-1 flex-col md:flex-row">
              <Button
                className="mr-0 md:mr-3"
                onClick={() => branchAction({
                  successMessage: "Branch merged successfuly!",
                  errorMessage: "An error occured while merging the branch",
                  request: mergeBranch,
                  options: {
                    name: branch.name
                  }
                })}
                type={BUTTON_TYPES.VALIDATE}
                disabled={branch.is_default}
              >
                Merge
                <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>

              <Button
                className="mr-0 md:mr-3"
                onClick={() => branchAction({
                  successMessage: "Pull request created successfuly!",
                  errorMessage: "An error occured while creating the pull request",
                  request: createPullRequest,
                  options: {
                    name: branch.name
                  }
                })}
                // disabled={branch.is_default}
                disabled
              >
                Pull request
                <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>

              <Button
                className="mr-0 md:mr-3"
                onClick={() => branchAction({
                  successMessage: "Branch rebased successfuly!",
                  errorMessage: "An error occured while rebasing the branch",
                  request: rebaseBranch,
                  options: {
                    name: branch.name
                  }
                })}
                disabled={branch.is_default}
              >
                Rebase
                <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>

              <Button
                className="mr-0 md:mr-3"
                onClick={() => branchAction({
                  successMessage: "The branch is valid!",
                  errorMessage: "An error occured while validating the branch",
                  request: validateBranch,
                  options: {
                    name: branch.name
                  }
                })}
                type={BUTTON_TYPES.WARNING}
                disabled={branch.is_default}
              >
                Validate
                <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>

              <Button
                className="mr-0 md:mr-3"
                onClick={() => branchAction({
                  successMessage: "Branch deleted successfuly!",
                  errorMessage: "An error occured while deleting the branch",
                  request: deleteBranch,
                  options: {
                    name: branch.name
                  }
                })}
                type={BUTTON_TYPES.CANCEL}
                // disabled={branch.is_default}
                disabled
              >
                Delete
                <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          )
        }
      </div>

      {
        isLoadingRequest
          && (
            <div className="rounded-lg bg-white shadow p-6 m-6">
              <LoadingScreen />
            </div>
          )
      }

      {
        detailsContent
        && !isLoadingRequest
          && (
            <div className="rounded-lg bg-white shadow p-6 m-6">
              <pre>
                {JSON.stringify(detailsContent, null, 2)}
              </pre>
            </div>
          )
      }
    </div>
  );
};