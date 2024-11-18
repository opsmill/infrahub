import { Tabs } from "@/components/tabs";
import { DIFF_TABS } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { ArtifactsDiff } from "@/screens/diff/artifact-diff/artifacts-diff";
import { NodeDiff } from "@/screens/diff/node-diff";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useTitle } from "@/hooks/useTitle";
import { BranchDetails } from "@/screens/branches/branch-details";
import { FilesDiff } from "@/screens/diff/file-diff/files-diff";
import Content from "@/screens/layout/content";
import { branchesState } from "@/state/atoms/branches.atom";
import { constructPath } from "@/utils/fetch";
import { useAtomValue } from "jotai";
import { Navigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";

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
