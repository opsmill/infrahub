// PROTOTYPE design-jam schema-viewer-sections
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";

import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { AccordionStyled } from "@/entities/schema/ui/styled";

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
import { SectionsSummary } from "../sections-summary-rev-02";

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
  const outsideCard = item.type === "relationship" && isShownAsTab(item.field);

  return (
    <li className="relative flex items-start justify-between gap-4 p-2 py-3 text-sm hover:bg-highlight">
      <div className="min-w-0">
        <p className="flex flex-wrap items-baseline gap-x-2">
          <button
            type="button"
            onClick={onOpen}
            className="text-left after:absolute after:inset-0 focus-visible:outline-none after:focus-visible:outline-2 after:focus-visible:outline-ring after:focus-visible:-outline-offset-2"
          >
            {label}
          </button>
          {label !== field.name && (
            <span className="font-mono text-foreground-muted text-xs">{field.name}</span>
          )}
        </p>
        {(showFieldSource || outsideCard) && (
          <p className="relative z-10 flex flex-wrap items-center gap-x-2">
            {showFieldSource && (
              <SourceTag source={fieldSource(schema, field)} onKindClick={onKindClick} />
            )}
            {outsideCard && (
              <span className="text-foreground-muted text-xs">
                not in a card on the detail page
              </span>
            )}
          </p>
        )}
      </div>
      <span className="flex shrink-0 items-center gap-1 text-end font-medium">
        {item.type === "attribute" ? (
          <Badge>{item.field.kind}</Badge>
        ) : (
          <>
            {item.field.cardinality === "many" ? "N" : "1"} → {item.field.peer}
          </>
        )}
      </span>
    </li>
  );
}

const countLabel = (count: number) => (count === 1 ? "1 field" : `${count} fields`);

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
    <div id={`proto-layout-${section.name}`} className="scroll-mt-2">
      <AccordionStyled
        defaultOpen
        title={
          <span className="inline-flex flex-wrap items-baseline gap-x-2">
            {section.label}
            <span className="font-normal text-foreground-muted text-xs tabular-nums">
              {countLabel(fields.length)}
            </span>
            {section.source.type !== "own" && (
              <SourceTag source={section.source} onKindClick={onKindClick} />
            )}
          </span>
        }
        kind=""
        description={section.description}
      >
        {section.collapsed && (
          <p className="p-2 text-foreground-muted text-xs">Starts collapsed on the detail page.</p>
        )}
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
          <p className="p-2 py-3 text-foreground-muted text-sm">
            No fields in this section on {schema.kind}. The detail page hides it.
          </p>
        )}
      </AccordionStyled>
    </div>
  );
}

export function LayoutRev02({ showFieldSource }: { showFieldSource: boolean }) {
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
                      <SectionsSummary
                        schema={schema}
                        onKindClick={onKindClick}
                        openLabel="view it in the layout"
                        onOpenSection={(name) => {
                          setTab("layout");
                          setTimeout(() =>
                            document
                              .getElementById(`proto-layout-${name}`)
                              ?.scrollIntoView({ block: "start" })
                          );
                        }}
                      />
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
                        <div className="space-y-2">
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
