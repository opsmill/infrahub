import { Icon } from "@iconify-icon/react";
import { useState } from "react";

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
import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { FilterFormDispatch } from "@/entities/nodes/object/ui/filters/filter-form-dispatch";
import { FilterMenuItem } from "@/entities/nodes/object/ui/filters/filter-menu-item";
import { FilterMenuSection } from "@/entities/nodes/object/ui/filters/filter-menu-section";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export function getFilterCount(schema: ModelSchema, filters: Filter[]): number {
  const isIpamSchema = isOfKind(IP_PREFIX_GENERIC, schema) || isOfKind(IP_ADDRESS_GENERIC, schema);

  if (!isIpamSchema || hasIncompatibleFiltersForIpAvailability(filters)) {
    return filters.length;
  }

  const availabilityFilter = filters.find((f) => f.name === AVAILABLE_IP_FILTER_NAME);

  if (!availabilityFilter) {
    return filters.length + 1;
  }

  if (!availabilityFilter.value) {
    return filters.length - 1;
  }

  return filters.length;
}

interface FilterMenuProps {
  schema: ModelSchema;
  filters: Filter[];
}

export function FilterMenu({ schema, filters }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const [hoveredSchema, setHoveredSchema] = useState<AttributeSchema | RelationshipSchema | null>(
    null
  );

  const sections: Array<{ title: string; items: Array<AttributeSchema | RelationshipSchema> }> = [
    { title: "Metadata", items: ALL_METADATA_FILTERS },
    { title: "Attributes", items: getAttributesVisibleInListView(schema.attributes ?? []) },
    {
      title: "Relationships",
      items: getRelationshipsVisibleInListView(schema.relationships ?? []),
    },
  ];

  const filterCount = getFilterCount(schema, filters);

  const closeMenu = () => {
    setOpen(false);
    setHoveredSchema(null);
  };

  return (
    <Popover
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) setHoveredSchema(null);
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="shrink-0 gap-1">
          <Icon icon="mdi:filter-variant" className="text-base" />
          Filter
          {filterCount > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-gray-200 px-1 text-gray-600 text-xs">
              {filterCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start" className="flex gap-0 p-0" sideOffset={8}>
        <Col className="max-h-80 w-52 gap-1 overflow-y-auto border-gray-200 border-r p-2">
          {sections.map(
            ({ title, items }) =>
              items.length > 0 && (
                <FilterMenuSection key={title} title={title}>
                  {items.map((fieldSchema) => (
                    <FilterMenuItem
                      key={fieldSchema.name}
                      schema={fieldSchema}
                      filters={filters}
                      onHover={setHoveredSchema}
                      isHovered={hoveredSchema?.name === fieldSchema.name}
                    />
                  ))}
                </FilterMenuSection>
              )
          )}
        </Col>

        {hoveredSchema && (
          <div className="min-w-64 p-0">
            <FilterFormDispatch
              key={hoveredSchema.name}
              fieldSchema={hoveredSchema}
              onSuccess={closeMenu}
            />
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
