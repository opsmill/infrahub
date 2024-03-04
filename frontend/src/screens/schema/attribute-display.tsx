import { components } from "../../infraops";
import { AccordionStyled, PropertyRow } from "./styled";
import Accordion from "../../components/display/accordion";

export const AttributeDisplay = ({
  attribute,
}: {
  attribute: components["schemas"]["AttributeSchema"];
}) => (
  <AccordionStyled
    title={attribute.label || attribute.name}
    kind={attribute.kind}
    description={attribute.description}
    isOptional={attribute.optional}
    isUnique={attribute.unique}
    isReadOnly={attribute.read_only}
    className="bg-custom-white shadow py-2 px-2 rounded">
    <div>
      <PropertyRow title="ID" value={attribute.id} />
      <PropertyRow title="Kind" value={attribute.kind} />
      <PropertyRow title="Name" value={attribute.name} />
      <PropertyRow title="Label" value={attribute.label} />
      <PropertyRow title="Description" value={attribute.description} />
      <PropertyRow title="Inherited" value={attribute.inherited} />
    </div>

    <div>
      <PropertyRow title="Unique" value={attribute.unique} />
      <PropertyRow title="Optional" value={attribute.optional} />
      <PropertyRow title="Choices" value={<ChoicesRow choices={attribute.choices} />} />
      <PropertyRow title="Enum" value={attribute.enum as string[]} />
    </div>

    <div>
      <PropertyRow title="Default value" value={attribute.default_value as any} />
      <PropertyRow title="Max length" value={attribute.max_length} />
      <PropertyRow title="Min length" value={attribute.min_length} />
      <PropertyRow title="Regex" value={attribute.regex} />
    </div>
    <div>
      <PropertyRow title="Branch" value={attribute.branch} />
      <PropertyRow title="Order weight" value={attribute.order_weight} />
    </div>
  </AccordionStyled>
);

const ChoicesRow = ({
  choices,
}: {
  choices: components["schemas"]["DropdownChoice"][] | null | undefined;
}) => {
  if (!choices || choices.length === 0) return "-";

  return (
    <div className="space-y-1 flex-grow">
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
            className="px-1.5 py-0.5 rounded-md flex-grow divide-y divide-gray-600"
            style={{ backgroundColor: color ?? undefined }}>
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
