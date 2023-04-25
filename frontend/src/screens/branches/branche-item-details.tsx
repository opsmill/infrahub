import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Diff } from "./diff/diff";
import { BranchDetails } from "./branch-details";
import { TabsButtons } from "../../components/tabs-buttons";
import { QSP } from "../../config/qsp";
import { constructPath } from "../../utils/fetch";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

const tabs = [
  {
    label: "Details",
    name: BRANCH_TABS.DETAILS
  },
  {
    label: "Diff",
    name: BRANCH_TABS.DIFF
  },
];

const renderContent = (tab: string | null | undefined, branch: any) => {
  switch(tab) {
    case BRANCH_TABS.DIFF: {
      return <Diff />;
    }
    default: {
      return <BranchDetails />;
    }
  }
};

export const BrancheItemDetails = () => {
  const [branch] = useState({} as any);
  const [qspTab] = useQueryParam(QSP.BRANCH_TAB, StringParam);
  const navigate = useNavigate();

  const branchesPath = constructPath("/branches");

  return (
    <>
      <div className="bg-white py-4 px-4 pb-0 w-full">
        <div className="flex items-center">
          <div
            onClick={() => navigate(branchesPath)}
            className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
          >
            <h1 className="text-xl font-semibold text-gray-900 mr-2">Branches</h1>
          </div>

          <p className="mt-2 text-sm text-gray-700 m-0 pl-2 mb-1">Access the branch details and management tools.</p>
        </div>
      </div>

      <TabsButtons tabs={tabs} qsp={QSP.BRANCH_TAB} />

      {
        renderContent(qspTab, branch)
      }
    </>
  );
};