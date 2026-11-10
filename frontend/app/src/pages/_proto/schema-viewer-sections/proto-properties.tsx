// PROTOTYPE design-jam schema-viewer-sections
// Copy of the production Properties tab with a slot where the sections block sits; revisions never edit it.
import type { ReactNode } from "react";

import type { ContainerSchema, ModelSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { isNodeSchema } from "@/entities/schema/domain/rules/is-node-schema";
import { isProfileSchema } from "@/entities/schema/domain/rules/is-profile-schema";
import { PropertyRow, PropertyTitle, SchemaKindDisplay } from "@/entities/schema/ui/styled";

export const PropertiesTab = ({
  schema,
  onKindClick,
  sections,
}: {
  schema: ModelSchema;
  onKindClick?: (kind: string) => void;
  sections?: ReactNode;
}) => {
  return (
    <div className="divide-y p-2">
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
          <PropertyRow
            title="Used by"
            value={<SchemaKindDisplay kinds={schema.used_by} onKindClick={onKindClick} />}
          />
          <PropertyRow title="Hierarchical" value={schema.hierarchical} />
          <PropertyRow title="Restricted namespaces" value={schema.restricted_namespaces} />
        </div>
      )}

      {isNodeSchema(schema) && (
        <div>
          <PropertyRow
            title="Inherit from"
            value={<SchemaKindDisplay kinds={schema.inherit_from} onKindClick={onKindClick} />}
          />
          <PropertyRow
            title="Hierarchy"
            value={
              schema.hierarchy ? (
                <SchemaKindDisplay kinds={[schema.hierarchy]} onKindClick={onKindClick} />
              ) : (
                schema.hierarchy
              )
            }
          />
          <PropertyRow
            title="Parent"
            value={
              schema.parent ? (
                <SchemaKindDisplay kinds={[schema.parent]} onKindClick={onKindClick} />
              ) : (
                schema.parent
              )
            }
          />
          <PropertyRow
            title="Children"
            value={
              schema.children ? (
                <SchemaKindDisplay kinds={[schema.children]} onKindClick={onKindClick} />
              ) : (
                schema.children
              )
            }
          />
        </div>
      )}

      {sections}

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
        {isNodeSchema(schema) && (
          <PropertyRow title="Generate template" value={schema.generate_template} />
        )}
      </div>

      <div>
        <PropertyRow title="Documentation" value={schema.documentation} />
      </div>
    </div>
  );
};

export const ContainersBlock = ({ containers }: { containers?: ContainerSchema[] }) => {
  if (!containers?.length) return null;

  return (
    <div>
      <PropertyTitle title="Containers" />

      <div className="divide-y pl-4">
        {containers.map((container) => (
          <div key={container.name}>
            <PropertyRow title="Name" value={container.name} />
            <PropertyRow title="Label" value={container.label} />
            <PropertyRow title="Order weight" value={container.order_weight} />
            <PropertyRow title="Collapsed" value={container.collapsed} />
            <PropertyRow title="Description" value={container.description} />
          </div>
        ))}
      </div>
    </div>
  );
};
