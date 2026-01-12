import type { TagGroupProps } from "react-aria-components";
import { useMemo } from "react";

import { ActiveFilterTags } from "@/shared/components/filters/active-filter-tags";

import {
  AVAILABLE_IP_FILTER_NAME,
  HIDE_AVAILABLE_IP,
  HIDE_AVAILABLE_IP_FILTER,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
  SHOW_AVAILABLE_IP,
} from "@/entities/ipam/constants";
import { IpAddressAvailabilityFilterTag } from "@/entities/ipam/ip-addresses/ui/ip-address-availability-filter-tag";
import { IpPrefixAvailabilityFilterTag } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-availability-filter-tag";
import {
  HIDE_INTERNAL_GROUPS_FILTER,
  HIDE_INTERNAL_GROUPS_ID,
  InternalGroupsFilterTag,
  SHOW_INTERNAL_GROUPS_ID,
} from "@/entities/nodes/object/ui/filters/internal-groups-filter-tag";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export interface ActiveObjectsFilterTagsProps extends TagGroupProps {
  schema: ModelSchema;
}

export function ActiveObjectFilterTags({ schema, ...props }: ActiveObjectsFilterTagsProps) {
  const { filters, setFilters } = useObjectTableContext();

  // Build field schemas map from model schema
  const fieldSchemas = useMemo(() => {
    const schemas: Record<string, AttributeSchema | RelationshipSchema> = {};
    for (const attr of schema?.attributes ?? []) {
      schemas[attr.name] = attr;
    }
    for (const rel of schema?.relationships ?? []) {
      schemas[rel.name] = rel;
    }
    return schemas;
  }, [schema]);

  // Filter out special filters that are handled separately
  const displayFilters = useMemo(() => {
    return filters.filter((f) => f.name !== HIDE_INTERNAL_GROUPS_FILTER.name);
  }, [filters]);

  // Handle custom filter removal for special cases
  const handleCustomFilterRemove = (filterName: string): boolean => {
    switch (filterName) {
      case HIDE_INTERNAL_GROUPS_ID: {
        setFilters([HIDE_INTERNAL_GROUPS_FILTER, ...filters]);
        return true;
      }
      case SHOW_INTERNAL_GROUPS_ID: {
        setFilters(filters.filter((filter) => filter.name !== HIDE_INTERNAL_GROUPS_FILTER.name));
        return true;
      }
      case SHOW_AVAILABLE_IP: {
        setFilters(filters.filter((filter) => filter.name !== AVAILABLE_IP_FILTER_NAME));
        return true;
      }
      case HIDE_AVAILABLE_IP: {
        setFilters([HIDE_AVAILABLE_IP_FILTER, ...filters]);
        return true;
      }
      default:
        return false;
    }
  };

  const additionalTags = (
    <>
      {isOfKind("CoreGroup", schema) && <InternalGroupsFilterTag />}
      {isOfKind(IP_PREFIX_GENERIC, schema) && <IpPrefixAvailabilityFilterTag />}
      {isOfKind(IP_ADDRESS_GENERIC, schema) && <IpAddressAvailabilityFilterTag />}
    </>
  );

  return (
    <ActiveFilterTags
      filters={displayFilters}
      setFilters={setFilters}
      fieldSchemas={fieldSchemas}
      additionalTags={additionalTags}
      onCustomFilterRemove={handleCustomFilterRemove}
      {...props}
    />
  );
}
