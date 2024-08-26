import Accordion from "@/components/display/accordion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DiffNodeRelationship } from "./node-relationship";
import { DiffNodeAttribute } from "./node-attribute";
import { DiffThread } from "./thread";
import { Icon } from "@iconify-icon/react";
import { useLocation, useParams } from "react-router-dom";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { useAtomValue } from "jotai";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import type { DiffNode as DiffNodeType } from "@/screens/diff/node-diff/types";
import { classNames } from "@/utils/common";
import { useEffect, useRef } from "react";

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
            <div className="group grid grid-cols-3 justify-items-end gap-2 py-2 pr-2 text-xs">
              <div className="flex w-full items-center justify-between gap-2 justify-self-start">
                <div className="flex items-center gap-2">
                  <DiffBadge status={node.status} hasConflicts={node.contains_conflict} />
                  <Badge variant="white">{schemaKindName[node.kind]}</Badge>
                  <span className="text-gray-800 font-medium px-2 py-1">{node.label}</span>
                </div>

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
