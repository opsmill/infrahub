import { Icon } from "@iconify-icon/react";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import { Card } from "@/shared/components/ui/card";

import type { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

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
    </Card>
  );
}
