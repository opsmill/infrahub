import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";
import BreadcrumbBranchSelector from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-branch-selector";

export function BreadcrumbBranches() {
  const { "*": branchName } = useParams();

  return (
    <Breadcrumbs data-testid="breadcrumb-branches">
      <BreadcrumbItem href={constructPath("/branches")}>Branches</BreadcrumbItem>
      {branchName && <BreadcrumbBranchSelector currentBranchName={branchName} />}
    </Breadcrumbs>
  );
}
