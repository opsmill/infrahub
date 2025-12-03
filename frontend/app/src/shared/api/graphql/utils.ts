import type { Filter } from "@/shared/hooks/useFilters";

import { AVAILABLE_IP_FILTER_NAME } from "@/entities/ipam/constants";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export type AddAttributesToRequestOptions = {
  withMetadata?: boolean;
  withPermissions?: boolean;
  relationshipFragment?: Record<string, string>;
};

type QueryAsJSON = { [key: string]: boolean | QueryAsJSON };

export const addAttributesToRequest = (
  attributes: Array<AttributeSchema>,
  { withMetadata, withPermissions }: AddAttributesToRequestOptions = {}
) => {
  let baseFragment: QueryAsJSON = {
    id: true,
    value: true,
  };

  return attributes.reduce((acc, attribute) => {
    let fragment = baseFragment;

    if (attribute.kind === ATTRIBUTE_KIND.DROPDOWN) {
      fragment = { ...fragment, color: true, description: true, label: true };
    }

    if (withMetadata) {
      fragment = {
        ...fragment,
        updated_at: true,
        is_default: true,
        is_from_profile: true,
        is_protected: true,
        source: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
      };
    }

    if (withPermissions) {
      fragment = {
        ...fragment,
        permissions: {
          update_value: true,
        },
      };
    }

    return {
      ...acc,
      [attribute.name]: fragment,
    };
  }, {});
};

export const addRelationshipsToRequest = (
  relationships: Array<RelationshipSchema>,
  { relationshipFragment, withMetadata }: AddAttributesToRequestOptions = {}
) => {
  const baseFragment = {
    node: {
      id: true,
      hfid: true,
      display_label: true,
      ...(relationshipFragment ?? {}),
    },
    ...(withMetadata && {
      properties: {
        is_protected: true,
        updated_at: true,
        source: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
        owner: {
          id: true,
          hfid: true,
          display_label: true,
          __typename: true,
        },
      },
    }),
  };

  return relationships.reduce((acc, relationship) => {
    if (!["one", "many"].includes(relationship.cardinality)) {
      return acc;
    }

    return {
      ...acc,
      [relationship.name]:
        relationship.cardinality === "one" ? baseFragment : { edges: baseFragment },
    };
  }, {});
};

export const addFiltersToRequest = (filters: Array<Filter>) => {
  return filters.reduce(
    (acc, filter) => {
      if (filter.name === AVAILABLE_IP_FILTER_NAME) {
        acc[AVAILABLE_IP_FILTER_NAME] = filter.value;
        return acc;
      }

      const [fieldName, fieldKey] = filter.name.split("__");
      if (!fieldName || !fieldKey) {
        return acc;
      }

      switch (fieldKey) {
        case "value":
        case "values": {
          acc.partial_match = true; // Add partial_match for text-based filters
          acc[filter.name] = filter.value;
          break;
        }
        case "isnull": {
          acc[filter.name] = filter.value;
          break;
        }
        case "ids": {
          acc[filter.name] = filter.value.map(({ id }: { id: string }) => id);
          break;
        }
      }

      return acc;
    },
    {} as Record<string, string | number | boolean | string[]>
  );
};

export const dropIncludeAvailableWhenFalse = (filters?: Filter[]) =>
  filters?.filter((f) => !(f.name === AVAILABLE_IP_FILTER_NAME && f.value === false));
