// PROTOTYPE design-jam schema-viewer-sections
// Copy of the production field accordion with a slot after the title; revisions never edit it.
import { type ReactNode, useEffect, useRef } from "react";

import type { components } from "@/shared/api/rest/types.generated";
import { Icon } from "@/shared/components/display/icon";
import { Badge } from "@/shared/components/ui/badge";
import { warnUnexpectedType } from "@/shared/utils/common";

import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { AccordionStyled, PropertyRow, SchemaKindDisplay } from "@/entities/schema/ui/styled";

export const ProtoRelationshipDisplay = ({
  extra,
  relationship,
  onKindClick,
  defaultOpen = false,
}: {
  relationship: RelationshipSchema;
  onKindClick?: (kind: string) => void;
  defaultOpen?: boolean;
  extra?: ReactNode;
}) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (defaultOpen && ref.current) {
      ref.current.scrollIntoView({ behavior: "instant", block: "start" });
    }
  }, [defaultOpen]);

  const cardinalityLabel = relationship.cardinality
    ? getLabelForCardinality(relationship.cardinality)
    : null;

  const directionLabel = relationship.direction
    ? getLabelForDirection(relationship.direction)
    : null;

  return (
    <AccordionStyled
      ref={ref}
      title={
        <span className="inline-flex flex-wrap items-center gap-x-1.5">
          {relationship.label || relationship.name}
          {extra}
        </span>
      }
      kind={
        <>
          <span className="flex items-center gap-0.5">
            {cardinalityLabel} {directionLabel} {relationship.peer}
          </span>
          <Badge variant="blue" className="ml-1 px-1">
            {relationship.kind}
          </Badge>
        </>
      }
      description={relationship.description}
      isOptional={relationship.optional}
      defaultOpen={defaultOpen}
    >
      <div>
        <PropertyRow title="ID" value={relationship.id} />
        <PropertyRow title="Label" value={relationship.label} />
        <PropertyRow title="Name" value={relationship.name} />
      </div>

      <div>
        <PropertyRow
          title="Peer"
          value={<SchemaKindDisplay kinds={[relationship.peer]} onKindClick={onKindClick} />}
        />
        <PropertyRow title="Peer identifier" value={relationship.identifier} />
        <PropertyRow title="Common parent" value={relationship.common_parent} />
        <PropertyRow title="Cardinality" value={relationship.cardinality} />
        <PropertyRow title="Direction" value={relationship.direction} />
        <PropertyRow title="Kind" value={relationship.kind} />
        <PropertyRow title="Hierarchical" value={relationship.hierarchical} />
        <PropertyRow title="Inherited" value={relationship.inherited} />
        <PropertyRow title="On delete" value={relationship.on_delete} />
      </div>

      <div>
        <PropertyRow title="Branch" value={relationship.branch} />
        <PropertyRow title="Max count" value={relationship.max_count} />
        <PropertyRow title="Min count" value={relationship.min_count} />
        <PropertyRow title="Display" value={relationship.display} />
        <PropertyRow title="Container" value={relationship.container ?? "-"} />
        <PropertyRow title="Order weight" value={relationship.order_weight} />
      </div>
    </AccordionStyled>
  );
};

function getLabelForCardinality(cardinality: components["schemas"]["RelationshipCardinality"]) {
  switch (cardinality) {
    case "many":
      return "N";
    case "one":
      return "1";
    default:
      warnUnexpectedType(cardinality);
      return "";
  }
}

function getLabelForDirection(direction: components["schemas"]["RelationshipDirection"]) {
  switch (direction) {
    case "bidirectional":
      return <Icon icon="mdi:arrow-left-right" />;
    case "inbound":
      return <Icon icon="mdi:arrow-left" />;
    case "outbound":
      return <Icon icon="mdi:arrow-right" />;
    default:
      warnUnexpectedType(direction);
      return "";
  }
}
