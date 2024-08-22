import Accordion from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";

type DiffNodeProps = {
  node: any;
  sourceBranch: string;
  destinationBranch: string;
};

export const DiffNode = ({ sourceBranch, destinationBranch, node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();
  const schemaKindName = useAtomValue(schemaKindNameState);

  return (
    <Card>
      {(!!node.attributes?.length || !!node.relationships?.length) && (
        <Accordion
          title={
            <div className="group grid grid-cols-3 justify-items-end gap-2 p-1 text-xs">
              <div className="flex items-center gap-2 justify-self-start">
                <DiffBadge status={node.status} hasConflicts={node.contains_conflict} />
                <Badge variant="white">{schemaKindName[node.kind]}</Badge>
                <span className="text-gray-800 font-medium px-2 py-1">{node.label}</span>
                {!branchName && node.path_identifier && <DiffThread path={node.path_identifier} />}
              </div>

              <Badge variant="green" className="bg-transparent">
                <Icon icon="mdi:layers-triple" className="mr-1" /> {sourceBranch}
              </Badge>

              <Badge variant="blue" className="bg-transparent">
                <Icon icon="mdi:layers-triple" className="mr-1" /> {destinationBranch}
              </Badge>
            </div>
          }
          className="bg-gray-100 border rounded-md">
          <div className="divide-y border-t">
            {node.attributes.map((attribute: any, index: number) => (
              <DiffNodeAttribute key={index} attribute={attribute} />
            ))}
            {node.relationships.map((relationship: any, index: number) => (
              <DiffNodeRelationship key={index} relationship={relationship} />
            ))}
          </div>
        </Accordion>
      )}
    </Card>
  );
};
