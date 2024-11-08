import { SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import { AttributeSchema, RelationshipSchema } from "@/screens/schema/types";

type AddAttributesToRequestOptions = {
  withPermissions?: boolean;
};

export const addAttributesToRequest = (
  attributes: Array<AttributeSchema>,
  { withPermissions }: AddAttributesToRequestOptions = {}
) => {
  return attributes.reduce((acc, attribute) => {
    const fragment = {
      id: true,
      value: true,
      updated_at: true,
      is_default: true,
      is_from_profile: true,
      is_protected: true,
      is_visible: true,
      source: {
        id: true,
        display_label: true,
        __typename: true,
      },
      owner: {
        id: true,
        display_label: true,
        __typename: true,
      },
      permissions: {
        update_value: true,
      },
    };

    if (attribute.kind === SCHEMA_ATTRIBUTE_KIND.DROPDOWN) {
      return {
        ...acc,
        [attribute.name]: { ...fragment, color: true, description: true, label: true },
      };
    }

    if (withPermissions) {
      return {
        ...acc,
        [attribute.name]: {
          ...fragment,
        },
      };
    }

    return {
      ...acc,
      [attribute.name]: fragment,
    };
  }, {});
};

export const addRelationshipsToRequest = (relationships: Array<RelationshipSchema>) => {
  return relationships.reduce((acc, relationship) => {
    const fragment = {
      node: {
        id: true,
        display_label: true,
      },
    };

    if (relationship.cardinality === "one") {
      return {
        ...acc,
        [relationship.name]: {
          ...fragment,
        },
      };
    }

    if (relationship.cardinality === "many") {
      return {
        ...acc,
        [relationship.name]: {
          edges: {
            ...fragment,
          },
        },
      };
    }

    return acc;
  }, {});
};
