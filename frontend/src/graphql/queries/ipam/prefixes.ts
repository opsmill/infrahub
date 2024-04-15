import { gql } from "@apollo/client";

export const GET_NAMESPACES = gql`
  query IpamIPPrefix($ids: [String!]) {
    IpamIPPrefix(ip_namespace__ids: $ids) {
        edges {
          node {
            display_label
            id
            name {
              id
            }
            description {
              id
            }
          }
        }
      }
    }
  }
`;
