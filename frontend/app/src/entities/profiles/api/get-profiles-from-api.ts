import { gql } from "@apollo/client";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import type { ContextParams } from "@/shared/api/types";

import type {
  ProfileAttributeField,
  ProfileQueryParams,
  ProfileRelationshipField,
} from "@/entities/profiles/types";

function buildAttributeQuery(attribute: ProfileAttributeField): string {
  const dropdownFields = attribute.kind === "Dropdown" ? "color\ndescription\nlabel" : "";

  return `${attribute.name} {
    value
    ${dropdownFields}
  }`;
}

function buildRelationshipQuery(relationship: ProfileRelationshipField): string {
  const nodeFields = `id
      display_label
      hfid
      __typename`;

  if (relationship.paginated) {
    return `${relationship.name} {
    edges {
      node {
        ${nodeFields}
      }
    }
  }`;
  }

  return `${relationship.name} {
    node {
      ${nodeFields}
    }
  }`;
}

function buildProfileQuery(profile: ProfileQueryParams): string {
  const attributeQueries = profile.attributes.map(buildAttributeQuery).join("\n");
  const relationshipQueries = profile.relationships.map(buildRelationshipQuery).join("\n");

  return `${profile.name} {
    edges {
      node {
        id
        display_label
        ${attributeQueries}
        ${relationshipQueries}
      }
    }
  }`;
}

function buildGetProfilesQuery(profiles: ProfileQueryParams[]): string {
  const profileQueries = profiles.map(buildProfileQuery).join("\n");

  return `query GetProfiles {
    ${profileQueries}
  }`;
}

export interface GetProfilesFromApiParams extends ContextParams {
  profiles: ProfileQueryParams[];
}

export function getProfilesFromApi({ profiles, branchName, atDate }: GetProfilesFromApiParams) {
  const queryString = buildGetProfilesQuery(profiles);

  const query = gql`
    ${queryString}
  `;

  return graphqlClient.query({
    query,
    context: {
      branch: branchName,
      date: atDate,
    },
  });
}
