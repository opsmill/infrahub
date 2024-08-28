import Accordion from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { useLocation, useParams } from "react-router-dom";
import { DiffBadge, formatValue } from "@/screens/diff/node-diff/utils";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import type { DiffNode as DiffNodeType } from "@/screens/diff/node-diff/types";
import { classNames } from "@/utils/common";
import { useEffect, useRef } from "react";
import { Icon } from "@iconify-icon/react";

type DiffNodeProps = {
  node: DiffNodeType;
  sourceBranch: string;
  destinationBranch: string;
};

export const DiffNode = ({ sourceBranch, destinationBranch, node }: DiffNodeProps) => {
  const { "*": branchName } = useParams();
  const schemaKindName = useAtomValue(schemaKindNameState);
  const { hash } = useLocation();
  const diffNodeRef = useRef<HTMLDivElement>(null);

  const isSelectedOnNavigation = hash === `#${node.uuid}`;

  useEffect(() => {
    if (isSelectedOnNavigation && diffNodeRef?.current) {
      diffNodeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [hash]);

  return (
    <Card
      ref={diffNodeRef}
      id={node.uuid}
      className={classNames(isSelectedOnNavigation && "ring-2 ring-custom-blue-500")}>
      {(!!node.attributes?.length || !!node.relationships?.length) && (
        <Accordion
          defaultOpen={isSelectedOnNavigation}
          title={
            <div className="group flex items-center gap-2 py-2 pr-2 text-xs">
              <DiffBadge status={node.status} hasConflicts={node.contains_conflict} />
              <Badge variant="white">{schemaKindName[node.kind] ?? node.kind}</Badge>
              <span className="text-gray-800 font-medium px-2 py-1">{node.label}</span>

              {!branchName && node.path_identifier && <DiffThread path={node.path_identifier} />}
            </div>
          }
          className="bg-gray-100 border rounded-md">
          <div className="divide-y border-t">
            <div className="bg-custom-white grid grid-cols-3 pl-8">
              <Badge variant="green" className="bg-transparent col-start-2 col-end-3">
                <Icon icon="mdi:layers-triple" className="mr-1" /> {sourceBranch}
              </Badge>

              <Badge variant="blue" className="bg-transparent">
                <Icon icon="mdi:layers-triple" className="mr-1" /> {destinationBranch}
              </Badge>
            </div>

            {node.attributes.map((attribute: any, index: number) => {
              const valueProperty = attribute.properties.find(
                ({ property_type }) => property_type === "HAS_VALUE"
              );

              return (
                <DiffNodeAttribute
                  key={index}
                  attribute={attribute}
                  status={node.status}
                  previousValue={
                    valueProperty?.previous_value && formatValue(valueProperty?.previous_value)
                  }
                  newValue={status !== "REMOVED" && formatValue(valueProperty?.new_value)}
                />
              );
            })}

            {node.relationships.map((relationship: any, index: number) => {
              if (relationship.cardinality === "ONE") {
                const element = relationship.elements[0];

                const attribute = {
                  ...relationship,
                  path_identifier: relationship.path_identifier,
                  properties: element.properties,
                };

                return (
                  <DiffNodeAttribute
                    key={index}
                    attribute={attribute}
                    status={node.status}
                    previousValue={"-"}
                    newValue={element.peer_label}
                  />
                );
              }

              return (
                <DiffNodeRelationship
                  key={index}
                  relationship={relationship}
                  status={node.status}
                />
              );
            })}
          </div>
        </Accordion>
      )}
    </Card>
  );
};
