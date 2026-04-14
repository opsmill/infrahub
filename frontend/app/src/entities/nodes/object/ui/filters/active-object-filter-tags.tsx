import type { TagGroupProps } from "react-aria-components";

import { ActiveFilterTags } from "@/shared/components/filters/active-filter-tags";
import type { Filter } from "@/shared/hooks/useFilters";

import {
  AVAILABLE_IP_FILTER_NAME,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { IpAddressAvailabilityFilterTag } from "@/entities/ipam/ip-addresses/ui/ip-address-availability-filter-tag";
import { IpPrefixAvailabilityFilterTag } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-availability-filter-tag";
import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { getFilterDefinitionName } from "@/entities/nodes/object/domain/filter-definition";
import { ALL_METADATA_FILTERS } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import {
  HIDE_INTERNAL_GROUPS_FILTER,
  InternalGroupsFilterTag,
} from "@/entities/nodes/object/ui/filters/internal-groups-filter-tag";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getDecisionOptions } from "@/entities/role-manager/domain/get-decision-options";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export interface ActiveObjectsFilterTagsProps extends TagGroupProps {
  schema: ModelSchema;
}

function buildFilterDefinitions(schema: ModelSchema): Record<string, FilterDefinition> {
  const definitions: Record<string, FilterDefinition> = {};

  for (const attr of schema?.attributes ?? []) {
    const decisionOptions = getDecisionOptions(schema.kind, attr.name);
    definitions[attr.name] = decisionOptions
      ? { type: "permission-decision", schema: attr, options: decisionOptions }
      : { type: "attribute", schema: attr };
  }
  for (const rel of schema?.relationships ?? []) {
    definitions[rel.name] = { type: "relationship", schema: rel };
  }
  for (const meta of ALL_METADATA_FILTERS) {
    definitions[getFilterDefinitionName(meta)] = meta;
  }

  return definitions;
}

const HIDDEN_FILTER_NAMES = new Set([HIDE_INTERNAL_GROUPS_FILTER.name, AVAILABLE_IP_FILTER_NAME]);

function excludeHiddenFilters(filters: Filter[]): Filter[] {
  return filters.filter((f) => !HIDDEN_FILTER_NAMES.has(f.name));
}

export function ActiveObjectFilterTags({ schema, ...props }: ActiveObjectsFilterTagsProps) {
  const { filters, setFilters } = useObjectTableContext();

  const hasAdditionalTags =
    isOfKind("CoreGroup", schema) ||
    isOfKind(IP_PREFIX_GENERIC, schema) ||
    isOfKind(IP_ADDRESS_GENERIC, schema);

  const additionalTags = hasAdditionalTags ? (
    <>
      {isOfKind("CoreGroup", schema) && <InternalGroupsFilterTag />}
      {isOfKind(IP_PREFIX_GENERIC, schema) && <IpPrefixAvailabilityFilterTag />}
      {isOfKind(IP_ADDRESS_GENERIC, schema) && <IpAddressAvailabilityFilterTag />}
    </>
  ) : undefined;

  return (
    <ActiveFilterTags
      filters={excludeHiddenFilters(filters)}
      setFilters={setFilters}
      filterDefinitions={buildFilterDefinitions(schema)}
      additionalTags={additionalTags}
      {...props}
    />
  );
}
