import { TabsButtons } from "@/components/buttons/tabs-buttons";
import { QSP } from "@/config/qsp";
import { useTitle } from "@/hooks/useTitle";
import { BranchDetails } from "@/screens/branches/branch-details";
import { Diff } from "@/screens/diff/diff";
import Content from "@/screens/layout/content";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

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

const BranchItemDetails = () => {
  const { branchname } = useParams();
  const [qspTab, setQspTab] = useQueryParam(QSP.BRANCH_TAB, StringParam);
  useTitle(`${branchname} details`);

  const tabs = [
    {
      label: "Details",
      name: BRANCH_TABS.DETAILS,
    },
    {
      label: "Diff",
      name: BRANCH_TABS.DIFF,
      disabled: branchname === "main",
    },
  ];

  if (qspTab === BRANCH_TABS.DIFF && branchname === "main") {
    // Prevent dif access for main branch, when loading the url
    setQspTab(undefined);
  }

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-1">
            <Link to={constructPath("/branches")} className="hover:underline">
              Branches
            </Link>
            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />
            <p className="max-w-2xl text-sm text-gray-500 font-normal">{branchname}</p>
          </div>
        }
      />

      <TabsButtons tabs={tabs} qsp={QSP.BRANCH_TAB} />

      <div>{renderContent(qspTab)}</div>
    </Content>
  );
};

export default BranchItemDetails;
