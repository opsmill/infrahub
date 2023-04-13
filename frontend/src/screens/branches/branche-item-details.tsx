import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "../../components/alert";
import { Badge } from "../../components/badge";
import { Button, BUTTON_TYPES } from "../../components/button";
import { Pill } from "../../components/pill";
import deleteBranch from "../../graphql/mutations/branches/deleteBranch";
import mergeBranch from "../../graphql/mutations/branches/mergeBranch";
import rebaseBranch from "../../graphql/mutations/branches/rebaseBranch";
import validateBranch from "../../graphql/mutations/branches/validateBranch";
import getBranchDetails from "../../graphql/queries/branches/getBranchDetails";
import LoadingScreen from "../loading-screen/loading-screen";

export const BrancheItemDetails = () => {
  const { branchname } = useParams();

  const [branch, setBranch] = useState({} as any);
  const [isLoadingBranch, setIsLoadingBranch] = useState(true);
  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [detailsContent, setDetailsContent] = useState({});

  const navigate = useNavigate();

  const branchAction = async ({
    successMessage,
    errorMessage,
    request,
    options
  }: any) => {
    if (!branchname) return;

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
      if (!branchname) return;

      try {
        const branchDetails = await getBranchDetails(branchname);
        console.log("branchDetails: ", branchDetails);

        setBranch(branchDetails);
        setIsLoadingBranch(false);
      } catch(err) {
        console.error("err: ", err);
        setIsLoadingBranch(false);
      }
    }, [branchname]
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
          <div
            onClick={() => navigate("/branches")}
            className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
          >
            <h1 className="text-xl font-semibold text-gray-900 mr-2">Branches</h1>
          </div>

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
            <>
              <div className="border-t border-b border-gray-200 px-4 py-5 sm:p-0 mb-6">
                <dl className="divide-y divide-gray-200">
                  <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                    <dt className="text-sm font-medium text-gray-500">Name</dt>
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{branch.name}</dd>
                  </div>
                  <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                    <dt className="text-sm font-medium text-gray-500">Origin branch</dt>
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0"><Badge>{branch.origin_branch}</Badge></dd>
                  </div>
                  <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                    <dt className="text-sm font-medium text-gray-500">Branched</dt>
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0"> <Pill>{formatDistanceToNow(new Date(branch.branched_from), { addSuffix: true })}</Pill></dd>
                  </div>
                  <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                    <dt className="text-sm font-medium text-gray-500">Created</dt>
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0"> <Pill>{formatDistanceToNow(new Date(branch.created_at), { addSuffix: true })}</Pill></dd>
                  </div>
                </dl>
              </div>

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
                  onClick={() => navigate(`/branches/${branch.name}/pull-request`)}
                  disabled={branch.is_default}
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
            </>
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