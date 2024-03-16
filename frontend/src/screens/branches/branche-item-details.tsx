import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { TabsButtons } from "../../components/buttons/tabs-buttons";
import { QSP } from "../../config/qsp";
import { useTitle } from "../../hooks/useTitle";
import { constructPath } from "../../utils/fetch";
import { Diff } from "../diff/diff";
import { BranchDetails } from "./branch-details";
import Content from "../layout/content";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

const tabs = [
  {
    label: "Details",
    name: BRANCH_TABS.DETAILS,
  },
  {
    label: "Diff",
    name: BRANCH_TABS.DIFF,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    case BRANCH_TABS.DIFF: {
      return <Diff />;
    }
    default: {
      return <BranchDetails />;
    }
  }
};

export const BrancheItemDetails = () => {
  const { branchname } = useParams();
  const [qspTab] = useQueryParam(QSP.BRANCH_TAB, StringParam);
  const navigate = useNavigate();
  useTitle(`${branchname} details`);

  const branchesPath = constructPath("/branches");

  return (
    <>
      <div className="bg-custom-white py-4 px-4 pb-0 w-full">
        <div className="flex items-center">
          <div
            onClick={() => navigate(branchesPath)}
            className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
            Branches
          </div>
          <ChevronRightIcon
            className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
            aria-hidden="true"
          />

          <p className="mt-1 max-w-2xl text-sm text-gray-500">{branchname}</p>
        </div>
      </div>

      <TabsButtons tabs={tabs} qsp={QSP.BRANCH_TAB} />

      <Content>{renderContent(qspTab)}</Content>
    </>
  );
};
