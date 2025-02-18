import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

type AddAttributesToRequestOptions = {
  withMetadata?: boolean;
  withPermissions?: boolean;
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
  { withMetadata }: AddAttributesToRequestOptions = {}
) => {
  const baseFragment = {
    node: {
      id: true,
      hfid: true,
      display_label: true,
    },
    ...(withMetadata && {
      properties: {
        is_visible: true,
        is_protected: true,
        updated_at: true,
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
