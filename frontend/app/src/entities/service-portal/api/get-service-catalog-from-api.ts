import { graphql, graphqlClient } from "@/shared/api/graphql/client";

const GET_SERVICE_CATALOG = graphql(`
  query ServiceCatalog {
    ServiceCatalog {
      count
      entries {
        id
        name
        description
        icon
        tags
        target_kind
        mode
        fields
        generators
        template_id
      }
    }
  }
`);

// No branch in the context: the portal always reads the default branch.
export const getServiceCatalogFromApi = async () => {
  return graphqlClient.query({ query: GET_SERVICE_CATALOG });
};
