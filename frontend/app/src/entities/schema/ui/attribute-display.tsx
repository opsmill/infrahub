import { useEffect, useRef } from "react";

import { constructPath } from "@/shared/api/rest/fetch";
import type { components } from "@/shared/api/rest/types.generated";
import Accordion from "@/shared/components/display/accordion";
import { Link } from "@/shared/components/ui/link";
import { formatNumberDisplay } from "@/shared/utils/number";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

import { ComputedAttributeDisplay } from "./computed-attribute-display";
import { AccordionStyled, NullDisplay, PropertyRow, PropertyTitle } from "./styled";

export const AttributeDisplay = ({
  attribute,
  defaultOpen = false,
}: {
  attribute: components["schemas"]["AttributeSchema-Output"];
  defaultOpen?: boolean;
}) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (defaultOpen && ref.current) {
      ref.current.scrollIntoView({ behavior: "instant", block: "start" });
    }
  }, [defaultOpen]);

  return (
    <AccordionStyled
      ref={ref}
      title={attribute.label || attribute.name}
      kind={attribute.kind}
      description={attribute.description}
      isOptional={attribute.optional}
      isUnique={attribute.unique}
      isReadOnly={attribute.read_only}
      isComputed={!!attribute.computed_attribute}
      isDeprecated={!!attribute.deprecation}
      defaultOpen={defaultOpen}
    >
      <div>
        <PropertyRow title="ID" value={attribute.id} />
        <PropertyRow title="Kind" value={attribute.kind} />
        <PropertyRow
          title="Computed attribute"
          value={<ComputedAttributeDisplay computedAttribute={attribute.computed_attribute} />}
        />
        <PropertyRow title="Name" value={attribute.name} />
        <PropertyRow title="Label" value={attribute.label} />
        <PropertyRow title="Description" value={attribute.description} />
        <PropertyRow title="Inherited" value={attribute.inherited} />
        <PropertyRow title="Default value" value={attribute.default_value as any} />
        <PropertyRow title="Deprecation" value={attribute.deprecation} />
      </div>

      <div>
        <PropertyRow title="Unique" value={attribute.unique} />
        <PropertyRow title="Optional" value={attribute.optional} />
        <PropertyRow title="Choices" value={<ChoicesRow choices={attribute.choices} />} />
        <PropertyRow title="Enum" value={attribute.enum as string[]} />
      </div>

      <div>
        <PropertyRow title="Branch" value={attribute.branch} />
        <PropertyRow title="Order weight" value={attribute.order_weight} />
      </div>

      <AttributeParameters attribute={attribute} />
    </AccordionStyled>
  );
};

const ChoicesRow = ({
  choices,
}: {
  choices: components["schemas"]["DropdownChoice"][] | null | undefined;
}) => {
  if (choices === undefined) return null;
  if (choices === null) return <NullDisplay />;
  if (choices.length === 0) return "No choices";

  return (
    <div className="grow space-y-1">
      {choices.map((choice) => {
        const color = choice.color === "" ? "#f1f1f1" : choice.color;
        return (
          <Accordion
            key={choice.name}
            title={
              <div className="flex justify-between gap-2 pr-2 font-normal">
                {choice.label || choice.name} <span>{choice.color}</span>
              </div>
            }
            className="grow divide-y divide-gray-600 rounded-md px-1.5 py-0.5"
            style={{ backgroundColor: color ?? undefined }}
          >
            <PropertyRow title="Name" value={choice.name} />
            <PropertyRow title="Label" value={choice.label} />
            <PropertyRow title="Color" value={choice.color} />
            <PropertyRow title="Description" value={choice.description} />
          </Accordion>
        );
      })}
    </div>
  );
};

const AttributeParameters = ({
  attribute,
}: {
  attribute: components["schemas"]["AttributeSchema-Output"];
}) => {
  if (attribute.kind === "Text") {
    const parameters = attribute.parameters as components["schemas"]["TextAttributeParameters"];
    return (
      <div>
        <PropertyTitle title="Parameters" />

        <div className="pl-4">
          <PropertyRow title="Regex" value={parameters.regex} />
          <PropertyRow title="Min length" value={parameters.min_length} />
          <PropertyRow title="Max length" value={parameters.max_length} />
        </div>
      </div>
    );
  }

  if (attribute.kind === "Number") {
    const parameters = attribute.parameters as components["schemas"]["NumberAttributeParameters"];
    return (
      <div>
        <PropertyTitle title="Parameters" />

        <div className="pl-4">
          <PropertyRow title="Min value" value={parameters.min_value} />
          <PropertyRow title="Max value" value={parameters.max_value} />
          <PropertyRow title="Excluded values" value={parameters.excluded_values} />
        </div>
      </div>
    );
  }

  if (attribute.kind === "NumberPool") {
    const parameters = attribute.parameters as components["schemas"]["NumberPoolParameters"];
    return (
      <div>
        <PropertyTitle title="Parameters" />

        <div className="pl-4">
          <PropertyRow
            title="Number pool"
            value={
              <Link to={constructPath(`/resource-manager/${parameters.number_pool_id}`)}>
                <NodeLabel id={parameters.number_pool_id ?? undefined} />
              </Link>
            }
          />
          <PropertyRow title="Start range" value={formatNumberDisplay(parameters.start_range)} />
          <PropertyRow title="End range" value={formatNumberDisplay(parameters.end_range)} />
        </div>
      </div>
    );
  }

  return null;
};
