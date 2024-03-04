import { iNodeSchema } from "../../state/atoms/schema.atom";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { Tab } from "@headlessui/react";
import { classNames } from "../../utils/common";
import { components } from "../../infraops";
import { ReactElement } from "react";
import { AccordionStyled, PropertyRow } from "./styled";
import { RelationshipDisplay } from "./relationship-display";

type SchemaViewerProps = {
  schema: iNodeSchema;
  onClose?: () => void;
};

export const SchemaViewer = ({ schema, onClose }: SchemaViewerProps) => {
  return (
    <section className="flex flex-col flex-grow shrink-0 max-w-lg max-h-screen overflow-hidden sticky top-2 right-2 space-y-4 p-4 shadow-lg border border-gray-200 bg-custom-white rounded-md">
      <div className="flex justify-between items-start">
        <Badge variant="blue">{schema.namespace}</Badge>

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

const TabStyled = ({ children }: { children: ReactElement | string }) => (
  <Tab
    className={({ selected }) =>
      classNames(
        "px-4 py-1 text-sm hover:bg-gray-100",
        selected ? "border-b-2 border-b-custom-blue-600 font-semibold" : ""
      )
    }>
    {children}
  </Tab>
);

const TabPanelStyled = ({ children }: { children?: ReactElement | ReactElement[] | string }) => {
  return <Tab.Panel className="space-y-2">{children}</Tab.Panel>;
};

const Properties = ({ schema }: SchemaViewerProps) => {
  return (
    <div className="p-2 divide-y">
      <PropertyRow title="Branch" value={schema.branch} />
      <PropertyRow title="Children" value={schema.children} />
      <PropertyRow title="Default filter" value={schema.default_filter} />
      <PropertyRow title="Display labels" value={schema.display_labels} />
      <PropertyRow title="Hierarchy" value={schema.hierarchy} />
      <PropertyRow title="Icon" value={schema.icon} />
      <PropertyRow title="ID" value={schema.id} />
      <PropertyRow title="Included in menu" value={schema.include_in_menu} />
      <PropertyRow title="Inherit from" value={schema.inherit_from} />
      <PropertyRow title="Kind" value={schema.kind} />
      <PropertyRow title="Label" value={schema.label} />
      <PropertyRow title="Menu placement" value={schema.menu_placement} />
      <PropertyRow title="Name" value={schema.name} />
      <PropertyRow title="Namespace" value={schema.namespace} />
      <PropertyRow title="Order by" value={schema.order_by} />
      <PropertyRow title="Parent" value={schema.parent} />
      <PropertyRow title="Uniqueness constraints" value={schema.uniqueness_constraints} />
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
    <article className="divide-y">
      <PropertyRow title="Branch" value={attribute.branch} />
      <PropertyRow title="Choices" value={attribute.choices} />
      <PropertyRow title="Default value" value={attribute.default_value as any} />
      <PropertyRow title="Description" value={attribute.description} />
      <PropertyRow title="Enum" value={attribute.enum as string[]} />
      <PropertyRow title="ID" value={attribute.id} />
      <PropertyRow title="Inherited" value={attribute.inherited} />
      <PropertyRow title="Kind" value={attribute.kind} />
      <PropertyRow title="Label" value={attribute.label} />
      <PropertyRow title="Max length" value={attribute.max_length} />
      <PropertyRow title="Min length" value={attribute.min_length} />
      <PropertyRow title="Name" value={attribute.name} />
      <PropertyRow title="Optional" value={attribute.optional} />
      <PropertyRow title="Order weight" value={attribute.order_weight} />
      <PropertyRow title="Regex" value={attribute.regex} />
      <PropertyRow title="Unique" value={attribute.unique} />
    </article>
  </AccordionStyled>
);
