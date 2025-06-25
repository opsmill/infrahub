import { getRelationshipParent } from "@/entities/nodes/api/getRelationshipParent";
import { getSchema } from "@/entities/schema/domain/get-schema";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ContextParams } from "@/shared/api/types";
import { gql } from "@apollo/client";

interface DefaultValue {
  value?: {
    id?: string;
  } | null;
}

interface GetDefaultParentFromApiParams extends ContextParams {
  parentRelationship: {
    peer?: string;
    direction?: "bidirectional" | "inbound" | "outbound";
    identifier?: string;
  };
  defaultValue?: DefaultValue;
}

export const getDefaultParentFromApi = ({
  parentRelationship,
  defaultValue,
  branchName,
  atDate,
}: GetDefaultParentFromApiParams) => {
  const { schema: parentRelationshipSchema } = getSchema(parentRelationship?.peer);

  const parentRelationshipAttribute = parentRelationshipSchema?.relationships?.find(
    (relationship) => {
      if (parentRelationship?.direction === "bidirectional") {
        return relationship.identifier === parentRelationship?.identifier;
      }

      if (parentRelationship?.direction === "inbound") {
        return (
          relationship.direction === "outbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      if (parentRelationship?.direction === "outbound") {
        return (
          relationship.direction === "inbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      return false;
    }
  );

  const id =
    defaultValue?.value && typeof defaultValue.value === "object" && "id" in defaultValue.value
      ? defaultValue.value.id
      : undefined;

  if (!parentRelationship?.peer || !parentRelationshipAttribute?.name) {
    return {};
  }

  const queryString = getRelationshipParent({
    kind: parentRelationship?.peer,
    attribute: `${parentRelationshipAttribute?.name}__ids`,
    id,
  });

  const query = gql`${queryString}`;

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
      queryDeduplication: false,
      processErrorMessage: () => {},
    },
  });
};
