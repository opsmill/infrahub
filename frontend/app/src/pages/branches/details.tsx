import { useAtomValue } from "jotai";
import { Navigate, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import Content from "@/shared/components/layout/content";
import { Tabs } from "@/shared/components/tabs";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchesState } from "@/entities/branches/stores";
import { BranchDetails } from "@/entities/branches/ui/branch-details";
import { ArtifactsDiff } from "@/entities/diff/artifact-diff/artifacts-diff";
import { FilesDiff } from "@/entities/diff/file-diff/files-diff";
import { NodeDiff } from "@/entities/diff/node-diff";

export const BRANCH_TABS = {
  DETAILS: "details",
  DIFF: "diff",
};

export function BranchDetailsPage() {
  const { "*": branchName } = useParams();
  const branches = useAtomValue(branchesState);
  useTitle(`${branchName} details`);

  if (!branchName) {
    return <Navigate to={constructPath("/branches")} />;
  }

  if (branches.length === 0) {
    return (
      <Content.Card className="flex justify-center items-center p-5 min-h-[400px]">
        <Spinner />
      </Content.Card>
    );
  }

  const branch = branches.find((branch) => branch.name === branchName);

  if (!branch) {
    return <Navigate to={constructPath("/branches")} />;
  }

  return (
    <Content.Card>
      <header className="p-5 font-bold flex gap-2 items-center">
        <h1 className="text-xl">{branch.name}</h1>
        {branch.is_default && <Badge variant="blue-outline">default</Badge>}
      </header>

      <BranchTab />

      <Content.CardContent>
        <BranchContent branchName={branchName} />
      </Content.CardContent>
    </Content.Card>
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
