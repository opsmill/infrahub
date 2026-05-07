import { useParams } from "react-router";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function BranchTabs() {
  const { branchName } = useParams() as { branchName: string };
  const base = `/branches/${branchName}`;

  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab href={base}>Details</LinkTab>
        <LinkTab href={`${base}/data`}>Data</LinkTab>
        <LinkTab href={`${base}/files`}>Files</LinkTab>
        <LinkTab href={`${base}/artifacts`}>Artifacts</LinkTab>
        <LinkTab href={`${base}/schema`}>Schema</LinkTab>
      </Row>
    </nav>
  );
}
