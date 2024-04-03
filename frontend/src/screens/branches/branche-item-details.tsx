import { Link, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { TabsButtons } from "../../components/buttons/tabs-buttons";
import { QSP } from "../../config/qsp";
import { useTitle } from "../../hooks/useTitle";
import { constructPath } from "../../utils/fetch";
import { Diff } from "../diff/diff";
import { BranchDetails } from "./branch-details";
import Content from "../layout/content";
import { Icon } from "@iconify-icon/react";

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
  useTitle(`${branchname} details`);

  return (
    <Content>
      <Content.Title
        title={
          <>
            <Link to={constructPath("/branches")} className="hover:underline">
              Branches
            </Link>
            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />
            <p className="max-w-2xl text-sm text-gray-500 font-normal">{branchname}</p>
          </>
        }
      />

      <TabsButtons tabs={tabs} qsp={QSP.BRANCH_TAB} />

      <div>{renderContent(qspTab)}</div>
    </Content>
  );
};
