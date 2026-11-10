// PROTOTYPE design-jam schema-viewer-sections
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

import { ContainersSummaryRev04 } from "../containers-summary-rev-04";
import { fieldSource, SchemaPage, SourceTag, ViewerPanel, type ViewerSection } from "../context";
import { ProtoAttributeDisplay } from "../proto-attribute-display";
import { PropertiesTabRev04 } from "../proto-properties-rev-04";
import { ProtoRelationshipDisplay } from "../proto-relationship-display";
import { viewerSectionsRev03 } from "../sections-rev-03";

type FieldTab = "attributes" | "relationships";
const ALL = "__all";

function SectionChips({
  sections,
  tab,
  selected,
  onSelect,
}: {
  sections: ViewerSection[];
  tab: FieldTab;
  selected: string;
  onSelect: (name: string) => void;
}) {
  const countOn = (s: ViewerSection) =>
    tab === "attributes" ? s.attributes.length : s.relationships.length;
  const total = sections.reduce((sum, s) => sum + countOn(s), 0);
  const chips = [{ name: ALL, label: "All", count: total }].concat(
    sections.map((s) => ({ name: s.name, label: s.label, count: countOn(s) }))
  );

  return (
    <div role="group" aria-label="Filter by container" className="flex flex-wrap gap-1.5 px-1 pb-1">
      {chips.map((chip) => {
        const isSelected = chip.name === selected;
        return (
          <button
            key={chip.name}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onSelect(chip.name)}
            className={classNames(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs focus-visible:outline-2 focus-visible:outline-ring",
              isSelected
                ? "border-accent bg-accent/10 font-semibold text-foreground"
                : "bg-card text-foreground-muted hover:bg-highlight",
              chip.count === 0 && !isSelected && "border-dashed"
            )}
          >
            {chip.label}
            <span className="tabular-nums">{chip.count}</span>
          </button>
        );
      })}
    </div>
  );
}

function FieldList({
  schema,
  tab,
  selected,
  showFieldSource,
  onSelect,
  onKindClick,
  onSwitchTab,
}: {
  schema: ModelSchema;
  tab: FieldTab;
  selected: string;
  showFieldSource: boolean;
  onSelect: (name: string) => void;
  onKindClick: (kind: string) => void;
  onSwitchTab: (tab: FieldTab) => void;
}) {
  const sections = viewerSectionsRev03(schema);
  const current = sections.find((s) => s.name === selected);
  const sectionOfField = (name: string) =>
    sections.find(
      (s) =>
        s.attributes.some((f) => f.name === name) || s.relationships.some((f) => f.name === name)
    );

  const extra = (field: AttributeSchema | RelationshipSchema) => {
    const section = sectionOfField(field.name);
    return (
      <>
        {!current && section && <Badge variant="gray-outline">{section.label}</Badge>}
        {showFieldSource && (
          <SourceTag source={fieldSource(schema, field)} onKindClick={onKindClick} />
        )}
      </>
    );
  };

  const pool = current ?? {
    attributes: schema.attributes ?? [],
    relationships: schema.relationships ?? [],
  };
  const fields = tab === "attributes" ? pool.attributes : pool.relationships;
  const otherTab: FieldTab = tab === "attributes" ? "relationships" : "attributes";
  const otherCount = current
    ? tab === "attributes"
      ? current.relationships.length
      : current.attributes.length
    : 0;

  return (
    <div className="space-y-2">
      {sections.length > 0 && (
        <SectionChips sections={sections} tab={tab} selected={selected} onSelect={onSelect} />
      )}

      {current && (
        <div className="flex items-start justify-between gap-3 rounded-md bg-panel px-3 py-2 shadow-panel">
          <div className="min-w-0">
            <p className="flex flex-wrap items-baseline gap-x-2 font-semibold text-sm">
              {current.label}
              <SourceTag source={current.source} onKindClick={onKindClick} />
              {current.collapsed && <Badge variant="gray-outline">starts collapsed</Badge>}
            </p>
            {current.description && (
              <p className="text-foreground-muted text-xs">{current.description}</p>
            )}
          </div>
          {otherCount > 0 && (
            <button
              type="button"
              onClick={() => onSwitchTab(otherTab)}
              className="shrink-0 whitespace-nowrap rounded-sm text-custom-blue-700 text-xs hover:underline focus-visible:outline-2 focus-visible:outline-ring dark:text-custom-blue-300"
            >
              + {otherCount} in {otherTab === "attributes" ? "Attributes" : "Relationships"}
            </button>
          )}
        </div>
      )}

      {fields.length === 0 ? (
        <div className="flex h-24 items-center justify-center text-foreground-muted text-sm">
          {current
            ? `No ${tab} in ${current.label}.`
            : tab === "attributes"
              ? "No attribute"
              : "No relationship"}
        </div>
      ) : tab === "attributes" ? (
        (fields as AttributeSchema[]).map((attribute) => (
          <ProtoAttributeDisplay
            key={attribute.name}
            attribute={attribute}
            onKindClick={onKindClick}
            extra={extra(attribute)}
          />
        ))
      ) : (
        (fields as RelationshipSchema[]).map((relationship) => (
          <ProtoRelationshipDisplay
            key={relationship.name}
            relationship={relationship}
            onKindClick={onKindClick}
            extra={extra(relationship)}
          />
        ))
      )}
    </div>
  );
}

export function FilterRev04({ showFieldSource }: { showFieldSource: boolean }) {
  const [tab, setTab] = useState("attributes");
  const [selected, setSelected] = useState(ALL);

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
                      openLabel="filter the attributes to it"
                      onOpenSection={(name) => {
                        setSelected(name);
                        setTab("attributes");
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
                  selected={
                    viewerSectionsRev03(schema).some((s) => s.name === selected) ? selected : ALL
                  }
                  showFieldSource={showFieldSource}
                  onSelect={setSelected}
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
