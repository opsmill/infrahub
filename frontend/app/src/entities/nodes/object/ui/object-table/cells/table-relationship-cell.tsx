import { LinkButton } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";

import type {
  NodeCore,
  NodeRelationship,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
      href={getObjectDetailsUrl(node.__typename, node.id)}
      className="truncate rounded-full pr-2.5 hover:border-custom-blue-700 hover:underline"
    >
      <Icon icon={getSchemaIcon(schema)} className="text-custom-blue-800" />
      {getNodeLabel(node)}
    </LinkButton>
  );
}
