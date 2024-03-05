import { components } from "../../infraops";
import { Badge } from "../../components/ui/badge";
import { warnUnexpectedType } from "../../utils/common";
import { Icon } from "@iconify-icon/react";
import { AccordionStyled, PropertyRow } from "./styled";

export const RelationshipDisplay = ({
  relationship,
}: {
  relationship: components["schemas"]["RelationshipSchema-Output"];
}) => {
  const cardinalityLabel = relationship.cardinality
    ? getLabelForCardinality(relationship.cardinality)
    : null;

  const directionLabel = relationship.direction
    ? getLabelForDirection(relationship.direction)
    : null;

  return (
    <AccordionStyled
      title={relationship.label || relationship.name}
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
      isOptional={relationship.optional}>
      <div>
        <PropertyRow title="ID" value={relationship.id} />
        <PropertyRow title="Label" value={relationship.label} />
        <PropertyRow title="Name" value={relationship.name} />
      </div>

      <div>
        <PropertyRow title="Peer" value={relationship.peer} />
        <PropertyRow title="Peer identifier" value={relationship.identifier} />
        <PropertyRow title="Cardinality" value={relationship.cardinality} />
        <PropertyRow title="Direction" value={relationship.direction} />
        <PropertyRow title="Kind" value={relationship.kind} />
        <PropertyRow title="Hierarchical" value={relationship.hierarchical} />
        <PropertyRow title="Inherited" value={relationship.inherited} />
      </div>

      <div>
        <PropertyRow title="Branch" value={relationship.branch} />
        <PropertyRow title="Max count" value={relationship.max_count} />
        <PropertyRow title="Min count" value={relationship.min_count} />
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
