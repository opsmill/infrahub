import { Card, CardContent } from "@infrahub/ui";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import type { UpdateObjectParams } from "@/entities/nodes/object/domain/use-cases/update-object";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ProcessingMutateObjectProps {
  node: NodeCore;
  payload: UpdateObjectParams["data"];
  onSuccess?: () => void;
}

export function ProcessingMutateObject({ node, payload, onSuccess }: ProcessingMutateObjectProps) {
  const { mutate, isPending, error } = useUpdateObjectMutation();

  const handleProcessing = () => {
    mutate(
      {
        objectKind: node.__typename,
        data: {
          id: node.id,
          ...payload,
        },
      },
      {
        onSuccess,
      }
    );
  };

  React.useEffect(() => {
    handleProcessing();
  }, []);

  if (isPending) {
    return <NodeCard node={node}>updating...</NodeCard>;
  }

  if (error) {
    return (
      <NodeCard node={node}>
        <Row className="cursor-pointer text-red-600 text-xs">
          <span>{error.message}</span>
          <div className="rounded-full border border-red-200 bg-red-50 p-1 hover:border-current">
            <RefreshCwIcon className="size-2.5" onClick={() => handleProcessing()} />
          </div>
        </Row>
      </NodeCard>
    );
  }

  return (
    <NodeCard node={node}>
      <Row className="text-green-800">
        success
        <div className="rounded-full bg-green-200 p-0.5">
          <CheckIcon className="size-3" />
        </div>
      </Row>
    </NodeCard>
  );
}

export function NodeCard({ node, children }: { node: NodeCore; children?: React.ReactNode }) {
  const { schema } = useSchema(node.__typename);

  return (
    <Card className="w-100 text-sm">
      <CardContent>
        <Col className="gap-1">
          <Row className="justify-between text-gray-600 text-xs">
            <Row className="gap-1">
              <Icon icon={getSchemaIcon(schema)} />
              <span>{schema?.label}</span>
            </Row>

            <span className="truncate">ID {node.id}</span>
          </Row>
          <Row className="justify-between">
            <span className="shrink-0">{getNodeLabel(node)}</span>
            <span>{children}</span>
          </Row>
        </Col>
      </CardContent>
    </Card>
  );
}
