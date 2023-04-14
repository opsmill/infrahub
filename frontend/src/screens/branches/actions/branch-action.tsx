import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ALERT_TYPES, Alert } from "../../../components/alert";
import { toast } from "react-toastify";
import LoadingScreen from "../../loading-screen/loading-screen";
import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { BUTTON_TYPES, Button } from "../../../components/button";
import deleteBranch from "../../../graphql/mutations/branches/deleteBranch";
import validateBranch from "../../../graphql/mutations/branches/validateBranch";
import rebaseBranch from "../../../graphql/mutations/branches/rebaseBranch";
import mergeBranch from "../../../graphql/mutations/branches/mergeBranch";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../../config/constants";

export const BRANCH_TABS = {
  DIFF: "diff",
  MERGE: "merge",
  PR: "pull-request",
  REBASE: "rebase",
  VALIDATE: "validate",
  DELETE: "delete",
};

export const BranchAction = (props: any) => {
  const { branch } = props;
  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [detailsContent, setDetailsContent] = useState({});

  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const { branchname } = useParams();
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

  const renderButton = () => {
    switch(qspTab) {
      case BRANCH_TABS.MERGE: {
        return (
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
        );
      }
      case BRANCH_TABS.PR: {
        return (
          <Button
            className="mr-0 md:mr-3"
            onClick={() => navigate(`/branches/${branch.name}/pull-request`)}
            disabled={branch.is_default}
          >
            Pull request
            <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
          </Button>
        );
      }
      case BRANCH_TABS.REBASE: {
        return (
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
        );
      }
      case BRANCH_TABS.VALIDATE: {
        return (
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
        );
      }
      case BRANCH_TABS.DELETE: {
        return (
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
        );
      }
      default: {
        return null;
      }
    }
  };

  return (
    <div className="">
      <div className="bg-white p-6 mb-6">
        {
          branch?.name
          && (
            <>
              <div className="flex flex-1 flex-col md:flex-row">
                {renderButton()}
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