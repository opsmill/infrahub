import { Tabs } from "@/components/tabs";
import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { NodeDiff } from "@/screens/diff/node-diff";

import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import Content from "@/screens/layout/content";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { BranchDetails } from "@/screens/branches/branch-details";
import { Link, Navigate, useMatches, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { useTitle } from "@/hooks/useTitle";
import { Button } from "@/components/buttons/button-primitive";
import React from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAtomValue } from "jotai";
import { branchesState } from "@/state/atoms/branches.atom";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

export function BranchDetailsPage() {
  const { "*": branchName } = useParams();
  const matches = useMatches();
  console.log(matches);
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

const BranchSelectorBreadcrumb = ({ branchName }: { branchName: string }) => {
  const branches = useAtomValue(branchesState);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="inline-flex gap-2 justify-between -ml-2">
          {branchName}
          <Icon icon="mdi:unfold-more-horizontal" className="text-gray-300" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent>
        {branches.map((branch) => (
          <DropdownMenuItem key={branch.name} asChild>
            <Link to={constructPath(`/branches/${branch.name}`, undefined, [QSP.BRANCH_TAB])}>
              {branch.name}
            </Link>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

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
