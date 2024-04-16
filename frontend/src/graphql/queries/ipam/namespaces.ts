import { gql } from "@apollo/client";

export const GET_NAMESPACES = gql`
  query IpamIPNamespace {
      IpamIPNamespace {
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
