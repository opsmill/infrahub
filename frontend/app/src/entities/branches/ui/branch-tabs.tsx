import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";
import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { getBranchDetailsUrl } from "@/entities/branches/utils";

export function BranchTabs() {
  const { branchName } = useRequiredParams("branchName");

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab href={getBranchDetailsUrl(branchName)}>Details</LinkTab>
        <LinkTab href={getBranchDetailsUrl(branchName, "data")}>Data</LinkTab>
        <LinkTab href={getBranchDetailsUrl(branchName, "files")}>Files</LinkTab>
        <LinkTab href={getBranchDetailsUrl(branchName, "artifacts")}>Artifacts</LinkTab>
        <LinkTab href={getBranchDetailsUrl(branchName, "schema")}>Schema</LinkTab>
      </Row>
    </nav>
  );
}
