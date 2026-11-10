// PROTOTYPE design-jam schema-viewer-sections
// Properties tab with titled groups, used from rev 4; later revisions copy it instead of editing it.
import type { ReactNode } from "react";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { isNodeSchema } from "@/entities/schema/domain/rules/is-node-schema";
import { isProfileSchema } from "@/entities/schema/domain/rules/is-profile-schema";
import { PropertyRow, SchemaKindDisplay } from "@/entities/schema/ui/styled";

export const PropertyGroup = ({ title, children }: { title: string; children: ReactNode }) => (
  <section aria-label={title} className="rounded-sm bg-card p-3 shadow-card">
    <h3 className="px-1 font-semibold text-sm">{title}</h3>
    <div className="mt-2 divide-y rounded-sm bg-panel px-2 shadow-panel">{children}</div>
  </section>
);

const KindValue = ({
  kind,
  onKindClick,
}: {
  kind: string | null | undefined;
  onKindClick?: (kind: string) => void;
}) => (kind ? <SchemaKindDisplay kinds={[kind]} onKindClick={onKindClick} /> : kind);

export const PropertiesTabRev04 = ({
  schema,
  onKindClick,
  containers,
}: {
  schema: ModelSchema;
  onKindClick?: (kind: string) => void;
  containers?: ReactNode;
}) => {
  return (
    <div className="space-y-2">
      <PropertyGroup title="General">
        <PropertyRow title="ID" value={schema.id} />
        <PropertyRow title="Namespace" value={schema.namespace} />
        <PropertyRow title="Name" value={schema.name} />
        <PropertyRow title="Label" value={schema.label} />
        <PropertyRow title="Kind" value={schema.kind} />
        <PropertyRow title="Human Friendly ID" value={schema.human_friendly_id} />
        <PropertyRow title="Display label" value={schema.display_label} />
        <PropertyRow title="Display labels (deprecated)" value={schema.display_labels} />
        <PropertyRow title="Description" value={schema.description} />
      </PropertyGroup>

      {isGenericSchema(schema) && (
        <PropertyGroup title="Inheritance">
          <PropertyRow
            title="Used by"
            value={<SchemaKindDisplay kinds={schema.used_by} onKindClick={onKindClick} />}
          />
          <PropertyRow title="Hierarchical" value={schema.hierarchical} />
          <PropertyRow title="Restricted namespaces" value={schema.restricted_namespaces} />
        </PropertyGroup>
      )}

      {isNodeSchema(schema) && (
        <PropertyGroup title="Inheritance and hierarchy">
          <PropertyRow
            title="Inherit from"
            value={<SchemaKindDisplay kinds={schema.inherit_from} onKindClick={onKindClick} />}
          />
          <PropertyRow
            title="Hierarchy"
            value={<KindValue kind={schema.hierarchy} onKindClick={onKindClick} />}
          />
          <PropertyRow
            title="Parent"
            value={<KindValue kind={schema.parent} onKindClick={onKindClick} />}
          />
          <PropertyRow
            title="Children"
            value={<KindValue kind={schema.children} onKindClick={onKindClick} />}
          />
        </PropertyGroup>
      )}

      {containers}

      <PropertyGroup title="Menu">
        <PropertyRow title="Included in menu" value={schema.include_in_menu} />
        <PropertyRow title="Menu placement" value={schema.menu_placement} />
        <PropertyRow title="Icon" value={schema.icon} />
      </PropertyGroup>

      <PropertyGroup title="Data">
        <PropertyRow title="Branch" value={schema.branch} />
        <PropertyRow title="Default filter" value={schema.default_filter} />
        <PropertyRow title="Order by" value={schema.order_by} />
        <PropertyRow title="Uniqueness constraints" value={schema.uniqueness_constraints} />
      </PropertyGroup>

      {(!isProfileSchema(schema) || isNodeSchema(schema)) && (
        <PropertyGroup title="Profiles and templates">
          {!isProfileSchema(schema) && (
            <PropertyRow title="Generate profile" value={schema.generate_profile} />
          )}
          {isNodeSchema(schema) && (
            <PropertyRow title="Generate template" value={schema.generate_template} />
          )}
        </PropertyGroup>
      )}

      <PropertyGroup title="Documentation">
        <PropertyRow title="Documentation" value={schema.documentation} />
      </PropertyGroup>
    </div>
  );
};
