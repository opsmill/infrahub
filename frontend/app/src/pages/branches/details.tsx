import { Spinner } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { Navigate, Outlet, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { branchesState } from "@/entities/branches/stores";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { BranchTabs } from "@/entities/branches/ui/branch-tabs";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";

function BranchDetailsLayout() {
  const { branchName } = useParams() as { branchName: string };
  const branches = useAtomValue(branchesState);
  useTitle(`${branchName} details`);

  if (!branchName) {
    return <Navigate to={constructPath("/branches")} />;
  }

  if (branches.length === 0) {
    return (
      <Content.Card className="flex min-h-[400px] items-center justify-center p-5">
        <Spinner />
      </Content.Card>
    );
  }

  const branch = branches.find((b) => b.name === branchName);

  if (!branch) {
    return <Navigate to={constructPath("/branches")} />;
  }

  return (
    <Content.Card>
      <header className="p-5 pb-2">
        <Row>
          <h1 className="font-bold text-xl">{branch.name}</h1>
          <NodeMetadataPopover objectKind="InfrahubBranch" objectId={branch.id} />
          {branch.is_default ? (
            <BranchDefaultBadge className="text-sm" />
          ) : (
            <BranchStatusBadge status={branch.status} className="text-sm" />
          )}
        </Row>
        {branch.description && <p className="text-sm">{branch.description}</p>}
      </header>

      {!branch.is_default && <BranchTabs />}

      <div className="p-2">
        <Outlet />
      </div>
    </Content.Card>
  );
}

export const Component = BranchDetailsLayout;
