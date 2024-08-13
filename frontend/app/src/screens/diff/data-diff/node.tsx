import Accordion, { EmptyAccordion } from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffTitle } from "./utils";

type DiffNodeProps = {
  node: any;
};

export const DiffNode = ({ node }: DiffNodeProps) => {
  const title = (
    <DiffTitle id={node.id} containsConflict={node.contains_conflict} status={node.status}>
      <div className="flex items-center">
        <div>
          <Badge variant={"white"}>{node.kind}</Badge>
        </div>

        <div className="text-sm">
          {node.label && (
            <BadgeCircle type={CIRCLE_BADGE_TYPES.GHOST}>
              <span className="mr-2">{node.label}</span>
              <CopyToClipboard text={node.label} />
            </BadgeCircle>
          )}
        </div>
      </div>
    </DiffTitle>
  );

  return (
    <Card className="m-4">
      <div className="bg-gray-100 rounded-md border overflow-hidden">
        {!!node.relationships.length && (
          <Accordion title={title}>
            {node.relationships.map((relationship: any, index: number) => (
              <DiffNodeRelationship key={index} relationship={relationship} />
            ))}
          </Accordion>
        )}

        {!node.relationships.length && <EmptyAccordion title={title} />}
      </div>
    </Card>
  );
};
