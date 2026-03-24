import { graphql } from "gql.tada";

export const GET_ROLE_MANAGEMENT_COUNTS = graphql(`
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
    CoreGenericAccount {
      count
    }
  }
`);
