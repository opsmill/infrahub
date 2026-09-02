import { Icon } from "@/shared/components/display/icon";
import { LinkPill } from "@/shared/components/ui/link-pill";

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
    <LinkPill href={getObjectDetailsUrl(node.__typename, node.id)} className="min-w-0 shrink">
      <Icon icon={getSchemaIcon(schema)} className="shrink-0 text-accent" />
      <span className="truncate">{getNodeLabel(node)}</span>
    </LinkPill>
  );
}
