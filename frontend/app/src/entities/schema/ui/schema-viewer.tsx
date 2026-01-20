import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { parseAsNativeArrayOf, parseAsString, useQueryState } from "nuqs";
import type { CSSProperties } from "react";
import { TabList, Tabs } from "react-aria-components";

import { Button } from "@/shared/components/buttons/button-primitive";
import { Badge } from "@/shared/components/ui/badge";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { isNodeSchema } from "@/entities/schema/utils/is-node-schema";
import { isProfileSchema } from "@/entities/schema/utils/is-profile-schema";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

import { AttributeDisplay } from "./attribute-display";
import { RelationshipDisplay } from "./relationship-display";
import { SchemaHelpMenu } from "./schema-help-menu";
import { ModelDisplay, PropertyRow, TabPanelStyled, TabStyled } from "./styled";

export const SchemaViewerStack = ({ className = "" }: { className: string }) => {
  const [selectedKind, setKinds] = useQueryState(QSP.KIND, parseAsNativeArrayOf(parseAsString));
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);
  const templates = useAtomValue(templateSchemasAtom);

  if (!selectedKind) return null;

  const schemas = [...nodes, ...generics, ...profiles, ...templates];

  return (
    <div className={classNames("relative", className)}>
      {selectedKind.map((kind, index) => {
        const position = selectedKind.length - index - 1;
        const schema = schemas.find((s) => s.kind === kind);
        if (!schema) return null;

        return kind ? (
          <SchemaViewer
            key={kind + index}
            className="absolute top-0 max-h-full w-full"
            schema={schema}
            onClose={() => {
              const nextKinds = selectedKind.filter((_, i) => i !== index);
              setKinds(nextKinds);
            }}
            style={{
              transition: "transform 300ms ease-in-out",
              transform: `translate(${position * 10}px, ${position * 10}px)`,
              zIndex: index,
            }}
          />
        ) : null;
      })}
    </div>
  );
};

export const SchemaViewer = ({
  className = "",
  schema,
  onClose,
  style,
  defaultTab = "properties",
}: {
  className?: string;
  schema: ModelSchema;
  onClose: () => void;
  style?: CSSProperties;
  defaultTab?: "properties" | "attributes" | "relationships";
}) => {
  return (
    <section
      style={style}
      className={classNames(
        "flex flex-col space-y-4 overflow-hidden rounded-md border border-gray-200 bg-white p-4 shadow-lg",
        className
      )}
      data-testid="schema-viewer"
    >
      <div className="flex items-start justify-between">
        <div className="space-x-1">
          <Badge variant="blue">{schema.namespace}</Badge>
          <Badge>{isGenericSchema(schema) ? "Generic" : "Node"}</Badge>
          <span className="text-xs">{schema.id}</span>
        </div>

        <div className="flex items-center gap-2 text-gray-600">
          <SchemaHelpMenu schema={schema} />

          <Button size="icon" variant="ghost" onClick={onClose}>
            <Icon icon="mdi:close" className="text-xl" />
          </Button>
        </div>
      </div>

      <SchemaViewerTitle schema={schema} />

      <SchemaViewerDetails schema={schema} defaultTab={defaultTab} />
    </section>
  );
};

const SchemaViewerTitle = ({ schema }: { schema: ModelSchema }) => {
  return (
    <header className="flex gap-2">
      {schema.icon && (
        <Icon
          icon={schema.icon}
          className="self-start rounded-sm border border-custom-blue-100 p-2 text-custom-blue-600 text-xl"
        />
      )}

      <div>
        <h1 className="font-semibold">{schema.label}</h1>
        <p className="text-gray-600 text-sm">{schema.description}</p>
      </div>
    </header>
  );
};

const SchemaViewerDetails = ({
  schema,
  defaultTab,
}: {
  schema: ModelSchema;
  defaultTab: "properties" | "attributes" | "relationships";
}) => {
  return (
    <Tabs defaultSelectedKey={defaultTab} className="flex flex-col overflow-y-hidden">
      <TabList className="flex">
        <TabStyled id="properties">Properties</TabStyled>
        <TabStyled id="attributes">Attributes</TabStyled>
        <TabStyled id="relationships">Relationships</TabStyled>
      </TabList>

      <TabPanelStyled id="properties">
        <Properties schema={schema} />
      </TabPanelStyled>

      <TabPanelStyled id="attributes">
        {schema.attributes && schema.attributes.length > 0 ? (
          schema.attributes?.map((attribute) => (
            <AttributeDisplay key={attribute.id} attribute={attribute} />
          ))
        ) : (
          <div className="flex h-32 items-center justify-center">No attribute</div>
        )}
      </TabPanelStyled>

      <TabPanelStyled id="relationships">
        {schema.relationships && schema.relationships.length > 0
          ? schema.relationships?.map((relationship) => (
              <RelationshipDisplay key={relationship.id} relationship={relationship} />
            ))
          : "No relationship"}
      </TabPanelStyled>
    </Tabs>
  );
};

const Properties = ({ schema }: { schema: ModelSchema }) => {
  return (
    <div className="divide-y divide-gray-200 p-2">
      <div>
        <PropertyRow title="ID" value={schema.id} />
        <PropertyRow title="Namespace" value={schema.namespace} />
        <PropertyRow title="Name" value={schema.name} />
        <PropertyRow title="Label" value={schema.label} />
        <PropertyRow title="Kind" value={schema.kind} />
        <PropertyRow title="Human Friendly ID" value={schema.human_friendly_id} />
        <PropertyRow title="Display label" value={schema.display_label} />
        <PropertyRow title="Display labels (deprecated)" value={schema.display_labels} />
        <PropertyRow title="Description" value={schema.description} />
      </div>

      {isGenericSchema(schema) && (
        <div>
          <PropertyRow title="Used by" value={<ModelDisplay kinds={schema.used_by} />} />
          <PropertyRow title="Hierarchical" value={schema.hierarchical} />
        </div>
      )}

      {isNodeSchema(schema) && (
        <div>
          <PropertyRow title="Inherit from" value={<ModelDisplay kinds={schema.inherit_from} />} />
          <PropertyRow
            title="Hierarchy"
            value={
              schema.hierarchy ? <ModelDisplay kinds={[schema.hierarchy]} /> : schema.hierarchy
            }
          />
          <PropertyRow
            title="Parent"
            value={schema.parent ? <ModelDisplay kinds={[schema.parent]} /> : schema.parent}
          />
          <PropertyRow
            title="Children"
            value={schema.children ? <ModelDisplay kinds={[schema.children]} /> : schema.children}
          />
        </div>
      )}

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

      <div>
        {!isProfileSchema(schema) && (
          <PropertyRow title="Generate profile" value={schema.generate_profile} />
        )}
        {!isTemplateSchema(schema) && (
          <PropertyRow title="Generate template" value={schema.generate_template} />
        )}
      </div>

      <div>
        <PropertyRow title="Documentation" value={schema.documentation} />
      </div>
    </div>
  );
};
