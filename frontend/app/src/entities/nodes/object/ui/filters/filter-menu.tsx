import { Icon } from "@iconify-icon/react";
import { useMemo, useState } from "react";

import { Col } from "@/shared/components/container";
import { Button } from "@/shared/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import type { Filter } from "@/shared/hooks/useFilters";

import {
  AVAILABLE_IP_FILTER_NAME,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { hasIncompatibleFiltersForIpAvailability } from "@/entities/ipam/utils";
import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { FilterMenuItem } from "@/entities/nodes/object/ui/filters/filter-menu-item";
import { FilterMenuSection } from "@/entities/nodes/object/ui/filters/filter-menu-section";
import {
  ALL_METADATA_FILTERS,
  isMetadataFilter,
} from "@/entities/nodes/object/ui/filters/metadata-filter-definitions";
import { MetadataFilterForm } from "@/entities/nodes/object/ui/filters/metadata-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface FilterMenuProps {
  schema: ModelSchema;
  filters: Filter[];
}

export function FilterMenu({ schema, filters }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const [hoveredSchema, setHoveredSchema] = useState<AttributeSchema | RelationshipSchema | null>(
    null
  );

  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);

  // Adjust filter count for IPAM suggested filters that are enabled by default (not in URL)
  // +1 when the availability filter is implicitly active (not in URL)
  // -1 when it's explicitly disabled (in URL as false)
  const filterCount = useMemo(() => {
    const isIpamSchema =
      isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

    if (!isIpamSchema || hasIncompatibleFiltersForIpAvailability(filters)) {
      return filters.length;
    }

    const availabilityFilter = filters.find((f) => f.name === AVAILABLE_IP_FILTER_NAME);

    if (!availabilityFilter) {
      // Implicitly active (default state) — not in URL but effectively filtering
      return filters.length + 1;
    }

    if (!availabilityFilter.value) {
      // Explicitly disabled — in URL but not an active filter
      return filters.length - 1;
    }

    return filters.length;
  }, [filters, schema]);

  const closeMenu = () => {
    setOpen(false);
    setHoveredSchema(null);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="shrink-0 gap-1">
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
          {filterCount > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-gray-200 px-1 text-xs text-gray-600">
              {filterCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start" className="flex gap-0 p-0" sideOffset={8}>
        <Col className="max-h-80 w-52 gap-1 overflow-y-auto border-gray-200 border-r p-2">
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
            {isMetadataFilter(hoveredSchema.name) ? (
              <MetadataFilterForm metadataFilter={hoveredSchema} onSuccess={closeMenu} />
            ) : "peer" in hoveredSchema ? (
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
