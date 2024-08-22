import Accordion from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import React from "react";
import { DiffBadge } from "@/screens/diff/node-diff/utils";

type DiffNodeProps = {
  node: any;
  sourceBranch: string;
  destinationBranch: string;
};

export const DiffNode = ({ sourceBranch, destinationBranch, node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();

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
                {!branchName && node.path_identifier && <DiffThread path={node.path_identifier} />}
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
    </Card>
  );
};
