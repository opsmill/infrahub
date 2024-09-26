import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_OBJECT_PERMISSIONS = gql`
  query {
    CoreObjectPermission {
      edges {
        node {
          display_label
          name {
            value
          }
          branch {
            value
          }
          namespace {
            value
          }
          action {
            value
          }
          decision {
            value
          }
          roles {
            count
          }
        }
      }
    }
  }
`;
