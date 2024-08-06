import Accordion, { EmptyAccordion } from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { BadgeAdd, BadgeRemove, BadgeType, BadgeUnchange, BadgeUpdate } from "../ui/badge";
import { Badge } from "@/components/ui/badge";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { capitalizeFirstLetter } from "@/utils/string";
import { DiffNodeRelationship } from "./node-relationship";
import { useParams } from "react-router-dom";
import { DiffThread } from "./thread";

const diffBadges: { [key: string]: BadgeType } = {
  ADDED: BadgeAdd,
  UPDATED: BadgeUpdate,
  REMOVED: BadgeRemove,
  UNCHANGED: BadgeUnchange,
};

type DiffNodeProps = {
  node: any;
};

export const DiffNode = ({ node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();

  const DiffBadge = diffBadges[node.status];

  const title = (
    <div className="flex items-center gap-2 relative group">
      <div>
        <DiffBadge conflicts={node.contains_conflict}>
          {capitalizeFirstLetter(node.status)}
        </DiffBadge>
      </div>

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

      {!branchName && <DiffThread path={`data/${node.id}`} />}
    </div>
  );

  return (
    <Card className="m-4">
      <div className="bg-gray-100 rounded-md border">
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
