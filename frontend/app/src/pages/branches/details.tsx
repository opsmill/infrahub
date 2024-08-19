import { Tabs } from "@/components/tabs";
import { Link } from "@/components/ui/link";
import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { useTitle } from "@/hooks/useTitle";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { NodeDiff } from "@/screens/diff/node-diff";

import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import Content from "@/screens/layout/content";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { BranchDetails } from "@/screens/branches/branch-details";
import { Status } from "@/screens/proposed-changes/diff-summary";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

const ProposedChangesDetailsPage = () => {
  const { "*": branchName } = useParams();
  const [qspTab] = useQueryParam(QSP.BRANCH_TAB, StringParam);
  useTitle(`${branchName} details`);

  const tabs = [
    {
      label: "Details",
      name: BRANCH_TABS.DETAILS,
    },
    {
      label: "Data",
      name: DIFF_TABS.DATA,
    },
    {
      label: "Files",
      name: DIFF_TABS.FILES,
    },

    {
      label: "Schema",
      name: DIFF_TABS.SCHEMA,
    },
  ];

  const renderContent = () => {
    switch (qspTab) {
      case DIFF_TABS.FILES:
        return <FilesDiff />;
      case DIFF_TABS.ARTIFACTS:
        return <ArtifactsDiff />;
      case DIFF_TABS.SCHEMA:
        return (
          <NodeDiff
            filters={{
              namespace: { includes: ["Schema"], excludes: ["Profile"] },
              status: { excludes: ["UNCHANGED"] },
            }}
          />
        );
      case DIFF_TABS.DATA:
        return (
          <NodeDiff
            filters={{
              namespace: { excludes: ["Schema", "Profile"] },
              status: { excludes: [Status.UNCHANGED] },
            }}
          />
        );
      default: {
        return <BranchDetails />;
      }
    }
  };

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-1">
            <Link to={constructPath("/branches")} className="hover:underline">
              Branches
            </Link>
            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />
            <p className="max-w-2xl text-sm text-gray-500 font-normal">{branchName}</p>
          </div>
        }
      />

      <Tabs tabs={tabs} qsp={QSP.BRANCH_TAB} />

      <div>{renderContent()}</div>
    </Content>
  );
};

export function Component() {
  return <ProposedChangesDetailsPage />;
}
