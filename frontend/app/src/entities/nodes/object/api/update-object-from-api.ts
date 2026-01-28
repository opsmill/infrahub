import { gql } from "@apollo/client";
import { jsonToGraphQLQuery, VariableType } from "json-to-graphql-query";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { BranchContextParams } from "@/shared/api/types";
import {
  RELATIONSHIP_BULK_ADD_PREFIX,
  RELATIONSHIP_BULK_REMOVE_PREFIX,
} from "@/shared/components/form/constants";

import { getRelationshipMutation } from "@/entities/nodes/object/utils/get-relationship-mutations";

export interface UpdateObjectFromApiParams extends BranchContextParams {
  objectKind: string;
  data: Record<string, unknown>;
  profileIds?: Array<string>;
  file?: File;
}

export function updateObjectFromApi({
  data,
  objectKind,
  profileIds = [],
  branchName,
  file,
}: UpdateObjectFromApiParams) {
  const hasFile = file instanceof File;

  const objectData: Record<string, unknown> = Object.entries(data).reduce((acc, [key, value]) => {
    const valueWithProp = value as { value?: unknown };
    if (key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX) && valueWithProp.value === null) {
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

    const valueWithProp = value as { value?: unknown };
    if (key.startsWith(RELATIONSHIP_BULK_REMOVE_PREFIX) && valueWithProp.value === null) {
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
        ...(hasFile && { file: new VariableType("file") }),
      },
      object: {
        id: true,
        display_label: true,
        hfid: true,
        __typename: true,
      },
    },
    ...(hasFile && { __variables: { file: "Upload!" } }),
  };

  const relationshipAddMutation =
    objectData?.id && Object.entries(relationshipAddData)?.length
      ? getRelationshipMutation({
          id: objectData.id as string,
          data: relationshipAddData as Record<string, Array<{ id: string }>>,
          mutation: "RelationshipAdd",
        })
      : {};

  const relationshipRemoveMutation =
    objectData?.id && Object.entries(relationshipRemoveData)?.length
      ? getRelationshipMutation({
          id: objectData.id as string,
          data: relationshipRemoveData as Record<string, Array<{ id: string }>>,
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
    variables: hasFile ? { file } : undefined,
    context: {
      branch: branchName,
    },
  });
}
