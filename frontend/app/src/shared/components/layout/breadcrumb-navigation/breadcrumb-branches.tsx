import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import BreadcrumbBranchSelector from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-branch-selector";
import { Breadcrumb, BreadcrumbItem, BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbBranches() {
  const { "*": branchName } = useParams();

  return (
    <Breadcrumb data-testid="breadcrumb-branches">
      <BreadcrumbSeparator />
      <BreadcrumbItem href={constructPath("/branches")}>Branches</BreadcrumbItem>
      {branchName && (
        <>
          <BreadcrumbSeparator />
          <BreadcrumbBranchSelector currentBranchName={branchName} />
        </>
      )}
    </Breadcrumb>
  );
}
