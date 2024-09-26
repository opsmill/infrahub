import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_COUNTS = gql`
  query {
    CoreAccountRole {
      count
    }
    CoreAccountGroup {
      count
    }
    CoreGlobalPermission {
      count
    }
    CoreObjectPermission {
      count
    }
    CoreAccount {
      count
    }
  }
`;
