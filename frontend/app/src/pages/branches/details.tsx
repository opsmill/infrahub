import { Spinner } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { Navigate, Outlet } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useRequiredParams } from "@/shared/hooks/use-required-params";
import { useTitle } from "@/shared/hooks/useTitle";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { branchesState } from "@/entities/branches/stores";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { BranchTabs } from "@/entities/branches/ui/branch-tabs";
import type { BranchDetailsOutletContext } from "@/entities/branches/ui/use-branch-details-outlet";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";

function BranchDetailsLayout() {
  const { branchName } = useRequiredParams("branchName");
  const branches = useAtomValue(branchesState);

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

  return <BranchDetailsContent branch={branch} />;
}

function BranchDetailsContent({ branch }: { branch: BranchListItem }) {
  useTitle(`${branch.name} details`);

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
        <Outlet context={{ branch } satisfies BranchDetailsOutletContext} />
      </div>
    </Content.Card>
  );
}

export const Component = BranchDetailsLayout;
