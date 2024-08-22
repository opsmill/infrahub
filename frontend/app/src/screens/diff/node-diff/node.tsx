import Accordion, { EmptyAccordion } from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/components/display/badge-circle";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { DiffNodeRelationship } from "./node-relationship";
import { diffBadges, DiffTitle } from "./utils";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { capitalizeFirstLetter } from "@/utils/string";
import { DiffBadgeProps } from "@/screens/diff/diff-badge";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";

type DiffNodeProps = {
  node: any;
  sourceBranch: string;
  destinationBranch: string;
};

export const DiffNode = ({ sourceBranch, destinationBranch, node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <DiffTitle containsConflict={node.contains_conflict} status={node.status}>
      <div className="flex items-center">
        <Badge variant="white">{node.kind}</Badge>

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
    <Card>
      {(!!node.attributes?.length || !!node.relationships?.length) && (
        <Accordion
          title={
            <div className="grid grid-cols-3 justify-items-start gap-2 p-1 text-xs">
              <div className="flex items-center gap-1">
                <DiffBadge status={node.status} hasConflicts={node.contains_conflict} />
                <Badge variant="white">{node.kind}</Badge>
                <span className="text-gray-800 font-medium px-2">{node.label}</span>
              </div>

              <span>
                <Badge variant="green">
                  <Icon icon="mdi:layers-triple" /> {sourceBranch}
                </Badge>
              </span>

              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" /> {destinationBranch}
              </Badge>
            </div>
          }
          className="bg-gray-100 border rounded-md">
          {node.attributes.map((attribute: any, index: number) => (
            <DiffNodeAttribute key={index} attribute={attribute} />
          ))}
          {node.relationships.map((relationship: any, index: number) => (
            <DiffNodeRelationship key={index} relationship={relationship} />
          ))}
        </Accordion>
      )}

      {!node.attributes?.length && !node.relationships?.length && <EmptyAccordion title={title} />}
    </Card>
  );
};

const DiffBadge = ({ status, ...props }: DiffBadgeProps & { status: string }) => {
  const DiffBadgeComp = diffBadges[status];

  if (!DiffBadgeComp) {
    return null;
  }

  return <DiffBadgeComp {...props}>{capitalizeFirstLetter(status)}</DiffBadgeComp>;
};
