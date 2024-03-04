import { iNodeSchema } from "../../state/atoms/schema.atom";
import { Badge } from "../../components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { Tab } from "@headlessui/react";
import { PropertyRow, TabPanelStyled, TabStyled } from "./styled";
import { RelationshipDisplay } from "./relationship-display";
import { AttributeDisplay } from "./attribute-display";

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
