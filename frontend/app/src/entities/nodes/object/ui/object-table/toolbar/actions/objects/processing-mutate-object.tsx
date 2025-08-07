import { UpdateObjectParams } from "@/entities/nodes/object/domain/update-object";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeCore } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import { Card } from "@/shared/components/ui/card";
import { Icon } from "@iconify-icon/react";
import { CheckIcon, RefreshCwIcon } from "lucide-react";
import React from "react";

export interface ProcessingMutateObjectProps {
  schema: ModelSchema;
  node: NodeCore;
  payload: UpdateObjectParams["data"];
  onSuccess?: () => void;
}

export function ProcessingMutateObject({
  schema,
  node,
  payload,
  onSuccess,
}: ProcessingMutateObjectProps) {
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
        onSuccess: () => {
          queryClient.invalidateQueries({
            predicate: (query) =>
              query.queryKey.includes("objects") && query.queryKey.includes(schema.kind),
          });
          onSuccess?.();
        },
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
        <Row className="text-red-600 text-xs cursor-pointer">
          <span>{error.message}</span>
          <div className="bg-red-50 rounded-full p-1 border border-red-200 hover:border-current">
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
        <div className="bg-green-200 rounded-full p-0.5">
          <CheckIcon className="size-3" />
        </div>
      </Row>
    </NodeCard>
  );
}

export function NodeCard({ node, children }: { node: NodeCore; children?: React.ReactNode }) {
  const { schema } = useSchema(node.__typename);

  return (
    <Card className="text-sm w-100">
      <Col className="gap-1">
        <Row className="text-xs text-gray-600 justify-between">
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
