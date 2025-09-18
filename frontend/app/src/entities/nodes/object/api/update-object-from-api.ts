import { gql } from "@apollo/client";
import { jsonToGraphQLQuery } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";
import {
  RELATIONSHIP_BULK_ADD_PREFIX,
  RELATIONSHIP_BULK_REMOVE_PREFIX,
} from "@/shared/components/form/constants";

import { getRelationshipMutation } from "@/entities/nodes/object/utils/get-relationship-mutations";

export interface UpdateObjectFromApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, any>;
  profileIds?: Array<string>;
}

export function updateObjectFromApi({
  data,
  objectKind,
  profileIds = [],
  branchName,
}: UpdateObjectFromApiParams) {
  const objectData = Object.entries(data).reduce((acc, [key, value]) => {
    if (key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX) && value.value === null) {
      // WHen using the reset to null value, we need to use the regular mutation and not the RelationshipRemove
      return {
        ...acc,
        [key.replace(RELATIONSHIP_BULK_REMOVE_PREFIX, "")]: null,
      };
    }

    if (
      key.startsWith(RELATIONSHIP_BULK_ADD_PREFIX) ||
      key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX)
    ) {
      return acc;
    }

    return {
      ...acc,
      [key]: value,
    };
  }, {});

  const relationshipAddData = Object.entries(data).reduce((acc, [key, value]) => {
    if (key.startsWith(RELATIONSHIP_BULK_ADD_PREFIX)) {
      return {
        ...acc,
        [key.replace(RELATIONSHIP_BULK_ADD_PREFIX, "")]: value,
      };
    }

    return acc;
  }, {});

  const relationshipRemoveData = Object.entries(data).reduce((acc, [key, value]) => {
    if (!key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX)) {
      return acc;
    }

    if (key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX) && value.value === null) {
      // When using the reset to null value, we need to use the regular mutation and not the RelationshipRemove
      return acc;
    }

    return {
      ...acc,
      [key.replace(RELATIONSHIP_BULK_REMOVE_PREFIX, "")]: value,
    };
  }, {});

  const objectMutation = {
    [`${objectKind}Update`]: {
      __args: {
        data: {
          ...objectData,
          ...(profileIds?.length
            ? { profiles: profileIds.map((profileId) => ({ id: profileId })) }
            : {}),
        },
      },
      object: {
        id: true,
        display_label: true,
        hfid: true,
        __typename: true,
      },
    },
  };

  const relationshipAddMutation =
    objectData?.id && Object.entries(relationshipAddData)?.length
      ? getRelationshipMutation({
          id: objectData.id,
          data: relationshipAddData,
          mutation: "RelationshipAdd",
        })
      : {};

  const relationshipRemoveMutation =
    objectData?.id && Object.entries(relationshipRemoveData)?.length
      ? getRelationshipMutation({
          id: objectData.id,
          data: relationshipRemoveData,
          mutation: "RelationshipRemove",
        })
      : {};

  const mutation = jsonToGraphQLQuery({
    mutation: {
      ...objectMutation,
      ...relationshipAddMutation,
      ...relationshipRemoveMutation,
    },
  });

  return graphqlClient.mutate({
    mutation: gql(mutation),
    context: {
      branch: branchName,
    },
  });
}
