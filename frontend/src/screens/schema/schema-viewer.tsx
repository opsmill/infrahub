import { iNodeSchema } from "../../state/atoms/schema.atom";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { Tab } from "@headlessui/react";
import { components } from "../../infraops";
import { AccordionStyled, PropertyRow, TabPanelStyled, TabStyled } from "./styled";
import { RelationshipDisplay } from "./relationship-display";
import Accordion from "../../components/display/accordion";

type SchemaViewerProps = {
  schema: iNodeSchema;
  onClose?: () => void;
};

export const SchemaViewer = ({ schema, onClose }: SchemaViewerProps) => {
  return (
    <section className="flex flex-col flex-grow shrink-0 max-w-lg max-h-screen overflow-hidden sticky top-2 right-2 space-y-4 p-4 shadow-lg border border-gray-200 bg-custom-white rounded-md">
      <div className="flex justify-between items-start">
        <div className="space-x-1">
          <Badge variant="blue">{schema.namespace}</Badge>
          <Badge>Node</Badge>
          <span className="text-xs">{schema.id}</span>
        </div>

        <Icon icon="mdi:close" className="text-xl cursor-pointer text-gray-600" onClick={onClose} />
      </div>

      <SchemaViewerTitle schema={schema} />

      <SchemaViewerDetails schema={schema} />
    </section>
  );
};

const SchemaViewerTitle = ({ schema }: SchemaViewerProps) => {
  return (
    <header className="flex gap-2">
      {schema.icon && (
        <Icon
          icon={schema.icon}
          className="text-xl p-2 self-start rounded text-custom-blue-600 border border-custom-blue-100"
        />
      )}

      <div>
        <h1 className="font-semibold">{schema.label}</h1>
        <p className="text-sm text-gray-600">{schema.description}</p>
      </div>
    </header>
  );
};

const SchemaViewerDetails = ({ schema }: SchemaViewerProps) => {
  return (
    <section className="flex flex-col overflow-hidden">
      <Tab.Group>
        <Tab.List>
          <TabStyled>Properties</TabStyled>
          <TabStyled>Attributes</TabStyled>
          <TabStyled>Relationships</TabStyled>
        </Tab.List>

        <Tab.Panels className="p-2 bg-gray-100 flex-grow min-h-0 overflow-auto">
          <TabPanelStyled>
            <Properties schema={schema} />
          </TabPanelStyled>

          <TabPanelStyled>
            {schema.attributes?.map((attribute) => (
              <AttributeDisplay key={attribute.id} attribute={attribute} />
            ))}
          </TabPanelStyled>

          <TabPanelStyled>
            {schema.relationships?.map((relationship) => (
              <RelationshipDisplay key={relationship.id} relationship={relationship} />
            ))}
          </TabPanelStyled>
        </Tab.Panels>
      </Tab.Group>
    </section>
  );
};

const Properties = ({ schema }: SchemaViewerProps) => {
  return (
    <div className="p-2 divide-y">
      <div>
        <PropertyRow title="ID" value={schema.id} />
        <PropertyRow title="Namespace" value={schema.namespace} />
        <PropertyRow title="Name" value={schema.name} />
        <PropertyRow title="Label" value={schema.label} />
        <PropertyRow title="Kind" value={schema.kind} />
        <PropertyRow title="Display labels" value={schema.display_labels} />
        <PropertyRow title="Description" value={schema.description} />
      </div>

      <div>
        <PropertyRow title="Inherit from" value={schema.inherit_from} />
        <PropertyRow title="Hierarchy" value={schema.hierarchy} />
        <PropertyRow title="Parent" value={schema.parent} />
        <PropertyRow title="Children" value={schema.children} />
      </div>

      <div>
        <PropertyRow title="Included in menu" value={schema.include_in_menu} />
        <PropertyRow title="Menu placement" value={schema.menu_placement} />
      </div>

      <div>
        <PropertyRow title="Icon" value={schema.icon} />
        <PropertyRow title="Branch" value={schema.branch} />
        <PropertyRow title="Default filter" value={schema.default_filter} />
        <PropertyRow title="Order by" value={schema.order_by} />
        <PropertyRow title="Uniqueness constraints" value={schema.uniqueness_constraints} />
      </div>
    </div>
  );
};

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

const AttributeDisplay = ({
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
