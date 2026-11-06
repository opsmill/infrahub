import { Icon } from "@/shared/components/display/icon";
import { Badge } from "@/shared/components/ui/badge";
import { LinkPill, Pill } from "@/shared/components/ui/link-pill";

import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { isNodeReference } from "@/entities/nodes/object/domain/rules/is-node-reference";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const chipWidthStyle = "min-w-0 max-w-40 shrink-0";

export function NodeElementPill({
  node,
  label,
  isLink = true,
}: {
  node: NodeCore;
  label: string;
  isLink?: boolean;
}) {
  const { schema } = useSchema(node.__typename);
  const content = (
    <>
      {schema && <Icon icon={getSchemaIcon(schema)} className="shrink-0 text-accent" />}
      <span className="truncate" title={label}>
        {label}
      </span>
    </>
  );

  if (!isLink) {
    return (
      <Pill size="xxs" className={chipWidthStyle}>
        {content}
      </Pill>
    );
  }

  return (
    <LinkPill
      size="xxs"
      href={getObjectDetailsUrl(node.__typename, node.id)}
      className={chipWidthStyle}
    >
      {content}
    </LinkPill>
  );
}

/** A list element as a badge, or as a relationship-style pill when it references a node. */
export function ListElementChip({ element, isLink }: { element: ListElement; isLink?: boolean }) {
  if (isNodeReference(element.value)) {
    return <NodeElementPill node={element.value} label={element.text} isLink={isLink} />;
  }

  return (
    <Badge variant="gray" className={`${chipWidthStyle} font-normal`} title={element.text}>
      <span className="truncate">{element.text}</span>
    </Badge>
  );
}
