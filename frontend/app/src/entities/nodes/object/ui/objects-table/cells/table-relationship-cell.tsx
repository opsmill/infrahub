import {
  Node,
  RelationshipManyType,
  RelationshipOneType,
  RelationshipType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import { RelationshipSchema } from "@/entities/schema/types";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";

export interface TableRelationshipCellProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: RelationshipType;
}

export function TableRelationshipCell({
  relationshipSchema,
  relationshipData,
}: TableRelationshipCellProps) {
  if (relationshipSchema.cardinality === "one") {
    const { node } = relationshipData as RelationshipOneType;

    if (!node) return "-";

    return <RelationshipNodeDisplay node={node} />;
  }

  const nodes = (relationshipData as RelationshipManyType).edges
    .map(({ node }) => node)
    .filter((node) => !!node);

  if (!nodes.length) return "-";

  return nodes.map((node) => <RelationshipNodeDisplay key={node.id} node={node} />);
}

export function RelationshipNodeDisplay({ node }: { node: Node }) {
  const { schema } = useSchema(node.__typename);

  return (
    <LinkButton
      variant="outline"
      size="sm"
      to={getObjectDetailsUrl2(node.__typename, node.id)}
      className="rounded-full truncate hover:underline hover:border-custom-blue-700"
    >
      <Icon icon={schema?.icon ?? "mdi:cube-outline"} className="mr-1 text-custom-blue-800" />
      {node.display_label}
    </LinkButton>
  );
}
