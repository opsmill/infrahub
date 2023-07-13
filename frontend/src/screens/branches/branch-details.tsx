import { gql, useReactiveVar } from "@apollo/client";
import { CheckIcon, ShieldCheckIcon } from "@heroicons/react/20/solid";
import { ArrowPathIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useContext, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { Badge } from "../../components/badge";
import { BUTTON_TYPES, Button } from "../../components/button";
import { DateDisplay } from "../../components/date-display";
import ModalDelete from "../../components/modal-delete";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { deleteBranch } from "../../graphql/mutations/branches/deleteBranch";
import { mergeBranch } from "../../graphql/mutations/branches/mergeBranch";
import { rebaseBranch } from "../../graphql/mutations/branches/rebaseBranch";
import { validateBranch } from "../../graphql/mutations/branches/validateBranch";
import { getBranchDetails } from "../../graphql/queries/branches/getBranchDetails";
import { dateVar } from "../../graphql/variables/dateVar";
import useQuery from "../../hooks/useQuery";
import { objectToString } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

export const BranchDetails = () => {
  const { branchname } = useParams();
  const date = useReactiveVar(dateVar);
  const auth = useContext(AuthContext);

  const [isLoadingRequest, setIsLoadingRequest] = useState(false);
  const [displayModal, setDisplayModal] = useState(false);
  const [detailsContent, setDetailsContent] = useState({});

  const navigate = useNavigate();

  const branchAction = async ({ successMessage, errorMessage, request, options }: any) => {
    if (!branchname) return;

    try {
      setIsLoadingRequest(true);

      const mutationString = request({ data: objectToString(options) });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: branchname,
          date,
        },
      });

      setDetailsContent(result);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />);
    } catch (error: any) {
      console.log("error: ", error);
      setDetailsContent(error);

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={errorMessage} />);
    }

    setIsLoadingRequest(false);
  };

  const queryString = getBranchDetails({});

  const { loading, error, data } = useQuery(
    gql`
      ${queryString}
    `
  );

  const branch = data?.branch?.filter((branch: any) => branch.name === branchname)[0];

  return (
    <div className="bg-custom-white p-6">
      {loading && <LoadingScreen />}

      {error && <ErrorScreen />}

      {displayModal && (
        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to remove the the branch
              <br /> <b>`{branch?.name}`</b>?
            </>
          }
          onCancel={() => setDisplayModal(false)}
          onDelete={async () => {
            await branchAction({
              successMessage: "Branch deleted successfuly!",
              errorMessage: "An error occured while deleting the branch",
              request: deleteBranch,
              options: {
                name: branch.name,
              },
            });

            navigate(constructPath("/branches"));

            window.location.reload();
          }}
          open={!!displayModal}
          setOpen={() => setDisplayModal(false)}
        />
      )}

      {!loading && branch?.name && (
        <>
          <div className="border-t border-b border-gray-200 px-2 py-2 sm:p-0 mb-6">
            <dl className="divide-y divide-gray-200">
              <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Name</dt>
                <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">{branch.name}</dd>
              </div>
              <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Origin branch</dt>
                <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                  <Badge>{branch.origin_branch}</Badge>
                </dd>
              </div>
              <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Branched</dt>
                <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                  <DateDisplay date={branch.branched_at} />
                </dd>
              </div>
              <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                  <DateDisplay date={branch.created_at} />
                </dd>
              </div>
            </dl>
          </div>
        </>
      )}

      <div className="">
        <div className="mb-6">
          {branch?.name && (
            <>
              <div className="flex flex-1 flex-col md:flex-row">
                <Button
                  disabled={!auth?.permissions?.write || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "Branch merged successfuly!",
                      errorMessage: "An error occured while merging the branch",
                      request: mergeBranch,
                      options: {
                        name: branch.name,
                      },
                    })
                  }
                  buttonType={BUTTON_TYPES.VALIDATE}>
                  Merge
                  <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={!auth?.permissions?.write || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "Branch rebased successfuly!",
                      errorMessage: "An error occured while rebasing the branch",
                      request: rebaseBranch,
                      options: {
                        name: branch.name,
                      },
                    })
                  }>
                  Rebase
                  <ArrowPathIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() =>
                    branchAction({
                      successMessage: "The branch is valid!",
                      errorMessage: "An error occured while validating the branch",
                      request: validateBranch,
                      options: {
                        name: branch.name,
                      },
                    })
                  }
                  buttonType={BUTTON_TYPES.WARNING}>
                  Validate
                  <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                </Button>

                <Button
                  disabled={!auth?.permissions?.write || branch.is_default}
                  className="mr-0 md:mr-3"
                  onClick={() => setDisplayModal(true)}
                  buttonType={BUTTON_TYPES.CANCEL}>
                  Delete
                  <TrashIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </>
          )}
        </div>

        {isLoadingRequest && (
          <div className="">
            <LoadingScreen />
          </div>
        )}

        {detailsContent && !isLoadingRequest && (
          <div className="">
            <pre>{JSON.stringify(detailsContent, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
};
