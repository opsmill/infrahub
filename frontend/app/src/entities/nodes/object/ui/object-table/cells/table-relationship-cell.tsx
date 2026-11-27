import { Icon } from "@/shared/components/display/icon";
import { LinkPill, type LinkPillProps, Pill } from "@/shared/components/ui/link-pill";

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

export interface RelationshipNodeDisplayProps {
  node: NodeCore;
  size?: LinkPillProps["size"];
  isLink?: boolean;
  className?: string;
}

export function RelationshipNodeDisplay({
  node,
  size = "sm",
  isLink = true,
  className = "min-w-0 shrink",
}: RelationshipNodeDisplayProps) {
  const { schema } = useSchema(node.__typename);

  if (!schema) return `Schema for ${node.__typename} not found`;

  const label = getNodeLabel(node);
  const content = (
    <>
      <Icon icon={getSchemaIcon(schema)} className="shrink-0 text-accent" />
      <span className="truncate" title={label}>
        {label}
      </span>
    </>
  );

  if (!isLink) {
    return (
      <Pill size={size} className={className}>
        {content}
      </Pill>
    );
  }

  return (
    <LinkPill
      href={getObjectDetailsUrl(node.__typename, node.id)}
      size={size}
      className={className}
    >
      {content}
    </LinkPill>
  );
}
