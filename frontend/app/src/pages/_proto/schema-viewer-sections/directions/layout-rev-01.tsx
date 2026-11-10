// PROTOTYPE design-jam schema-viewer-sections
import { Card, CardHeader } from "@infrahub/ui";
import { ChevronRightIcon } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";

import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { PropertyRow } from "@/entities/schema/ui/styled";

import {
  fieldSource,
  isShownAsTab,
  SchemaPage,
  SourceTag,
  ViewerPanel,
  type ViewerSection,
  viewerSections,
} from "../context";
import { ProtoAttributeDisplay } from "../proto-attribute-display";
import { PropertiesTab } from "../proto-properties";
import { ProtoRelationshipDisplay } from "../proto-relationship-display";

type Field =
  | { type: "attribute"; field: AttributeSchema }
  | { type: "relationship"; field: RelationshipSchema };

const fieldsOf = (section: ViewerSection): Field[] =>
  [
    ...section.attributes.map((field) => ({ type: "attribute" as const, field })),
    ...section.relationships.map((field) => ({ type: "relationship" as const, field })),
  ].sort((a, b) => (a.field.order_weight ?? 0) - (b.field.order_weight ?? 0));

function FieldRow({
  schema,
  item,
  showFieldSource,
  onKindClick,
  onOpen,
}: {
  schema: ModelSchema;
  item: Field;
  showFieldSource: boolean;
  onKindClick: (kind: string) => void;
  onOpen: () => void;
}) {
  const { field } = item;
  const label = field.label || field.name;
  return (
    <li className="group relative flex items-center gap-3 px-3 py-2 text-sm hover:bg-highlight">
      <span className="flex min-w-0 grow flex-col">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <button
            type="button"
            onClick={onOpen}
            className="text-left font-medium after:absolute after:inset-0 focus-visible:outline-none after:focus-visible:outline-2 after:focus-visible:outline-ring after:focus-visible:-outline-offset-2"
          >
            {label}
          </button>
          {label !== field.name && (
            <span className="font-mono text-foreground-muted text-xs">{field.name}</span>
          )}
        </span>
        {(showFieldSource || (item.type === "relationship" && isShownAsTab(item.field))) && (
          <span className="relative z-10 flex flex-wrap items-center gap-x-2 self-start">
            {showFieldSource && (
              <SourceTag source={fieldSource(schema, field)} onKindClick={onKindClick} />
            )}
            {item.type === "relationship" && isShownAsTab(item.field) && (
              <span className="text-foreground-muted text-xs">
                not in a card on the detail page
              </span>
            )}
          </span>
        )}
      </span>
      <span className="shrink-0 text-foreground-muted text-xs">
        {item.type === "attribute" ? (
          <Badge>{item.field.kind}</Badge>
        ) : (
          <span className="inline-flex items-center gap-1">
            {item.field.cardinality === "many" ? "N" : "1"} → {item.field.peer}
          </span>
        )}
      </span>
      <ChevronRightIcon
        aria-hidden
        className="size-3.5 shrink-0 text-foreground-muted opacity-0 group-hover:opacity-100"
      />
    </li>
  );
}

function SectionCard({
  schema,
  section,
  showFieldSource,
  onKindClick,
  onOpenField,
}: {
  schema: ModelSchema;
  section: ViewerSection;
  showFieldSource: boolean;
  onKindClick: (kind: string) => void;
  onOpenField: (item: Field) => void;
}) {
  const fields = fieldsOf(section);
  return (
    <Card variant="panel" role="region" aria-label={section.label}>
      <CardHeader className="flex flex-col items-start gap-0.5">
        <h3 className="flex flex-wrap items-baseline gap-x-2 font-semibold text-sm">
          {section.label}
          <SourceTag source={section.source} onKindClick={onKindClick} />
          {section.collapsed && <Badge variant="gray-outline">collapsed</Badge>}
        </h3>
        {section.description && (
          <p className="font-normal text-foreground-muted text-xs">{section.description}</p>
        )}
      </CardHeader>
      {fields.length > 0 ? (
        <ul className="divide-y">
          {fields.map((item) => (
            <FieldRow
              key={item.field.name}
              schema={schema}
              item={item}
              showFieldSource={showFieldSource}
              onKindClick={onKindClick}
              onOpen={() => onOpenField(item)}
            />
          ))}
        </ul>
      ) : (
        <p className="px-3 py-2 text-foreground-muted text-xs">
          No fields in this section on {schema.kind}. The detail page hides it.
        </p>
      )}
    </Card>
  );
}

export function LayoutRev01({ showFieldSource }: { showFieldSource: boolean }) {
  const [tab, setTab] = useState("layout");
  const [target, setTarget] = useState<string>();

  return (
    <SchemaPage>
      {(schema, onKindClick) => {
        const sections = viewerSections(schema);
        const hasLayout = sections.length > 0;
        const selected = !hasLayout && tab === "layout" ? "properties" : tab;
        const openField = (item: Field) => {
          setTarget(item.field.name);
          setTab(item.type === "attribute" ? "attributes" : "relationships");
        };

        return (
          <ViewerPanel
            key={schema.kind}
            schema={schema}
            selectedTab={selected}
            onTabChange={(id) => {
              setTarget(undefined);
              setTab(id);
            }}
            tabs={[
              {
                id: "properties",
                label: "Properties",
                content: (
                  <PropertiesTab
                    schema={schema}
                    onKindClick={onKindClick}
                    sections={
                      hasLayout && (
                        <div>
                          <PropertyRow
                            title="Sections"
                            value={
                              <button
                                type="button"
                                onClick={() => setTab("layout")}
                                className="rounded-sm text-custom-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-ring dark:text-custom-blue-300"
                              >
                                {sections.length} sections, view the layout
                              </button>
                            }
                          />
                        </div>
                      )
                    }
                  />
                ),
              },
              ...(hasLayout
                ? [
                    {
                      id: "layout",
                      label: "Layout",
                      content: (
                        <div className="space-y-3 p-1">
                          {sections.map((section) => (
                            <SectionCard
                              key={section.name}
                              schema={schema}
                              section={section}
                              showFieldSource={showFieldSource}
                              onKindClick={onKindClick}
                              onOpenField={openField}
                            />
                          ))}
                        </div>
                      ),
                    },
                  ]
                : []),
              {
                id: "attributes",
                label: "Attributes",
                content: (schema.attributes ?? []).map((attribute) => (
                  <ProtoAttributeDisplay
                    key={`${attribute.name}-${target === attribute.name}`}
                    attribute={attribute}
                    onKindClick={onKindClick}
                    defaultOpen={target === attribute.name}
                  />
                )),
              },
              {
                id: "relationships",
                label: "Relationships",
                content: (schema.relationships ?? []).map((relationship) => (
                  <ProtoRelationshipDisplay
                    key={`${relationship.name}-${target === relationship.name}`}
                    relationship={relationship}
                    onKindClick={onKindClick}
                    defaultOpen={target === relationship.name}
                  />
                )),
              },
            ]}
          />
        );
      }}
    </SchemaPage>
  );
}
