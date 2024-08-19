import Accordion, { EmptyAccordion } from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffTitle } from "./utils";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { useParams } from "react-router-dom";

type DiffNodeProps = {
  node: any;
};

export const DiffNode = ({ node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();
  console.log("node: ", node);
  const title = (
    <DiffTitle containsConflict={node.contains_conflict} status={node.status}>
      <div className="flex items-center">
        <Badge variant={"white"}>{node.kind}</Badge>

        {node.label && (
          <BadgeCircle type={CIRCLE_BADGE_TYPES.GHOST}>
            <span className="mr-2 text-sm">{node.label}</span>
            <CopyToClipboard text={node.label} />
          </BadgeCircle>
        )}

        {!branchName && node.path_identifier && <DiffThread path={node.path_identifier} />}
      </div>
    </DiffTitle>
  );

  return (
    <Card className="m-4">
      <div className="bg-gray-100 rounded-md border overflow-hidden">
        {(node.attributes?.length || node.relationships?.length) && (
          <Accordion title={title}>
            <div className="bg-custom-white">
              {node.attributes.map((attribute: any, index: number) => (
                <DiffNodeAttribute key={index} attribute={attribute} />
              ))}
              {node.relationships.map((relationship: any, index: number) => (
                <DiffNodeRelationship key={index} relationship={relationship} />
              ))}
            </div>
          </Accordion>
        )}

        {!node.attributes?.length && !node.relationships?.length && (
          <EmptyAccordion title={title} />
        )}
      </div>
    </Card>
  );
};
