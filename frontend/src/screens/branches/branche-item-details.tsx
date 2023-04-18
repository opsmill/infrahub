import { formatDistanceToNow } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge } from "../../components/badge";
import { Pill } from "../../components/pill";
import getBranchDetails from "../../graphql/queries/branches/getBranchDetails";
import LoadingScreen from "../loading-screen/loading-screen";
import { DataDiff } from "./diff/data-diff";
import { Tabs } from "../../components/tabs";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/constants";
import { BRANCH_TABS, BranchAction } from "./actions/branch-action";

const tabs = [
  {
    label: "Diff",
    name: BRANCH_TABS.DIFF
  },
  {
    label: "Merge",
    name: BRANCH_TABS.MERGE
  },
  {
    label: "Pull Request",
    name: BRANCH_TABS.PR
  },
  {
    label: "Pull Request",
    name: BRANCH_TABS.REBASE
  },
  {
    label: "Validate",
    name: BRANCH_TABS.VALIDATE
  },
  {
    label: "Delete",
    name: BRANCH_TABS.DELETE
  },
];

const renderContent = (tab: string | null | undefined, branch: any) => {
  switch(tab) {
    case BRANCH_TABS.MERGE:
    case BRANCH_TABS.PR:
    case BRANCH_TABS.VALIDATE:
    case BRANCH_TABS.REBASE:
    case BRANCH_TABS.DELETE: {
      return <BranchAction branch={branch} />;
    }
    default: {
      return <DataDiff />;
    }
  }
};

export const BrancheItemDetails = () => {
  const { branchname } = useParams();

  const [branch, setBranch] = useState({} as any);
  const [isLoadingBranch, setIsLoadingBranch] = useState(true);
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const navigate = useNavigate();

  const fetchBranchDetails = useCallback(
    async () => {
      if (!branchname) return;

      try {
        const branchDetails = await getBranchDetails(branchname);

        if (!branchDetails?.name) {
          navigate("/branches");
        }

        setBranch(branchDetails);
        setIsLoadingBranch(false);
      } catch(err) {
        console.error("err: ", err);
        setIsLoadingBranch(false);
      }
    }, [branchname, navigate]
  );

  useEffect(
    () => {
      fetchBranchDetails();
    },
    [fetchBranchDetails]
  );

  return (
    <>
      <div className="bg-white sm:flex sm:items-center py-4 px-4 pb-0 sm:px-6 lg:px-8 w-full">
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

      <div className="bg-white p-6">
        {
          isLoadingBranch
          && <LoadingScreen />
        }

        {
          !isLoadingBranch
          && branch?.name
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

            </>
          )
        }
      </div>

      <Tabs tabs={tabs} />

      {
        renderContent(qspTab, branch)
      }
    </>
  );
};