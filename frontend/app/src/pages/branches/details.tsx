import { Tabs } from "@/components/tabs";
import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { NodeDiff } from "@/screens/diff/node-diff";

import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import Content from "@/screens/layout/content";
import { constructPath } from "@/utils/fetch";
import { BranchDetails } from "@/screens/branches/branch-details";
import { Navigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { useTitle } from "@/hooks/useTitle";
import React from "react";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

export function BranchDetailsPage() {
  const { "*": branchName } = useParams();
  useTitle(`${branchName} details`);

  if (!branchName) {
    return <Navigate to={constructPath("/branches")} />;
  }

  return (
    <Content>
      <Content.Title title={<div>Branch - {branchName}</div>} />

      <BranchTab />

      <BranchContent branchName={branchName} />
    </Content>
  );
}

const BranchTab = () => {
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

  return <Tabs tabs={tabs} qsp={QSP.BRANCH_TAB} />;
};

const BranchContent = ({ branchName }: { branchName: string }) => {
  const [currentTab] = useQueryParam(QSP.BRANCH_TAB, StringParam);

  switch (currentTab) {
    case DIFF_TABS.FILES: {
      return <FilesDiff />;
    }
    case DIFF_TABS.ARTIFACTS: {
      return <ArtifactsDiff />;
    }
    case DIFF_TABS.SCHEMA: {
      return (
        <NodeDiff
          branchName={branchName}
          filters={{
            namespace: { includes: ["Schema"], excludes: ["Profile"] },
            status: { excludes: ["UNCHANGED"] },
          }}
        />
      );
    }
    case DIFF_TABS.DATA: {
      return (
        <NodeDiff
          branchName={branchName}
          filters={{
            namespace: { excludes: ["Schema", "Profile"] },
            status: { excludes: ["UNCHANGED"] },
          }}
        />
      );
    }
    default: {
      return <BranchDetails />;
    }
  }
};

export const Component = BranchDetailsPage;
