import { Card, Spinner } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { Navigate, Outlet } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { useRequiredParams } from "@/shared/hooks/use-required-params";
import { useTitle } from "@/shared/hooks/useTitle";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { branchesState } from "@/entities/branches/stores";
import { BranchDetailsHeader } from "@/entities/branches/ui/branch-details/branch-details-header";
import { BranchTabs } from "@/entities/branches/ui/branch-tabs";
import { BranchWorkingNotice } from "@/entities/branches/ui/branch-working-notice";
import type { BranchDetailsOutletContext } from "@/entities/branches/ui/routing/use-branch-details-outlet";

function BranchDetailsLayout() {
  const { branchName } = useRequiredParams("branchName");
  const branches = useAtomValue(branchesState);

  if (branches.length === 0) {
    return (
      <Content.Card className="flex min-h-100 items-center justify-center p-5">
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
      <BranchWorkingNotice branch={branch} />

      <BranchDetailsHeader branch={branch} />

      <Col className="gap-0 p-1">
        {!branch.is_default && <BranchTabs />}
        <Card variant="panel" className="overflow-auto">
          <Outlet context={{ branch } satisfies BranchDetailsOutletContext} />
        </Card>
      </Col>
    </Content.Card>
  );
}

export const Component = BranchDetailsLayout;
