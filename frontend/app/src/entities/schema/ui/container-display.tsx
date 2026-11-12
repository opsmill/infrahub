import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

import { AccordionStyled, PropertyRow } from "./styled";

export const ContainerDisplay = ({ container }: { container: ContainerSchema }) => {
  return (
    <AccordionStyled
      title={container.label || container.name}
      kind={container.name}
      description={container.description}
    >
      <div>
        <PropertyRow title="Name" value={container.name} />
        <PropertyRow title="Label" value={container.label} />
        <PropertyRow title="Description" value={container.description} />
        <PropertyRow title="Order weight" value={container.order_weight} />
        <PropertyRow title="Collapsible" value={container.collapsible} />
        <PropertyRow title="Collapsed" value={container.collapsed} />
        <PropertyRow title="Inherited" value={container.inherited} />
      </div>
    </AccordionStyled>
  );
};
