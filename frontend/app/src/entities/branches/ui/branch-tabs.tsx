import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";
import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { getBranchDetailsUrl } from "@/entities/branches/utils";

export function BranchTabs() {
  const { branchName } = useRequiredParams("branchName");

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab to={getBranchDetailsUrl(branchName)}>Details</LinkTab>
        <LinkTab to={getBranchDetailsUrl(branchName, "data")}>Data</LinkTab>
        <LinkTab to={getBranchDetailsUrl(branchName, "files")}>Files</LinkTab>
        <LinkTab to={getBranchDetailsUrl(branchName, "artifacts")}>Artifacts</LinkTab>
        <LinkTab to={getBranchDetailsUrl(branchName, "schema")}>Schema</LinkTab>
      </Row>
    </nav>
  );
}
