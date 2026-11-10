// PROTOTYPE design-jam schema-viewer-sections
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { ContainersSummaryRev04 } from "../containers-summary-rev-04";
import { fieldSource, SchemaPage, SourceTag, ViewerPanel, type ViewerSection } from "../context";
import { ProtoAttributeDisplay } from "../proto-attribute-display";
import { PropertiesTabRev04 } from "../proto-properties-rev-04";
import { ProtoRelationshipDisplay } from "../proto-relationship-display";
import { viewerSectionsRev03 } from "../sections-rev-03";

type FieldTab = "attributes" | "relationships";

function SectionHeading({
  section,
  tab,
  onKindClick,
  onSwitchTab,
}: {
  section: ViewerSection;
  tab: FieldTab;
  onKindClick: (kind: string) => void;
  onSwitchTab: () => void;
}) {
  const otherCount =
    tab === "attributes" ? section.relationships.length : section.attributes.length;
  const otherNoun =
    tab === "attributes"
      ? otherCount === 1
        ? "relationship"
        : "relationships"
      : otherCount === 1
        ? "attribute"
        : "attributes";

  return (
    <div className="flex items-start justify-between gap-3 px-1 pt-4 pb-1 first:pt-1">
      <div className="min-w-0">
        <h3 className="flex flex-wrap items-baseline gap-x-2 font-semibold text-sm">
          {section.label}
          <SourceTag source={section.source} onKindClick={onKindClick} />
          {section.collapsed && <Badge variant="gray-outline">starts collapsed</Badge>}
        </h3>
        {section.description && (
          <p className="text-foreground-muted text-xs">{section.description}</p>
        )}
      </div>
      {otherCount > 0 && (
        <button
          type="button"
          onClick={onSwitchTab}
          className="shrink-0 whitespace-nowrap rounded-sm text-custom-blue-700 text-xs hover:underline focus-visible:outline-2 focus-visible:outline-ring dark:text-custom-blue-300"
        >
          + {otherCount} {otherNoun}
        </button>
      )}
    </div>
  );
}

function FieldList({
  schema,
  tab,
  showFieldSource,
  onKindClick,
  onSwitchTab,
}: {
  schema: ModelSchema;
  tab: FieldTab;
  showFieldSource: boolean;
  onKindClick: (kind: string) => void;
  onSwitchTab: (tab: FieldTab) => void;
}) {
  const sections = viewerSectionsRev03(schema);
  const other: FieldTab = tab === "attributes" ? "relationships" : "attributes";
  const extra = (field: Parameters<typeof fieldSource>[1]) =>
    showFieldSource ? (
      <SourceTag source={fieldSource(schema, field)} onKindClick={onKindClick} />
    ) : null;

  const renderFields = (section: Pick<ViewerSection, "attributes" | "relationships">) =>
    tab === "attributes"
      ? section.attributes.map((attribute) => (
          <ProtoAttributeDisplay
            key={attribute.name}
            attribute={attribute}
            onKindClick={onKindClick}
            extra={extra(attribute)}
          />
        ))
      : section.relationships.map((relationship) => (
          <ProtoRelationshipDisplay
            key={relationship.name}
            relationship={relationship}
            onKindClick={onKindClick}
            extra={extra(relationship)}
          />
        ));

  if (sections.length === 0) {
    const fields = {
      attributes: schema.attributes ?? [],
      relationships: schema.relationships ?? [],
    };
    return fields[tab].length > 0 ? (
      renderFields(fields)
    ) : (
      <div className="flex h-32 items-center justify-center">
        {tab === "attributes" ? "No attribute" : "No relationship"}
      </div>
    );
  }

  return sections.map((section) => {
    const fields = tab === "attributes" ? section.attributes : section.relationships;
    return (
      <section
        key={section.name}
        id={`proto-section-${tab}-${section.name}`}
        aria-label={section.label}
        className="scroll-mt-2 space-y-2"
      >
        <SectionHeading
          section={section}
          tab={tab}
          onKindClick={onKindClick}
          onSwitchTab={() => onSwitchTab(other)}
        />
        {fields.length > 0 ? (
          renderFields(section)
        ) : (
          <p className="rounded-sm border border-dashed px-3 py-2 text-foreground-muted text-xs">
            No {tab} in this container on {schema.kind}.
          </p>
        )}
      </section>
    );
  });
}

export function GroupedRev04({ showFieldSource }: { showFieldSource: boolean }) {
  const [tab, setTab] = useState("attributes");

  return (
    <SchemaPage>
      {(schema, onKindClick) => (
        <ViewerPanel
          key={schema.kind}
          schema={schema}
          selectedTab={tab}
          onTabChange={setTab}
          tabs={[
            {
              id: "properties",
              label: "Properties",
              content: (
                <PropertiesTabRev04
                  schema={schema}
                  onKindClick={onKindClick}
                  containers={
                    <ContainersSummaryRev04
                      schema={schema}
                      openLabel="view its attributes"
                      onOpenSection={(name) => {
                        setTab("attributes");
                        setTimeout(() =>
                          document
                            .getElementById(`proto-section-attributes-${name}`)
                            ?.scrollIntoView({ block: "start" })
                        );
                      }}
                    />
                  }
                />
              ),
            },
            ...(["attributes", "relationships"] as const).map((id) => ({
              id,
              label: id === "attributes" ? "Attributes" : "Relationships",
              content: (
                <FieldList
                  schema={schema}
                  tab={id}
                  showFieldSource={showFieldSource}
                  onKindClick={onKindClick}
                  onSwitchTab={setTab}
                />
              ),
            })),
          ]}
        />
      )}
    </SchemaPage>
  );
}
