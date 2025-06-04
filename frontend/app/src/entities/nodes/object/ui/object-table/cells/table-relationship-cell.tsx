import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import {
  NodeCore,
  NodeRelationship,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";

export interface TableRelationshipCellProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: NodeRelationship;
}

export function TableRelationshipCell({
  relationshipSchema,
  relationshipData,
}: TableRelationshipCellProps) {
  if (relationshipSchema.cardinality === "one") {
    const { node } = relationshipData as NodeRelationshipOne;

    if (!node) return "-";

    return <RelationshipNodeDisplay node={node} />;
  }

  const nodes = (relationshipData as NodeRelationshipMany).edges
    .map(({ node }) => node)
    .filter((node) => !!node);

  if (!nodes.length) return "-";

  return nodes.map((node) => <RelationshipNodeDisplay key={node.id} node={node} />);
}

export function RelationshipNodeDisplay({ node }: { node: NodeCore }) {
  const { schema } = useSchema(node.__typename);

  if (!schema) return `Schema for ${node.__typename} not found`;

  return (
    <LinkButton
      variant="outline"
      size="sm"
      to={getObjectDetailsUrl(node.__typename, node.id)}
      className="rounded-full truncate hover:underline hover:border-custom-blue-700 pr-2.5"
    >
      <Icon icon={getSchemaIcon(schema)} className="mr-1 text-custom-blue-800" />
      {getNodeLabel(node)}
    </LinkButton>
  );
}
