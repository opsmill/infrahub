import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import BreadcrumbBranchSelector from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-branch-selector";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbBranches() {
  const { "*": branchName } = useParams();

  return (
    <Breadcrumb data-testid="breadcrumb-branches">
      <BreadcrumbItem href={constructPath("/branches")}>Branches</BreadcrumbItem>
      {branchName && <BreadcrumbBranchSelector currentBranchName={branchName} />}
    </Breadcrumb>
  );
}
