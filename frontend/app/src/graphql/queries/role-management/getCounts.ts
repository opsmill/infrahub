import { gql } from "@apollo/client";

export const GET_ROLE_MANAGEMENT_COUNTS = gql`
  query GET_ROLE_MANAGEMENT_COUNTS {
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
