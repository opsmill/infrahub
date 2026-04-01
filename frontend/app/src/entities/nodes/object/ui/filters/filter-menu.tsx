import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Col } from "@/shared/components/container";
import { Button } from "@/shared/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import type { Filter } from "@/shared/hooks/useFilters";

import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { FilterMenuItem } from "@/entities/nodes/object/ui/filters/filter-menu-item";
import { FilterMenuSection } from "@/entities/nodes/object/ui/filters/filter-menu-section";
import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/ui/filters/metadata-filter-definitions";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export interface SuggestedFilter {
  id: string;
  label: string;
  isActive: boolean;
  onToggle: () => void;
}

interface FilterMenuProps {
  schema: ModelSchema;
  filters: Filter[];
  suggestedFilters?: SuggestedFilter[];
}

export function FilterMenu({ schema, filters, suggestedFilters }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const [hoveredSchema, setHoveredSchema] = useState<AttributeSchema | RelationshipSchema | null>(
    null
  );

  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);

  const closeMenu = () => {
    setOpen(false);
    setHoveredSchema(null);
  };

  const hasSuggested = suggestedFilters && suggestedFilters.length > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="shrink-0 gap-1">
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start" className="flex gap-0 p-0" sideOffset={8}>
        <Col className="max-h-80 w-52 gap-1 overflow-y-auto border-gray-200 border-r p-2">
          {hasSuggested && (
            <FilterMenuSection title="Suggested">
              {suggestedFilters.map((sf) => (
                <button
                  key={sf.id}
                  type="button"
                  className="flex items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-gray-50"
                  onClick={() => {
                    sf.onToggle();
                    closeMenu();
                  }}
                >
                  <Icon
                    icon={sf.isActive ? "mdi:check-circle" : "mdi:plus-circle-outline"}
                    className={sf.isActive ? "text-custom-blue-700" : "text-gray-400"}
                  />
                  <span>{sf.label}</span>
                </button>
              ))}
            </FilterMenuSection>
          )}

          {ALL_METADATA_FILTERS.length > 0 && (
            <FilterMenuSection title="Metadata">
              {ALL_METADATA_FILTERS.map((metaSchema) => (
                <FilterMenuItem
                  key={metaSchema.name}
                  schema={metaSchema}
                  filters={filters}
                  onHover={setHoveredSchema}
                  isHovered={hoveredSchema?.name === metaSchema.name}
                />
              ))}
            </FilterMenuSection>
          )}

          {attributes.length > 0 && (
            <FilterMenuSection title="Attributes">
              {attributes.map((attr) => (
                <FilterMenuItem
                  key={attr.name}
                  schema={attr}
                  filters={filters}
                  onHover={setHoveredSchema}
                  isHovered={hoveredSchema?.name === attr.name}
                />
              ))}
            </FilterMenuSection>
          )}

          {relationships.length > 0 && (
            <FilterMenuSection title="Relationships">
              {relationships.map((rel) => (
                <FilterMenuItem
                  key={rel.name}
                  schema={rel}
                  filters={filters}
                  onHover={setHoveredSchema}
                  isHovered={hoveredSchema?.name === rel.name}
                />
              ))}
            </FilterMenuSection>
          )}
        </Col>

        {hoveredSchema && (
          <div className="min-w-64 p-0">
            {"peer" in hoveredSchema ? (
              <RelationshipFilterForm relationshipSchema={hoveredSchema} onSuccess={closeMenu} />
            ) : (
              <AttributeFilterForm attributeSchema={hoveredSchema} onSuccess={closeMenu} />
            )}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
